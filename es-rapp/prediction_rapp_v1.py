#!/usr/bin/env python3
#SPDX-License-Identifier: Apache-2.0
#Copyright 2024 Intel Corporation

from flask import Flask,request
import json
app = Flask(__name__)
@app.route("/predict", methods=['POST'])
def predict():
    l = []
    req = json.loads(request.json)
    return ([str(sum(req)/len(req))])
       

app.run(host='0.0.0.0', port=9008)
