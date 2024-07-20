from flask import Flask,request,jsonify
import os
import requests
import threading
import helper as h
import time


self_Socket = os.getenv("SOCKET_ADDRESS")
socketAddress = []
failed = []
log = []

socket_threads = []

keys = {}
contexts = []
vectorClock = {}

app = Flask(__name__)

@app.route("/debug",methods = ["GET"])
def bug():
    data = request.json["data"]
    if data == "vector":
        return vectorClock,200
    if data == "log":
        return jsonify(logs=log),200

#--------------------------view--------------------------#
@app.route("/view",methods = ["PUT","GET","DELETE"])
def view():
    if request.method == "PUT":
        socketInfo = get_socket_data(request.json)
        return add_socket(socketInfo)

    if request.method == "DELETE":
        socketInfo = get_socket_data(request.json)
        return delete_socket(socketInfo)
    
    if request.method == "GET":
        return show_Socket()

@app.route("/view/startup",methods = ["PUT"])
def updating_new_node():
    global keys
    global context
    global vectorClock
    data = request.json
    keys = data["keys"]
    context = data['context']
    vectorClock = data["vector"]
    return jsonify(msg="up to date"),200

@app.route("/check",methods = ["GET"])
def ack():
    return jsonify(msg="ack"),200

@app.route("/view/reconnect", methods = ["PUT"])
def reconnect():
    data = request.json
    socketInfo = data["socket-address"]

    if socketInfo in socketAddress:
        return {"msg":"reconnected"},200
    return {"msg":"reconnected"},200

#---------------------function-------------------------#
def get_socket_data(data):
    if "socket-address" not in data:
        return None
    return data["socket-address"]

def add_socket(socketInfo):
    if socketInfo in socketAddress:
        return jsonify(result="already present"),200
    socketAddress.append(socketInfo)
    updateNewNode = threading.Thread(target=updating_node,args=(socketInfo,keys,contexts,vectorClock))
    updateNewNode.start()
    return jsonify(result="added"),200

def updating_node(socketInfo,keys,context,vector):
    while(True):
        try:
            requests.put(h.make_URL(socketInfo,"/view/startup"),json = {"keys":keys,"context":context,"vector":vector})
        except requests.exceptions.RequestException:
            continue
        break
    return

def delete_socket(socketInfo):
    #global log
    if socketInfo not in socketAddress:
        return jsonify(error="View has no such replica"),404
    #log.append("delete socket {}".format(socketInfo))
    socketAddress.remove(socketInfo)
    thread = threading.Thread(target=checking,args=(socketInfo,))
    thread.start()
    #log.append("starting pooling thread for checking {}".format(socketInfo))
    return jsonify(result="deleted"),200

def show_Socket():
    return jsonify(view = socketAddress),200

#-------------------------kvs---------------------------#
@app.route("/kvs/<key>",methods = ["PUT","GET","DELETE"])
def kvs(key):
    if request.method == "PUT":
        data = get_key_value(request.json)
        if len(key) > 50:
            return jsonify(error = "Key is too long"),400

        if data == None or data[0] == None:
            return jsonify(error = "PUT request does not specify a value"),400
        return write_data(key,data[1],"PUT",data[0])
    
    if request.method == "DELETE":
        metadata = get_meta(request.json)
        return write_data(key,metadata,"DELETE")
    
    if request.method == "GET":
        metadata = get_meta(request.json)
        if check_metadata(metadata) == False:
            return {"error":"Causal dependencies not satisfied; try again later"},503
        return get_key(key)
        
@app.route("/kvs/put", methods = ["PUT"])
def kvs_put():
    data = request.json
    key = data["key"]
    value = data["value"]
    context = data["context"]
    vector = data["vector"]
    socket = data["socket"]
    return replica_update(key,context,vector,socket,"p",value)

@app.route("/kvs/del",methods = ["DELETE"])
def kvs_del():
    data = request.json
    key = data["key"]
    context = data["context"]
    vector = data["vector"]
    socket = data["socket"]
    return replica_update(key,context,vector,socket,"d")

#---------------------function---------------------------#
def get_key_value(data):
    if "value" not in data or "causal-metadata" not in data:
        return None
    metadata = data["causal-metadata"]
    value = data["value"]
    if metadata == None:
        metadata = vectorClock.copy()
    return value,metadata

def get_meta(data):
    if "causal-metadata" not in data:
        return None
    metadata = data["causal-metadata"]
    if metadata == None:
        metadata = vectorClock.copy()
    return metadata

def check_metadata(metadata):
    for k in metadata.keys():
        if vectorClock[k] != metadata[k]:
            return False
    return True

def check_causal(metadata):
    for k in metadata.keys():
        if vectorClock[k] < metadata[k]:
            return False
    return True

def write_data(key,metadata,command,value = None):
    global log
    if check_metadata(metadata) == False:
        return {"error":"Causal dependencies not satisfied; try again later"},503
    if command == "PUT":
        return put_key(key,value)
    if command == "DELETE":
        log.append("deleting key")
        return delete_key(key)

def put_key(key,value):
    if key not in keys:
        keys[key] = value
        boardcast_put_key(key,value,contexts,vectorClock)
        contexts.append(("p",key,value,self_Socket))
        vectorClock[self_Socket] += 1

        return {"result":"created","causal-metadata":vectorClock},201
    
    keys[key] = value
    boardcast_put_key(key,value,contexts,vectorClock)
    contexts.append(("p",key,value,self_Socket))
    vectorClock[self_Socket] += 1
    return {"result":"replaced","causal-metadata":vectorClock},200

def delete_key(key):
    global log
    if key in keys:
        #log.append("key in keys")
        del keys[key]
        #log.append("deleted key")
        boardcast_delete_key(key,contexts,vectorClock)
        contexts.append(("d",key,None,self_Socket))
        vectorClock[self_Socket] += 1
        return {"result":"deleted","causal-metadata":vectorClock},200
    return {"error":"key does not exist"},404

def replica_update(key,context,vector,socket,op,val=None):
    global vectorClock
    contextsLength = len(contexts)
    if check_causal(vector) == False:
        count = 0
        for i in context:
            if count < contextsLength and contexts[count][0] == i[0] and contexts[count][1] == i[1] and contexts[count][2] == i[2] and contexts[count][3] == i[3]:
                count += 1
            else:
                if i[0] == 'p':
                    replica_put_key(i[1],i[2],i[3])
                    vectorClock[i[3]] += 1
                    count += 1
                if i[0] == "d":
                    replica_del_key(i[1],i[3])
                    vectorClock[i[3]] += 1
                    count += 1
    
    if op == "p":
        replica_put_key(key,val,socket)
        vectorClock[socket] += 1
    
    if op == "d":
        replica_del_key(key,socket)
        vectorClock[socket] += 1


    log.append("return")
    return jsonify(msg="updated"),200

def replica_put_key(key,value,socket):
    global contexts
    if key not in keys:
        keys[key] = value
        contexts.append(("p",key,value,socket))
        return

    keys[key] = value
    contexts.append(("p",key,value,socket))
    return

def replica_del_key(key,socket):
    if key in keys:
        del keys[key]
        contexts.append(("d",key,None,socket))

def get_key(key):
    if key in keys:
        return {"result":"found","value":keys[key],"causal-metadata":vectorClock},200
    return {"error":"Key does not exist"},404

#--------------------boardcast--------------------------#
def boardcast_new_node(socketInfo):
    threads = []
    for socket in socketAddress:
        threads.append(threading.Thread(target=new_node,args=(socket,socketInfo)))
        threads[-1].start()

    for t in threads:
        t.join()

def boardcast_put_key(key,value,context,vector):
    #global log
    for socket in socketAddress:
        if socket != self_Socket:
            try:
                requests.put(h.make_URL(socket,"/kvs/put"),json = {"key":key,"value":value,"context":context,"vector":vector,"socket":self_Socket},timeout=(1,None))
            except requests.exceptions.RequestException:
                failed.append(socket)

    boardcast_failed_socket()

def boardcast_delete_key(key,context,vector):
    for socket in socketAddress:
        if socket != self_Socket:
            try:
                requests.delete(h.make_URL(socket,"/kvs/del"),json = {"key":key,"context":context,"vector":vector,"socket":self_Socket},timeout=(1,None))
            except requests.exceptions.RequestException:
                failed.append(socket)
    boardcast_failed_socket()

def boardcast_failed_socket():
    #global log
    while len(failed) != 0:
        failedSocket = failed.pop()
        for socket in socketAddress:
            if (socket != failedSocket or socket not in failedSocket):
                try:
                    #log.append("send delete request to {}".format(socket))
                    requests.delete(h.make_URL(socket,"/view"),json = {"socket-address": failedSocket},timeout=(1,None))
                except requests.exceptions.RequestException:
                    continue

#--------------------boardcast multi-----------------#
def delete_view_request(socket,failedSocket):
    try:
        requests.delete(h.make_URL(socket,"/view"),json = {"socket-address": failedSocket})
    except requests.exceptions.RequestException:
        return

def new_node(socket,socketInfo):
    try:
        requests.put(h.make_URL(socket,"/view"),json = {"socket-address":socketInfo},timeout=(1.1,None))
    except requests.exceptions.RequestException:
        return

#-----------------pooling----------------------------#
def checking(failed_socket):
    global socketAddress
    #global log
    #log.append("called polling")
    while(True):
        try:
            log.append("pooling failed socket: {}".format(failed_socket))
            requests.put(h.make_URL(failed_socket,"/check"),timeout=(0.5,None))
        except requests.exceptions.RequestException:
            time.sleep(0.1)
            continue
        socketAddress.append(failed_socket)
        return

if __name__ == "__main__":
    View = os.getenv("VIEW")
    if View != None:
        socketAddress = View.split(",")
    for socket in socketAddress:
        vectorClock[socket] = 0
    boardcast_new_node(self_Socket)
    app.run(host = "0.0.0.0",port = "8090")