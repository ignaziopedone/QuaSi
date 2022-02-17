import os
from flask import Flask, request, Response, json
import logging
import networkx as nx
from networkx.readwrite import json_graph
import pika
import pyspx.shake256_128f as sphincs
import pickle
import uuid
from werkzeug.datastructures import Accept
import yaml

app = Flask(__name__)

#Topology Parameters
networkTopology = nx.Graph()
canDistribute = False

#RabbitMQ parameters
connection = None
channel = None
rabbit_host = None
rabbit_port = None

def run(serverPort):
    app.run(host='0.0.0.0', port=serverPort)

def setUpRabbit():
    global connection
    global channel
    global rabbit_host
    global rabbit_port

    rabbit_host = os.environ.get("RABBIT_HOST","rabbitmq")
    rabbit_port = int(os.environ.get("RABBIT_PORT",5672))

    app.logger.info(rabbit_host)
    app.logger.info(rabbit_port)

    #connection = pika.BlockingConnection(pika.URLParameters("http://192.168.2.18:5672"))
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbit_host, port=rabbit_port, heartbeat= 0))
    channel = connection.channel()

def check_Topology(topology):
    if "directed" in topology.keys() and isinstance(topology["directed"], bool):
        if "multigraph" in topology.keys() and isinstance(topology["multigraph"], bool):
            if "graph" in topology.keys() and isinstance(topology["graph"], list):
                if "nodes" in topology.keys() and isinstance(topology["nodes"], list) and len(topology["nodes"]) > 0:
                    if "adjacency" in topology.keys() and isinstance(topology["adjacency"], list) and len(topology["adjacency"]) > 0:
                        for a in topology["adjacency"]:
                            if not isinstance(a,list):
                                return False
                        return True
    
    return False

def createAndDistributeKeys(topology):

    global connection
    global channel

    adjacency_list = topology["adjacency"]
    nodes = topology["nodes"]

    app.logger.info(connection)
    app.logger.info(channel)

    for node_index,connections in enumerate(adjacency_list):

        # Create sphincs keys for the node
        seed = os.urandom(sphincs.crypto_sign_SEEDBYTES)
        publicKey, privateKey = sphincs.generate_keypair(seed)

        #Send Keys to current node
        
        #Get proper name of the queue
        queue_name = "endpoint-" + str(node_index)
        app.logger.info(queue_name + " keys: " + str(privateKey) + "     " + str(publicKey))
        #Build the message
        mess = ["Keys",queue_name,queue_name,"Forward",{},[privateKey,publicKey]]

        app.logger.info("Sending Keys to " + queue_name)

        # Ensuring the queue for the curernt node exists otherwise we create it
        channel.queue_declare(queue=queue_name,durable=True)
        channel.basic_publish(exchange='',routing_key=queue_name,body=pickle.dumps(mess))

        #Distribute public key of the curetn node to the others connected to it
        for n in connections:
            index = nodes.index(n)

            destination = "endpoint-" + str(index)

            #Build the message
            mess = ["Keys",queue_name,destination,"Forward",{},[{},publicKey]]

            # Ensuring the queue for the curernt node exists otherwise we create it
            channel.queue_declare(queue=queue_name,durable=True)
            channel.basic_publish(exchange='',routing_key=destination,body=pickle.dumps(mess))

def checkSim(topology,source,destination,com_chan):

    nodes = topology["nodes"]

    #Check we have proper names for the fields:
    if "endpoint-" in source and len(source) >= 10:
        s = 0
        for i in source[9:]:
            s += int(i) * 10**(len(source[9:]) - 1)

        if "endpoint-" in destination and len(destination) >= 10:
            d = 0
            for i in destination[9:]:
                d += int(i) * 10**(len(destination[9:]) - 1)

            m = max(s,d)
            n = min(s,d)
            app.logger.info(m)
            app.logger.info(n)
            if len(nodes) >= m + 1 and com_chan == ("cc" + str(n) + "-" + str(m)):
                return True
    
    return False

def cleanRepeatedEdges(topology):

    adjacency_list = topology["adjacency"]
    nodes = topology["nodes"]

    for node_index,connections in enumerate(adjacency_list):
        #Distribute public key of the curetn node to the others connected to it
        for n in connections:
            index = nodes.index(n)

            if index < node_index:
                connections.remove(n)
        
    return topology

@app.route('/startSimulation', methods=['POST'])
def startSimulation():

    #Proper data sent in the req body, use it to start a simulation with the received parameters on the endpoints indicated and on the specified communication channel
    
    #Setup the channel to write the start message on the source endpoint of the topology to rabbitMQ

    #Properly building the message with the predefined metadata needed for the simulation
    
    request_data = request.get_json()
    if request_data:
        global networkTopology
        global connection
        global channel

        app.logger.info(request_data)

        if "source" in request_data.keys() and "destination" in request_data.keys() and "com_channel" in request_data.keys():
            source = request_data["source"]
            destination = request_data["destination"]
            com_channel = request_data["com_channel"]
            
            #Check if requested simulation can happen given the curretn topology
            if checkSim(json_graph.adjacency_data(networkTopology),source,destination,com_channel):
                
                if "protocol" in request_data.keys() and "key_length" in request_data.keys() and "chunk_size" in request_data.keys():
                    protocol = request_data["protocol"]
                    key_length = request_data["key_length"]
                    chunk_size = request_data["chunk_size"]
                    
                    #These can be dafaulted
                    chsh_threshold = request_data.get("chsh_threshold") if False else -2.7
                    authentication = request_data.get("authentication") if False else "sphincs"
                    interceptAndResend = request_data.get("interceptAndResend") if False else 0
                    manInTheMiddle = request_data.get("manInTheMiddle") if False else 0

                    #Prepare metadata
                    metadata = dict()
                    metadata["protocol"] = protocol
                    metadata["key_length"] = key_length
                    metadata["chunk_size"] = chunk_size
                    metadata["chsh_threshold"] = chsh_threshold
                    metadata["authentication"] = authentication
                    metadata["com_channel"] = com_channel
                    metadata["interceptAndResend"] = interceptAndResend
                    metadata["manInTheMiddle"] = manInTheMiddle
                    metadata["com_channel"] = com_channel

                    #Generate UUID for new sim
                    conn_id = uuid.uuid4()
                    mess_id = uuid.uuid4()
                    metadata["id_connection"] = conn_id
                    metadata["id_message"] = mess_id
                    
                    #Prepare message
                    mess = ["Start",source,destination,"Forward",metadata,{}]

                    #Send message creating queue if it doesn't exist
                    channel.queue_declare(queue=source,durable=True)
                    channel.basic_publish(exchange='',routing_key=source,body=pickle.dumps(mess))

                    return Response(response=str(conn_id),status=200)
    
    return Response(response="Error while starting Simulation, check the parameters supplied",status=400)

@app.route('/getTopology', methods=['POST'])
def getAndDeployTopology():

    #Receive request body parsed from json dumped to python object
    request_data = request.get_json()
    app.logger.info(request_data)
    if request_data:
        #Basic Check of correct formatting of the received data

        global networkTopology
        global canDistribute

        if check_Topology(request_data):
            networkTopology = json_graph.adjacency_graph(request_data)
            canDistribute = True
            app.logger.info("Network Topology acquired correctly!")
            app.logger.info(networkTopology)

            #Create K8s YAML File for Topology deployment
            output = dict()
            output["apiVersion"] = 'qkdsim.s276624.qkdsim.dev/v1'
            output["kind"] = 'NetTopology'
            output["metadata"] = 'nettopology-sample'
            
            data = json_graph.adjacency_data(networkTopology)
            # Clean repeated edges to avoid deploying duplicated com_channels
            data = cleanRepeatedEdges(data)
            output["spec"] = data
            with open(r'./GeneratedNetTopology.yaml', 'w') as file:
                yaml.dump(output, file, allow_unicode=True)
            
            return Response(response= json.dumps(output),status=200)
        else:
            app.logger.info("Network Topology NOT acquired correctly!")
            return Response(response= "Bad Request", status=400)

    app.logger.info("Check Request Body Pls!")
    return Response(response= "Bad Request", status=400)

@app.route('/distributeKeys', methods=['POST'])
def distributeKeys():

    # If we have a network topology saved we can distribute keys to allow for later use of
    # sphincs authentication
    global networkTopology
    global canDistribute
    if not nx.is_empty(networkTopology) and canDistribute:
       canDistribute = False
       # Distribute Keys for the endpoints
       createAndDistributeKeys(json_graph.adjacency_data(networkTopology))
       app.logger.info("Keys successfully distributed!")
       return Response(response="OK",status=200)

    app.logger.info("Keys NOT successfully distributed!")
    return Response(response=json.dumps({"currentTopology": json_graph.adjacency_data(networkTopology), "flag": canDistribute}), status=400)


def main():
    fh = logging.FileHandler('manager.log',mode="w")
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    app.logger.addHandler(fh)
    app.logger.setLevel(logging.DEBUG)
    app.logger.info("Setting Up Rabbit Communication...")
    setUpRabbit()
    app.logger.info("Communication Set Up Done")
    # start server
    app.logger.info('Starting Flask Server...')
    serverPort = int(os.environ.get("PORT",6000))
    run(serverPort)

    app.logger.info('Correctly quit application')


if __name__ == "__main__":
    main()