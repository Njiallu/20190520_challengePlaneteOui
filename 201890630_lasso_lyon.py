#importing the libraries
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, time
from vacances_scolaires_france import SchoolHolidayDates
import sys
from impyute.imputation.cs import mice
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import cross_val_score
from sklearn.model_selection import TimeSeriesSplit

# my fonctions
def conv(data):
    data["date"] = data.timestamp.apply(lambda x : x.split('T')[0])
    data["datetime_perso"] = data.timestamp.apply(lambda x : get_format_the_date(x))
    data['year']=data['datetime_perso'].dt.year
    data['month']=data['datetime_perso'].dt.month
    data['timestamp'] = pd.to_datetime(data['timestamp'])
    data['hours'] = data['timestamp'].dt.hour
    return data

## get season
def get_season(doy):
    spring = range(80, 172)
    summer = range(172, 264)
    fall = range(264, 355)
    if doy in spring:
        season = 'spring'
    elif doy in summer:
      season = 'summer'
    elif doy in fall:
        season = 'fall'
    else:
        season = 'winter'
    return season

## verifie si jour ferie
def easter_date(year):
    a = year // 100
    b = year % 100
    c = (3 * (a + 25)) // 4
    d = (3 * (a + 25)) % 4
    e = (8 * (a + 11)) // 25
    f = (5 * a + b) % 19
    g = (19 * f + c - e) % 30
    h = (f + 11 * g) // 319
    j = (60 * (5 - d) + b) // 4
    k = (60 * (5 - d) + b) % 4
    m = (2 * j - k - g + h) % 7
    n = (g - h + m + 114) // 31
    p = (g - h + m + 114) % 31
    day = p + 1
    month = n
    return datetime(year, month, day)

def is_ferie(the_date):
    year = the_date.year
    easter = easter_date(year)
    days = [
        datetime(year, 1, 1),  # Premier de l'an
        easter + timedelta(days=1),  # Lundi de Pâques
        datetime(year, 5, 1),  # Fête du Travail
        datetime(year, 5, 8),  # Victoire de 1945
        easter + timedelta(days=39),  # Ascension
        easter + timedelta(days=49),  # Pentecôte
        datetime(year, 7, 14),  # Fête Nationale
        datetime(year, 8, 15),  # Assomption
        datetime(year, 11, 1),  # Toussaint
        datetime(year, 11, 11),  # Armistice 1918
        datetime(year, 12, 25),  # Noël
    ]
    return the_date in days

def get_format_the_date(timestamp):
    do = datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%S.%f')
    d5 = do.replace(minute=0, hour=0, second=0, microsecond=0).isoformat(' ')
    the_date = datetime.strptime(d5, "%Y-%m-%d %H:%M:%S")
    return the_date

def business_day(timestamp):
    if not is_ferie(timestamp) and timestamp.isoweekday() not in [6, 7]:
        return True
    else:
        return False
    
#------------------------------------------------------------------------------    
# creere un je de test
dataInt = pd.read_csv('./data_set1/input_training_ssnsrY0.csv')
dataTest = pd.read_csv('./data_set1/input_test_cdKcI0e.csv')
dataOut = pd.read_csv('./data_set1/output_training_Uf11I9I.csv')
dataInt.info()
data_blink = pd.concat([dataInt, dataOut[['consumption_1', 'consumption_2']]], axis=1)
#----------------------
#SPLIT
tscv = TimeSeriesSplit(n_splits=10)
print(tscv)
for train_index, test_index in tscv.split(dataInt):
    print("TRAIN:", train_index, "TEST:", test_index)
    X_train, X_test = dataInt.iloc[train_index, :], dataInt.iloc[test_index, :]
    y_train, y_test = dataOut.iloc[train_index, :], dataOut.iloc[test_index, :]
    
# jeu de donnees propres:
    # X-train et y_train pour faire le modele
    # X_test et y_test pour tester mon modele
    # dataTest pour la soumission 
#******************************************************************************    
## data engeebering Xtrain (a aplliquer sur x_test et dataTest)
dI = X_train.copy()
## missing value
dI_num = dI.drop(['timestamp','loc_1', 'loc_2', 'loc_secondary_1', 'loc_secondary_2', 'loc_secondary_3'], axis=1)
imputed_training_mice=mice(dI_num.values)
data_mice = pd.DataFrame(imputed_training_mice, columns=dI_num.columns, index = list(dI.index.values))
dI_NonNum = dI.select_dtypes(include=[np.object])
dClean = data_mice.join(dI_NonNum)

## drop variable inutile
d_tr = dClean.drop(['loc_1', 'loc_2', 'loc_secondary_1', 'loc_secondary_2', 'loc_secondary_3'], axis=1)
## create extra attribute
d_tr.info() #  A ENLEVER
conv(d_tr)
d_tr['timestamp'] = pd.to_datetime(d_tr.timestamp, format = '%Y-%m-%dT%H:%M:%S.%f')
## create season and rangeInYear
s = pd.to_datetime(pd.Series(d_tr['timestamp']))
d_tr['rangeInYear'] = s.dt.strftime('%j').astype(int)
#create jours working days
d_tr['is_business_day'] = d_tr['datetime_perso'].apply(lambda e : int(business_day(e)))
# Is it an holiday for zone A, B or C?
d = SchoolHolidayDates()
d_tr['is_holiday'] = d_tr['datetime_perso'].apply(lambda f : int(d.is_holiday(datetime.date(f))))
d_tr['season'] = d_tr['rangeInYear'].apply(lambda d : get_season(d))
d_tr= d_tr.drop(['rangeInYear', 'datetime_perso', 'date', 'timestamp'], axis=1)

## gerer les dummies et les variables num
Xtrain_new = d_tr.drop(['ID'], axis=1)
Xtrain_new.shape
featuresObject = ['season', 'year', 'month', 'hours', 'is_business_day', 'is_holiday']
for var in featuresObject:
    Xtrain_new[var] = Xtrain_new[var].astype('category')
Xtrain_new.dtypes
numeric_features_col_name_train = [f for f in Xtrain_new.columns if Xtrain_new[f].dtype == float]
numeric_features_train = Xtrain_new[numeric_features_col_name_train]
# Les Num
Xtrain_new.info()
Xtrain_new[numeric_features_col_name_train].dtypes
ct_num = ColumnTransformer([
        ('stdScal', StandardScaler(), ['temp_1','temp_2','mean_national_temp','humidity_1',
         'humidity_2','consumption_secondary_1','consumption_secondary_2','consumption_secondary_3'])],
    remainder='passthrough')
X_tr = ct_num.fit_transform(numeric_features_train)
Xtrain_new[numeric_features_col_name_train] = pd.DataFrame(X_tr, columns=numeric_features_train.columns, index = list(X_train.index.values))

Xtrain_new.info()

# Gerer les variables categoriques
ct = ColumnTransformer([
        ('oh_enc', 
         OneHotEncoder(sparse=False), 
         [8,9,10,11,12,13]),])
d_1he = ct.fit_transform(Xtrain_new)
d_encoded_data = pd.DataFrame(d_1he, columns=ct.get_feature_names())
d_encoded_data.drop(['oh_enc__x0_2016', 'oh_enc__x1_1','oh_enc__x2_0', 'oh_enc__x3_0','oh_enc__x4_0', 'oh_enc__x5_fall'], inplace=True, axis=1)
df_concat = pd.concat([Xtrain_new.reset_index(drop=True), d_encoded_data.reset_index(drop=True)], axis=1)
df_concat.drop(['season', 'year', 'month', 'hours', 'is_business_day', 'is_holiday'], inplace=True, axis=1)
X_trained = df_concat[:dataInt.shape[0]]

#******************************************************************************
## data engeebering sur x_test et dataTest)
dI = X_test.copy()
## missing value
dI_num = dI.drop(['timestamp','loc_1', 'loc_2', 'loc_secondary_1', 'loc_secondary_2', 'loc_secondary_3'], axis=1)
imputed_training_mice=mice(dI_num.values)
data_mice = pd.DataFrame(imputed_training_mice, columns=dI_num.columns, index = list(dI.index.values))
dI_NonNum = dI.select_dtypes(include=[np.object])
dClean = data_mice.join(dI_NonNum)

## drop variable inutile
d_tr = dClean.drop(['loc_1', 'loc_2', 'loc_secondary_1', 'loc_secondary_2', 'loc_secondary_3'], axis=1)
## create extra attribute
d_tr.info() #  A ENLEVER
conv(d_tr)
d_tr['timestamp'] = pd.to_datetime(d_tr.timestamp, format = '%Y-%m-%dT%H:%M:%S.%f')
## create season and rangeInYear
s = pd.to_datetime(pd.Series(d_tr['timestamp']))
d_tr['rangeInYear'] = s.dt.strftime('%j').astype(int)
#create jours working days
d_tr['is_business_day'] = d_tr['datetime_perso'].apply(lambda e : int(business_day(e)))
# Is it an holiday for zone A, B or C?
d = SchoolHolidayDates()
d_tr['is_holiday'] = d_tr['datetime_perso'].apply(lambda f : int(d.is_holiday(datetime.date(f))))
d_tr['season'] = d_tr['rangeInYear'].apply(lambda d : get_season(d))
d_tr= d_tr.drop(['rangeInYear', 'datetime_perso', 'date', 'timestamp'], axis=1)

## gerer les dummies et les variables num


Xtest_new = d_tr.drop(['ID'], axis=1)
featuresObject = ['season', 'year', 'month', 'hours', 'is_business_day', 'is_holiday']
for tar in featuresObject:
    Xtest_new[tar] = Xtest_new[tar].astype('category')

numeric_features_col_name_test = [e for e in Xtest_new.columns if Xtest_new[e].dtype == float]
numeric_features_test = Xtest_new[numeric_features_col_name_test]
# Les Num

X_tr = ct_num.fit(numeric_features_test)
Xtest_new[numeric_features_col_name_test] = pd.DataFrame(X_tr, columns=numeric_features_test.columns, index = list(X_test.index.values))
Xtest_new.info()
# Gerer les variables categoriques

d_1he_test = ct.fit(Xtest_new)

Xtest_new.info()
Xtrain_new.info()
d_encoded_data = pd.DataFrame(d_1he_test, columns=ct.get_feature_names(), index = list(X_test.index.values))
d_encoded_data.drop(['oh_enc__x0_2016', 'oh_enc__x1_1','oh_enc__x2_0', 'oh_enc__x3_0','oh_enc__x4_0', 'oh_enc__x5_fall'], inplace=True, axis=1)
df_concat = pd.concat([Xtest_new.reset_index(drop=True), d_encoded_data.reset_index(drop=True)], axis=1)
df_concat.drop(['season', 'year', 'month', 'hours', 'is_business_day', 'is_holiday'], inplace=True, axis=1)
X_test = df_concat[:dataInt.shape[0]]
#******************************************************************************
# prep y_train et y test
y_train = y_train.drop(['ID'], axis=1)
y_test = y_test.drop(['ID'], axis=1)
#*******************************************************************************
###*****************     FAIRE DES ESSAIS    **********************************


dI = some_data.copy()
## missing value
dI_num = dI.drop(['timestamp','loc_1', 'loc_2', 'loc_secondary_1', 'loc_secondary_2', 'loc_secondary_3'], axis=1)
imputed_training_mice=mice(dI_num.values)
data_mice = pd.DataFrame(imputed_training_mice, columns=dI_num.columns, index = list(dI.index.values))
dI_NonNum = dI.select_dtypes(include=[np.object])
dClean = data_mice.join(dI_NonNum)

## drop variable inutile
d_tr = dClean.drop(['loc_1', 'loc_2', 'loc_secondary_1', 'loc_secondary_2', 'loc_secondary_3'], axis=1)
## create extra attribute
d_tr.info() #  A ENLEVER
conv(d_tr)
d_tr['timestamp'] = pd.to_datetime(d_tr.timestamp, format = '%Y-%m-%dT%H:%M:%S.%f')
## create season and rangeInYear
s = pd.to_datetime(pd.Series(d_tr['timestamp']))
d_tr['rangeInYear'] = s.dt.strftime('%j').astype(int)
#create jours working days
d_tr['is_business_day'] = d_tr['datetime_perso'].apply(lambda e : int(business_day(e)))
# Is it an holiday for zone A, B or C?
d = SchoolHolidayDates()
d_tr['is_holiday'] = d_tr['datetime_perso'].apply(lambda f : int(d.is_holiday(datetime.date(f))))
d_tr['season'] = d_tr['rangeInYear'].apply(lambda d : get_season(d))
d_tr= d_tr.drop(['rangeInYear', 'datetime_perso', 'date', 'timestamp'], axis=1)

## gerer les dummies et les variables num
Xtrain_new = d_tr.drop(['ID'], axis=1)
Xtrain_new.shape
featuresObject = ['season', 'year', 'month', 'hours', 'is_business_day', 'is_holiday']
for var in featuresObject:
    Xtrain_new[var] = Xtrain_new[var].astype('category')
Xtrain_new.info()
numeric_features_col_name = [f for f in Xtrain_new.columns if Xtrain_new[f].dtype == float]
numeric_features = Xtrain_new[numeric_features_col_name]
# Les Num
ct_num = ColumnTransformer([
        ('stdScal', StandardScaler(), ['temp_1','temp_2','mean_national_temp','humidity_1',
         'humidity_2','consumption_secondary_1','consumption_secondary_2','consumption_secondary_3'])],
    remainder='passthrough')
X = ct_num.fit_transform(numeric_features)
Xtrain_new[numeric_features_col_name] = pd.DataFrame(X, columns=numeric_features.columns)
# Gerer les variables categoriques
ct = ColumnTransformer([
        ('oh_enc', 
         OneHotEncoder(sparse=False), 
         [8,9,10,11,12,13]),])
d_1he = ct.fit_transform(Xtrain_new)
d_encoded_data = pd.DataFrame(d_1he, columns=ct.get_feature_names())
d_encoded_data.drop(['oh_enc__x0_2016', 'oh_enc__x1_1','oh_enc__x2_0', 'oh_enc__x3_0','oh_enc__x4_0', 'oh_enc__x5_fall'], inplace=True, axis=1)
df_concat = pd.concat([Xtrain_new.reset_index(drop=True), d_encoded_data.reset_index(drop=True)], axis=1)
df_concat.drop(['season', 'year', 'month', 'hours', 'is_business_day', 'is_holiday'], inplace=True, axis=1)
X_somedata= df_concat[:dataInt.shape[0]]


#------------------------------------------------------------------------------


## SELECTIONNER ET ENTRAINER UN MODELE
some_data = X_train.iloc[:5]
some_labels = y_train.iloc[:5]

## 

Lasso = linear_model.Lasso()
>>> print(cross_val_score(lasso, X, y, cv=3))


lin_reg = LinearRegression()
lin_reg.fit(Xtrain_prep, ytrain_prep)
lin_reg.fit(Xtrain_prep, ytrain_prep)

# let's try the full preprocessing pipeline on a few training instances
some_data = Xtrain.iloc[:5]
some_labels = ytrain.iloc[:5]
some_data_prepared = full_pipeline.transform(some_data)





print("Predictions:", lin_reg.predict(some_data_prepared))


#TEST  
# partie intTest : test_new = d_ready[d_ready['consumption_1'].isnull()]
#                   test_new = test_new.drop(['consumption_1', 'consumption_2', 'ID'], axis=1)
#for var in featuresObject:
#    test_new[var] = test_new[var].astype('category')
#test_new.shape
#TEST
#test_new = ct_num.fit(numeric_features)
#d_ready.select_dtypes(include=['float64', 'int64']).columns
#Get Feature Names of Encoded columns
#ct.get_feature_names()
# Converting the numpy array into a pandas dataframe

#Concatenating the encoded dataframe with the original dataframe
# Dropping drive-wheels, make and engine-location columns as they are encoded
# Viewing few rows of data
#y_train = df_concat[['consumption_1', 'consumption_2']]
#X_train_prep = df_concat.drop(['consumption_1', 'consumption_2'], axis=1) 


#TEST
#ct = ColumnTransformer([
#        ('oh_enc', 
#         OneHotEncoder(sparse=False), 
#         [8,9,10,11,12,13]),])
#d_1heTest= ct.fit(test_new)
#d_encoded_data = pd.DataFrame(d_1heTest, columns=ct.get_feature_names())
#df_concat = pd.concat([test_new.reset_index(drop=True), d_encoded_data.reset_index(drop=True)], axis=1)
#X_test = df_concat.drop(['season', 'year', 'month', 'hours', 'is_business_day', 'is_holiday'], inplace=True, axis=1)



lin_reg = LinearRegression()
lin_reg.fit(X_train, y_train)

consum_predictions = lin_reg.predict(X_train)
lin_mse = mean_squared_error(y_train, consum_predictions)
lin_rmse = np.sqrt(lin_mse)
print('linear_train_rmse', lin_rmse)  #model might be underfitting

from sklearn.model_selection import cross_val_score

scores = cross_val_score(lin_reg, X_train, y_train, scoring='neg_mean_squared_error', cv=10)
lin_rmse_scores = np.sqrt(-scores)
def explain_scores(scores):
    print("Scores:", scores)
    print("Mean:", scores.mean())
    print("Standard deviation:", scores.std())
explain_scores(lin_rmse_scores)

from sklearn.linear_model import Lasso
regLasso1 = Lasso(fit_intercept=False,normalize=False)
print(regLasso1)
regLasso1.fit(X_train, y_train)
print(regLasso1.coef_)

my_alphas = np.array([0.001,0.01,0.02,0.025,0.05,0.1,0.25,0.5,0.8,1.0])
from sklearn.linear_model import lasso_path
alpha_for_path, coefs_lasso, _ = lasso_path(X_train, y_train ,alphas=my_alphas)
print(coefs_lasso.shape)
import matplotlib.cm as cm
couleurs = cm.rainbow(numpy.linspace(0,1,16))





# A helper function for writing predictions to a file
def write_to_submission_file(predicted_labels, out_file,
                             target='target', index_label="session_id"):
    predicted_df = pd.DataFrame(predicted_labels,
                                index = np.arange(1, predicted_labels.shape[0] + 1),
                                columns=[target])
    predicted_df.to_csv(out_file, index_label=index_label)



#-------------------------------------------------------------------------



# Imputation par KNN 
#sys.setrecursionlimit(100000) #Increase the recursion limit of the OS
# start the KNN training
#imputed_training_KNN=fast_knn(data_missing.values, k=30)





# dropping unncessary columns
dataTrain = dataTrain.drop(dropFeatures, axis=1)
dataTest = dataTest.drop(dropFeatures, axis=1)
#let's name the categorical and numeical attributes 



#RMSLE Scorer
def rmsle(y, y_,convertExp=True):
    if convertExp:
        y = np.exp(y),
        y_ = np.exp(y_)
    log1 = np.nan_to_num(np.array([np.log(v + 1) for v in y]))
    log2 = np.nan_to_num(np.array([np.log(v + 1) for v in y_]))
    calc = (log1 - log2) ** 2
    return np.sqrt(np.mean(calc))

#Linear Regrssion Model
from sklearn.linear_model import LinearRegression,Ridge,Lasso
from sklearn.model_selection import GridSearchCV
from sklearn import metrics
import warnings
pd.options.mode.chained_assignment = None
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Initialize logistic regression model
lModel = LinearRegression()

# Train the model
yLabelsLog = np.log1p(yLabels)
lModel.fit(X = dataTrain,y = yLabelsLog)





#___________________________________________


### pour concatener
X_ = Hitters.drop(['Salary', 'League', 'Division', 'NewLeague'], axis=1).astype('float64')
# Define the feature set X.
dummies = pd.get_dummies(Hitters[['League', 'Division', 'NewLeague']])
X = pd.concat([X_, dummies[['League_N', 'Division_W', 'NewLeague_N']]], axis=1)
X.info()