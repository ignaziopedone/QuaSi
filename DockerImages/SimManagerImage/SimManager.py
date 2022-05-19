from multiprocessing.dummy import Process
import os
import time
from urllib import response
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
import multiprocessing

app = Flask(__name__)

#Topology Parameters
networkTopology = nx.Graph()

connection = None
channel = None

#Connections To The Simulator
open_conns = dict()


def logging_consumer(logger_name,rabbit_host,rabbit_port):

    connection = connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbit_host, port=rabbit_port))
    rec_ch = connection.channel()

    queueResult = rec_ch.queue_declare(queue="manager")
    rec_name = queueResult.method.queue

    #Set up Logger to new file for simulation logs -- TO DO
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', handlers=[
    logging.FileHandler('simulations.log', mode="w"),
    logging.StreamHandler()
    ])

    cons_logger = logging.getLogger(logger_name)

    #Set up handler function of messages
    def message_handler(ch,method,properties,body):

        #We assume the messages flowing on the queue will have the following predefiend structure:
        #	[type string, source string, destination string, metedata map[string][object], msg object]

        res = pickle.loads(body)

        type = res[0]
        source = res[1]
        destination = res[2]
        metadata = res[3]
        msg = res[4]
        
        #Now depending on the type, role fields of the message we will evaluate what to do:
        nonlocal cons_logger
        #Analyze messages of communication start from manager
        if type == "info":
            cons_logger.info(f"in {str(source)} - ConID: {metadata['id_connection']} - SimID: {metadata['id_simulation']} - {str(msg)}")
        if type == "warning":
            cons_logger.warning(f"in {str(source)} - ConID: {metadata['id_connection']} - SimID: {metadata['id_simulation']} - {str(msg)}")
        if type == "error":
            cons_logger.error(f"in {str(source)} - ConID: {metadata['id_connection']} - SimID: {metadata['id_simulation']} - {str(msg)}")
        if type == "debug":
            cons_logger.debug(f"in {str(source)} - ConID: {metadata['id_connection']} - SimID: {metadata['id_simulation']} - {str(msg)}")
            
        #Done processing message, I can acknowledge it
        ch.basic_ack(delivery_tag=method.delivery_tag)

    #Consume Manager queue to log events into the file properly -- TO DO
    cons_logger.info(f'Starting to listen for messages on queue {rec_name}')
    rec_ch.basic_consume(on_message_callback=message_handler, queue=rec_name) #Manual acknowledgement on by default
    rec_ch.start_consuming()



def run(serverPort,rabbit_host,rabbit_port):
    global connection
    global channel

    connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbit_host, port=rabbit_port, heartbeat= 0))
    channel = connection.channel()
    app.run(host='0.0.0.0', port=serverPort)

    
def get_key(my_dict,val):
    for key, value in my_dict.items():
         if val == value:
             return key


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

    for node_index,connections in enumerate(adjacency_list):

        # Create sphincs keys for the node
        seed = os.urandom(sphincs.crypto_sign_SEEDBYTES)
        publicKey, privateKey = sphincs.generate_keypair(seed)

        #Send Keys to current node
        
        #Get proper name of the queue
        queue_name = "endpoint-" + str(node_index)
        app.logger.info(queue_name + " keys: " + str(privateKey) + "     " + str(publicKey))
        #Build the message
        mess = ["Keys",queue_name,queue_name,{},[privateKey,publicKey]]

        app.logger.info("Sending Keys to " + queue_name)

        # Ensuring the queue for the curernt node exists otherwise we create it
        channel.queue_declare(queue=queue_name,auto_delete=True)
        channel.basic_publish(exchange='',routing_key=queue_name,body=pickle.dumps(mess))

        #Distribute public key of the curetn node to the others connected to it
        for n in connections:
            index = nodes.index(n)

            destination = "endpoint-" + str(index)

            #Build the message
            mess = ["Keys",queue_name,destination,{},[{},publicKey]]

            # Ensuring the queue for the curernt node exists otherwise we create it
            channel.queue_declare(queue=queue_name,auto_delete=True)
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
            if index <= node_index:
                connections.remove(n)
        
    return topology

@app.route('/begin', methods=['POST'])
def begin():
    request_data = request.get_json()
    if request_data and "SRC"  in request_data.keys() and "DST" in request_data.keys():
        global open_conns
        if int(str(request_data["SRC"]).split("-")[1]) in range(len(networkTopology.nodes)) and int(str(request_data["DST"]).split("-")[1]) in range(len(networkTopology.nodes)):
            k = str(request_data["SRC"]) + "_" + str(request_data["DST"])
            if k in open_conns.keys(): 
                return Response(response=f"Connection already open for the specified endpoints with ID: {open_conns[k]}", status=200)
            conn_id = uuid.uuid4()
            open_conns[k] = conn_id
            return Response(response=f"Connection opened for the specified endpoints with ID: {open_conns[k]}", status=201)

    return Response(response=f"Wrong Parameters, Please specify source and destination endpoints for the connection {networkTopology.nodes}", status=400)

@app.route('/end', methods=['POST'])
def end():
    request_data = request.get_json()
    if request_data and "ID"  in request_data.keys():
        global open_conns
        conn_id = request_data["ID"] 
        if uuid.UUID(request_data["ID"]) in open_conns.values():
            key = get_key(open_conns,uuid.UUID(request_data["ID"]))
            del open_conns[key]
            return Response(response=f"Connection with ID: {conn_id} correctly closed", status=200)
        return Response(response=f"No Connection with ID: {conn_id} present", status=400)

    return Response(response=f"Wrong Parameters, Please specify source and destination endpoints for the connection", status=400)

@app.route('/startKeyExchange', methods=['POST'])
def startSimulation():
    #Proper data sent in the req body, use it to start a simulation with the received parameters on the endpoints indicated and on the specified communication channel
    
    #Setup the channel to write the start message on the source endpoint of the topology to rabbitMQ

    #Properly building the message with the predefined metadata needed for the simulation
    
    request_data = request.get_json()
    if request_data:
        global networkTopology
        global connection
        global channel
        global open_conns

        if "source" in request_data.keys() and "destination" in request_data.keys() and "com_channel" in request_data.keys():
            source = request_data["source"]
            destination = request_data["destination"]
            com_channel = request_data["com_channel"]
            k = str(source) + "_" + str(destination)
            #Check if requested simulation can happen given the curretn topology
            if checkSim(json_graph.adjacency_data(networkTopology),source,destination,com_channel) and k in open_conns.keys():
            
                if "protocol" in request_data.keys() and "key_length" in request_data.keys() and "chunk_size" in request_data.keys():
                    protocol = request_data["protocol"]
                    key_length = request_data["key_length"]
                    chunk_size = request_data["chunk_size"]
                    
                    #These can be dafaulted
                    chsh_threshold = request_data.get("chsh_threshold") or -2.7
                    authentication = request_data.get("authentication") or "sphincs"
                    interceptAndResend = request_data.get("interceptAndResend") or 0
                    manInTheMiddle = request_data.get("manInTheMiddle") or 0

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
                    conn_id = open_conns[k]
                    mess_id = uuid.uuid4()
                    metadata["id_connection"] = { "ID": conn_id, "SRC": source, "DST": destination }
                    metadata["id_message"] = mess_id
                    
                    #Prepare message
                    mess = ["Start",source,destination,metadata,{}]

                    #Creating queue if it doesn't exist
                    channel.queue_declare(queue=source,auto_delete=True)

                    if "key_number" in request_data.keys():
                        sims = request_data["key_number"]
                        while sims > 0:
                            if sims >= 8:
                                r = 8
                            else:
                                r = sims
                            for i in range(r):
                                sim_id = uuid.uuid4()
                                mess[3]["id_simulation"] = sim_id
                                mess[3]["requested_sims"] = request_data["key_number"]
                                channel.basic_publish(exchange='',routing_key=source,body=pickle.dumps(mess))
                            wait = int(mess[3]["key_length"]) * 8 / 4096
                            sims = sims - 8
                            time.sleep(wait)
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

        if check_Topology(request_data):
            networkTopology = json_graph.adjacency_graph(request_data)
            app.logger.info("Network Topology acquired correctly!")
            app.logger.info(networkTopology)

            #Create K8s YAML File for Topology deployment
            output = dict()
            output["apiVersion"] = 'qkdsim.s276624.qkdsim.dev/v1'
            output["kind"] = 'NetTopology'
            output["metadata"]= { "name": 'nettopology-sample' }
            
            data = json_graph.adjacency_data(networkTopology)
            # Clean repeated edges to avoid deploying duplicated com_channels
            #data = cleanRepeatedEdges(data)
            del data["directed"]
            del data["graph"]
            del data["multigraph"]
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
    if not nx.is_empty(networkTopology):
       # Distribute Keys for the endpoints
       createAndDistributeKeys(json_graph.adjacency_data(networkTopology))
       app.logger.info("Keys successfully distributed!")
       return Response(response="OK",status=200)

    app.logger.info("Keys NOT successfully distributed!")
    return Response(response=json.dumps({"currentTopology": json_graph.adjacency_data(networkTopology)}), status=400)

def main():
    fh = logging.FileHandler('manager.log',mode="w")
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    app.logger.addHandler(fh)
    app.logger.setLevel(logging.DEBUG)
    app.logger.info("Setting Up Rabbit Communication...")
    app.logger.info("Communication Set Up Done")
    # start server on parallel process
    app.logger.info('Starting Flask Server...')
    serverPort = int(os.environ.get("PORT",6000))
    # Run RabbitMQ Consumer
    app.logger.info('Starting Manager Consumer...')
    rabbit_host = os.environ.get("RABBIT_HOST","rabbitmq")
    rabbit_port = int(os.environ.get("RABBIT_PORT",5672))
    app.logger.info(f'{rabbit_host} {rabbit_port}')

    params = pika.ConnectionParameters(host=rabbit_host,port=rabbit_port)
    try:
        connection = pika.BlockingConnection(parameters=params)
        if connection.is_open:
            connection.close()
        #Start Manager Consumer And REST API
        pool = multiprocessing.Pool(2)
        rest = pool.apply_async(run,args=(serverPort,rabbit_host,rabbit_port))
        rmqcons = pool.apply_async(logging_consumer,args=("manager_logger",rabbit_host,rabbit_port))

        rmqcons.wait()

        pool.terminate()
        pool.close()
        app.logger.info('Correctly quit application')
    except Exception as e:
        raise e


if __name__ == "__main__":
    main()