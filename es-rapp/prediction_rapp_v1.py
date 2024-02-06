from flask import Flask,request
import json
app = Flask(__name__)
@app.route("/predict", methods=['POST'])
def predict():
    l = []
    req = json.loads(request.json)
    return ([str(sum(req)/len(req))])
       

app.run(host='0.0.0.0', port=9008)
