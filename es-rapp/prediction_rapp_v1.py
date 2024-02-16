#!/usr/bin/env python3
#SPDX-License-Identifier: Apache-2.0
#Copyright 2024 Intel Corporation

from flask import Flask,request
import pandas as pd
import tensorflow as tf
import numpy as np
import json
from tensorflow import keras
from keras.models import Sequential
from keras.layers import Dense
from keras.callbacks import ModelCheckpoint, EarlyStopping
app = Flask(__name__)

model = None


@app.route("/predict", methods=['POST'])
def predict():
    
    l = []
    req = json.loads(request.json)
    print(req)
    le = len(req)
    l.append(req[le - 8:])
    Z = model.predict(np.array(l))
    print(str(Z[0][0]))
    return ([str(int(Z[0][0]))])

def convert2matrix(data_arr, look_back, full_data):
 X, Y =[], []
 
 for i in range(len(data_arr)-look_back):
  d=i+look_back
  xdata = data_arr[i:d]
  X.append(xdata)
  Y.append(data_arr[d])
 return np.array(X), np.array(Y)
 
def model_dnn(look_back):
    model = Sequential()
    model.add(Dense(units=32, input_dim=look_back, activation='relu'))
    model.add(Dense(look_back, activation='relu'))
    model.add(Dense(1))

    model.compile(loss= "mse",  optimizer='adam',metrics = ['mse', 'mae'])
    return model


df = pd.DataFrame(pd.read_csv("load_test.csv"))
train_size = 300
train, test = (df['Load'].tolist())[0:train_size], (df['Load'].tolist())[train_size:len(df.values)]
look_back = 8
print("--------------------------------------------")
trainX, trainY = convert2matrix(train, look_back, df[0:train_size])
testX, testY = convert2matrix(test, look_back, df[train_size:])
model = model_dnn(look_back)
print(trainX, trainY)
print(model)
model.fit(trainX,trainY, epochs=100, batch_size=10, verbose=1, validation_data=(testX,testY),callbacks=[EarlyStopping(monitor='val_loss', patience=10)],shuffle=False)


app.run(host='0.0.0.0', port=9008)