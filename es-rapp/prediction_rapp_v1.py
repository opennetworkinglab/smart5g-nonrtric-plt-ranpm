from flask import Flask,request
import json
app = Flask(__name__)
test_predict = []
@app.route("/predict")
def hello():
    return "100"

@app.route("/retrain", methods=['POST'])
def retrain():
    l = []
    req = json.loads(request.json)
    return ([str(sum(req)/len(req))])
       

app.run(host='0.0.0.0', port=9008)
"""
    df = pd.DataFrame(pd.read_csv("cell_337.csv"))
    df.columns = ['Load']
    df['Load'] = df['Load'].apply(np.ceil)
    n99 = df.Load.quantile(0.99)
    max1 = df.Load.max()
    for ind in df.index:
        df['Load'][ind] = ((df['Load'][ind]/max1) * n99)
    print (df)
    """ 
