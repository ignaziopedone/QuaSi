# importing Qiskit
import multiprocessing
from unittest import result
from qiskit import QuantumCircuit, ClassicalRegister, QuantumRegister, execute, BasicAer
from qiskit.quantum_info import Statevector

# import utility modules
import math
import numpy as np
import pickle
import logging
import pyspx.shake256_128f as sphincs
#from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from trng import randomStringGen
import time
import time


#RabbitMQ management library
import pika
import uuid
import os
import logging


# utility function - timeout parameter is expressed in milliseconds
# convert epoch time to milliseconds
current_time = lambda: int(round(time.time() * 1000))

# convert the array of bits into an array of bytes as per QKD specifications (bit 0 is the first bit of the octect - ETSI GS QKD 004 v1.1.1 (2010-12), page 9, table 1)
def convertToBytes(key, key_length):
	# convert list of bit in list of bytes
	byteskey = []
	for octect in range(int(key_length/8)):
		i = 7
		num = 0
		for bit in key[(8*octect):(8*(octect+1))]:
			num = (int(bit) << i) | num
			i = i - 1
		byteskey.append(num)
	# convert list to bytearray
	byteskey = bytearray(byteskey)
	return byteskey

# MODULE INTERFACE

class BB84_Parameters:
	#Used both for receiver or source
	alice_table = np.array([])
	alice_key = ''
	#Used only for receiver
	temp_alice_key = ''
	#Used only for source
	picked = []
	verifyingKey = []
	start_sim = None
	start = time.time()
	includingVerifyLen = None
	qber = None
	return_flag = False

class Active_Connection:
	mess_id = None
	source = ""
	destination = ""
	params = None
	direction = ""

class Simulator():

    #a dict for each connection/simulation
    active_connections = dict()
    rec_channel = None
    send_channel = None
    me = ""
    authN_data = dict()
    l_acon = None
    l_authN = None
    

    def __init__(self,rhost,rport,me,acon,authN_data,l_acon,l_authN):
        
        #RabbtiMQ Set Up
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=rhost,port=rport))
        self.rec_channel = self.connection.channel()
        self.send_channel = self.connection.channel()

        #Setup Endpoint
        self.me = me
        self.active_connections = acon
        self.authN_data = authN_data
        self.l_acon = l_acon
        self.l_authN = l_authN
        
        return

    # RECEIVER SIMULATION FUNCTIONS

    def getQuantumKey_R(self,qubits,key_length,alice_key,alice_table,temp_alice_key):

        # new key requested - reset all variables
        alice_table = np.array([])
        alice_key = []
        temp_alice_key = ''
        logging.info('New key exchange requested from client. Desired key length %s' % str(key_length))
        
        qubits_vectors = qubits
        chunk = qubits_vectors[0].num_qubits


        for i in range(len(qubits_vectors)):
            # generate a quantum circuit random basis for measurements, Do Mesurements on received qubits
            qr = QuantumRegister(chunk, name='qr')
            cr = ClassicalRegister(chunk, name='cr')
            circuit = QuantumCircuit(qr, cr, name='qcircuit')

            basisChoice = randomStringGen(chunk)
            # randomly chose basis for measurement
            table = np.array([])
            for index, bit in enumerate(basisChoice): 
                if 0.5 < int(bit):
                    circuit.h(qr[index])
                    table = np.append(table, 'X')
                else:
                    table = np.append(table, 'Z')

            # Reverse table
            table = table[::-1]
            alice_table = np.append(alice_table, table)
            qubits = qubits_vectors[i].evolve(circuit)
            # Measure statevector
            meas = qubits.measure()
            temp_alice_key += meas[0]

        return alice_key,alice_table,temp_alice_key,"OK"

    def compareBasis_R(self,table,signature,alice_key,alice_table,temp_alice_key,metadata,destination):

        bob_table = table
        tableSign = signature

        authenticationMethod = metadata["authentication"]

        if authenticationMethod == "sphincs":
            # check that table was actually sent from Bob
            if not sphincs.verify(bob_table.tobytes(), tableSign, self.authN_data[destination]):
                logging.error("Table comparison failed due to wrong signature!")
                return "Unauthorized", 401

        keep = []
        discard = []
        for qubit, basis in enumerate(zip(bob_table, alice_table)):
            if basis[0] == basis[1]:
                #print("Same choice for qubit: {}, basis: {}" .format(qubit, basis[0])) 
                keep.append(qubit)
            else:
                #print("Different choice for qubit: {}, Alice has {}, Bob has {}" .format(qubit, basis[0], basis[1]))
                discard.append(qubit)

        #print('Percentage of qubits to be discarded according to table comparison: ', len(keep)/chunk)

        # get new key
        alice_key += [temp_alice_key[qubit] for qubit in keep]

        #Defaulting to sphincs
        if authenticationMethod == "sphincs":
            # prepare reply
            reply = alice_table
            # sign reply to let Bob trust us
            repSign = sphincs.sign(alice_table.tobytes(), self.authN_data["privateKey"])
            # reset alice_table for next comparisons
            alice_table = np.array([])
        if authenticationMethod == "none":
            # prepare reply
            reply = alice_table
            # sign reply to let Bob trust us
            repSign = None
            # reset alice_table for next comparisons
            alice_table = np.array([])


        return alice_key,alice_table,temp_alice_key,[reply, repSign]

    def verifyKey_R(self,bobKey,keySign,picked,pickedSign,alice_key,metadata,destination):

        logging.info(f"INSIDE VERIFY KEY R: {bobKey} {keySign} {picked} {pickedSign} {alice_key} {metadata} {destination}")

        # key exchange completed
        # verify key
        bobKey = bobKey
        keySign = keySign
        picked = picked
        pickSign = pickedSign
        key_length = metadata["key_length"]
        logging.info("VERIFY KEY R BEFORE AUTHN CHECK")
        # check that message actually comes from Bob
        if metadata["authentication"] == "sphincs":
            if not sphincs.verify(bytes(bobKey), keySign, self.authN_data[destination]):
                logging.error("Key verification failed due to wrong signature!")
                return "Unauthorized", 401
            if not sphincs.verify(picked.tobytes(), pickSign, self.authN_data[destination]):
                logging.error("Key verification failed due to wrong signature!")
                return "Unauthorized", 401
            logging.info("VERIFY KEY R AFTER AUTHN CHECK")
        
        # get part of the key to be used during key verification
        verifyingKey = []
        logging.info("VERIFY KEY R AFTER ZERO STEP")
        # add picked bit to verifyingKey and remove them from the key
        for i in sorted(picked, reverse=True):
            verifyingKey.append(int(alice_key[i]))
            del alice_key[i]

        logging.info("VERIFY KEY R AFTER FIRST STEP")

        # make sure key length is exactly equals to key_length
        alice_key = alice_key[:key_length]
        logging.info("VERIFY KEY R AFTER SECOND STEP")
        # check that Alice and Bob have the same key
        acc = 0
        for bit in zip(verifyingKey, bobKey):
            if bit[0] == bit[1]:
                acc += 1
        logging.info("VERIFY KEY R AFTER THIRD STEP")
        logging.info('\nPercentage of similarity between the keys: %s' % str(acc/len(verifyingKey)))

        if (acc//len(verifyingKey) == 1):
            verified = True
            logging.info("\nKey exchange has been successfull")
        else:
            verified = False
            logging.error("\nKey exchange has been tampered! Check for eavesdropper or try again")

        #default to sphincs
        # prepare our reply - sign this key part
        if metadata["authentication"] == "sphincs":
            keySignature = sphincs.sign(bytes(verifyingKey), self.authN_data["privateKey"])
        if metadata["authentication"] == "none":
            keySignature = None

        return alice_key, [verifyingKey, keySignature]

    # SOURCE SIMALTION FUNCTIONS

    # generateQubits
    # generates a random string and encodes it in a statevector
    # @return: the statevector, the basis table used to measure the qubits and the measurement results
    def generateQubits(self,chunk):
        # Creating registers with n qubits
        qr = QuantumRegister(chunk, name='qr')
        cr = ClassicalRegister(chunk, name='cr')

        # Quantum circuit for alice state
        alice = QuantumCircuit(qr, cr, name='Alice')

        # Generate a random number in the range of available qubits [0,65536))
        temp_alice_key = randomStringGen(chunk)
        #logging.info("key: ", temp_alice_key)

            
        # Switch randomly about half qubits to diagonal basis
        alice_table = np.array([])
        for index in range(len(qr)):
            if 0.5 < int(randomStringGen(1)):
                # change to diagonal basis
                alice.h(qr[index])
                alice_table = np.append(alice_table, 'X')
            else:
                # stay in computational basis
                alice_table = np.append(alice_table, 'Z')

        # Reverse basis table
        alice_table = alice_table[::-1]

        # Generate a statevector initialised with the random generated string
        sve = Statevector.from_label(temp_alice_key)
        # Evolve stetavector in generated circuit
        qubits = sve.evolve(alice)

        # return quantum circuit, basis table and temporary key
        return qubits, alice_table, temp_alice_key

    def initSimParameters(self,params,key_length,chunk):
        # delay the start of the exchange of a random number of seconds (between 0 and 8)
        randNo = randomStringGen(3)
        # convert bit string into bytes
        randNo = int(randNo, 2)
        time.sleep(randNo)

        logging.info('Starting key exchange. Desired key length: %s' % str(key_length))
        # 1/3 of the key needs to be exchanged in order to verify key
        # that part of the key cannot be used anymore after key verification
        # generate 1/3 more than key_length that will then be exchanged
        # in this way final key length will be as equals as key_length
        key_length = int(key_length)
        params.start_sim = time.time()
        params.includingVerifyLen = round(key_length + (key_length / 3))
        # add a 15% of the total length
        generateLength = params.includingVerifyLen + round(params.includingVerifyLen * 15 / 100)
        # multiply generatedLength by two since qubits will be discarded with a probability of 50%
        generateLength = generateLength * 2

        # start a new key exchange
        # generate state vectors

        #Initializing parameters
        params.picked = []
        params.verifyingKey = []
        params.qber=None
        params.return_flag = False
        params.alice_table = np.array([])
        params.alice_key = ''

        qubit_vectors = []
        params.start = time.time()
        for i in range(math.ceil(generateLength/chunk)):
            qubits, alice_table_part, temp_alice_key = self.generateQubits(chunk)
            qubit_vectors.append(qubits)
            params.alice_table = np.append(params.alice_table, alice_table_part)
            params.alice_key = params.alice_key + temp_alice_key
        end = time.time()
        logging.info("Qubits generation time: " + str(end - params.start))
        logging.info("Alice_key is " + str(len(params.alice_key)))


        # Preparation phase ended, send quantum bits
        logging.info("Preparation phase ended, sending qubits...")
        params.start = time.time()

        return params, qubit_vectors

    def checkResponseAndSendBasis(self,response,params,auth):
        aliceSign = None
        if response == "OK":
            logging.info("Alice_key is " + str(len(params.alice_key)))
            
            # default to sphincs
            if auth == "sphincs":
                # sign alice_table before sending it
                params.start = time.time()
                aliceSign = sphincs.sign(params.alice_table.tobytes(), self.authN_data["privateKey"])
                end = time.time()
                logging.info("sphincs+ signature time: " + str(end - params.start))
            # compare basis table
            params.start = time.time()

            return True, params, aliceSign

        return False, params, aliceSign

    def compareBasisAndPrepareForKeyVer(self,msg,authenticationMethod,destination,params,key_length,chunk):
        #Decode message received
        rep = msg
        bob_table = rep[0]
        tableSign = rep[1]

        # check that table was actually sent from Bob
        if authenticationMethod == "sphincs":
            params.start = time.time()
            if not sphincs.verify(bob_table.tobytes(), tableSign, self.authN_data[destination]):
                logging.error("Table comparison failed due to wrong signature!")
                return None, False, 0
            end = time.time()
            logging.info("sphincs+ verify time: " + str(end - params.start))

        keep = []
        discard = []
        for qubit, basis in enumerate(zip(params.alice_table, bob_table)):
            if basis[0] == basis[1]:
                #print("Same choice for qubit: {}, basis: {}" .format(qubit, basis[0]))
                keep.append(qubit)
            else:
                #print("Different choice for qubit: {}, Alice has {}, Bob has {}" .format(qubit, basis[0], basis[1]))
                discard.append(qubit)

        logging.info('Percentage of qubits to be discarded according to table comparison: ' + str(len(keep)/chunk))


        params.alice_key = [params.alice_key[qubit] for qubit in keep]
        logging.info("Next Instruction pls")

        # randomly select bit to be used for key verification
        
        i = 0
        # we need to generate a random number between 0 and includingVerifyLen
        # randomStringGen generates a string of bit - calculate how many bit we need to get a consistent top value
        bits = 0
        temp = params.includingVerifyLen
        while temp > 0:
            temp = temp >> 1
            bits += 1
        while i < params.includingVerifyLen - key_length:
            # generate a valid random number (in range 0 - key_length + includingVerifyLen and not already used)
            while True:
                randNo = randomStringGen(bits)
                # convert bit string into bytes
                randNo = int(randNo, 2)
                if randNo >= params.includingVerifyLen:
                    # not a valid number
                    continue
                if randNo in params.picked:
                    # number already used
                    continue
                # number is valid - exit from this inner loop
                break
            # add randNo to list of picked
            #logging.info("It crashes where we think it does!!")
            params.picked.append(randNo)
            i += 1

        # remove used bits from the key
        for i in sorted(params.picked, reverse=True):
            params.verifyingKey.append(int(params.alice_key[i]))
            del params.alice_key[i]

        # make sure key length is exactly equals to key_length
        params.alice_key = params.alice_key[:key_length]

        logging.info("key len: %s" % str(len(params.alice_key)))

        
        # sign data with our private key
        params.picked = np.array(params.picked)
        if authenticationMethod == "sphincs":
            keySign = sphincs.sign(bytes(params.verifyingKey), self.authN_data["privateKey"])
            pickSign = sphincs.sign(params.picked.tobytes(), self.authN_data["privateKey"])
        if authenticationMethod == "none":
            keySign = None
            pickSign = None

        return params, keySign, pickSign

    def verifyAndSetSimResults(self,msg,authenticationMethod,destination,params):
        #Decode message
        rep = msg
        # get Bob's reply
        bobKey = rep[0]
        bobKeySign = rep[1]
        end = None

        logging.info("verifyingKey is: " + str(len(params.verifyingKey)))

        # verify Bob's signature
        if authenticationMethod == "sphincs":
            if not sphincs.verify(bytes(bobKey), bobKeySign, self.authN_data[destination]):
                logging.error("Key verification failed due to wrong signature!")
                #stop consuming and set variables to return
                #receive_channel.stop_consuming()
                params.return_flag = False

        # check that Alice and Bob have the same key
        acc = 0
        for bit in zip(params.verifyingKey, bobKey):
            if bit[0] == bit[1]:
                acc += 1

        logging.info("Acc is: " + str(acc))
        logging.info('\nPercentage of similarity between the keys: %s' % str(acc/len(params.verifyingKey)))
        params.qber = 1 - (acc/len(params.verifyingKey))
        logging.info("Qber is: " + str(params.qber))

        if (acc//len(params.verifyingKey) == 1):
            logging.info("\nKey exchange has been successfull")
            params.return_flag = True
            #ch.stop_consuming()
        else:
            logging.error("\nKey exchange has been tampered! Check for eavesdropper or try again")
            params.return_flag = False
            #ch.stop_consuming()
        
        return params

    # MESSAGE TYPE DISPATCHER

    def type_switcher(self,argument):
        logging.info("Argument is " + str(argument))
        switcher = {
            "Keys": self.set_Sphincs_Keys,
            "Start": self.startSim,
            "sendRegister": self.sendRegister_H,
            "compareBasis": self.compareBasis_H,
            "verifyKey": self.verifyKey_H,
        }

        return switcher.get(argument,"Invalid Mssage Type Received")

    # MESSAGE TYPE HANDLERS

    # CLASSICAL CHANNEL AUTHENTICATION METHOD HANDLING FUNCTIONS
    # SPHINCS+
    def set_Sphincs_Keys(self,source,destination,metadata,msg):
        if source == destination:
            #setting my own keys
            self.l_authN.acquire()
            self.authN_data["privateKey"] = msg[0]
            self.authN_data[destination] = msg[1]
            self.l_authN.release()
        else:
            # we only set up other reachable peers public keys we will need for authentication
            self.l_authN.acquire()
            self.authN_data[source] = msg[1]
            self.l_authN.release()

    def startSim(self,source,destination,metadata,msg):

        #Set up a new simulation involving this endpoint:

        #Generate a new sim ids per simulation uuid4:
        conn_id = metadata["id_connection"]["ID"]
        sim_id = metadata["id_simulation"]

        #Initialize some fields:
        active_con = Active_Connection()

        mess_id = uuid.uuid4()
        active_con.mess_id = mess_id

        active_con.source = source
        active_con.destination = destination

        
        #Before initializing parameters of the active_con we must check what protocol we will be simulating:

        if(metadata["protocol"] == "bb84"):					
            params = BB84_Parameters()
            key_length = metadata["key_length"]
            chunk = metadata["chunk_size"]
            
            
            params, qubit_vectors = self.initSimParameters(params,key_length,chunk)
            #Save updated simulation parameters
            active_con.params = params
            
            #Building message to send:
            meta = metadata
            meta["id_message"] = active_con.mess_id 
            #To fill in with what we need, it will have for sure the newly cretaed com chan to send messages inside and the index of the right com parameters
            mess = ["sendRegister",source,destination,meta,qubit_vectors]

            #Save all changes to the parameters and rest:
            sim = dict()
            sim[sim_id] = active_con

            self.l_acon.acquire()
            if conn_id in self.active_connections.keys():
                internal_dict = self.active_connections[conn_id]
                internal_dict.update(sim)
                self.active_connections[conn_id] = internal_dict
            elif conn_id not in self.active_connections.keys() or not self.active_connections[conn_id]:
                sim["start_time"] = time.time()
                self.active_connections[conn_id] = sim
                
            logging.info(f"Active Connections: {self.active_connections}")
            self.l_acon.release()
            
            com_chan = self.send_channel
            queueResult = com_chan.queue_declare(queue=metadata["com_channel"],auto_delete=True)
            com_name = queueResult.method.queue

            #Sending messages on the appropriate communication channel:
            com_chan.basic_publish(exchange='',routing_key=metadata["com_channel"],body=pickle.dumps(mess))

    def sendRegister_H(self,source,destination,metadata,msg):
        
        logging.info("Entering sendRegister handling function")

        #Check Parameters
        sim_id = metadata["id_simulation"]
        conn_id = metadata["id_connection"]["ID"]

        #Health Check
        #Check if me is in eitehr source or destination field of the message
        #call helath check func to implement

        #If Health Check Passed
        if  self.me == metadata["id_connection"]["SRC"]:
            # I am Source
            
            #Get params of the specified connection and simulation
            self.l_acon.acquire()
            active_con = self.active_connections[conn_id][sim_id]
            self.l_acon.release()
            params = active_con.params

            if(metadata["protocol"] == "bb84"):
                
                end = time.time()
                logging.info("/sendRegister time: " + str(end - params.start))

                ok, params, aliceSign = self.checkResponseAndSendBasis(msg,params,metadata["authentication"])

                if ok:
                    #Building message to send:
                    meta = metadata
                    mess_id = uuid.uuid4()
                    meta["id_message"] = mess_id
                    mess = ["compareBasis",destination,source,meta,[params.alice_table, aliceSign]]

                    #Save all changes to the parameters and rest:
                    active_con.params = params
                    active_con.mess_id = mess_id

                    self.l_acon.acquire()
                    internal_dict = self.active_connections[conn_id]
                    internal_dict[sim_id] = active_con
                    self.active_connections[conn_id]= internal_dict
                    self.l_acon.release()
                    
                    #Retrieve com_channel to use for communication:
                    com_chan = self.send_channel

                    #Send appropriate classical data towards Bob
                    com_chan.basic_publish(exchange='',routing_key=meta["com_channel"],body=pickle.dumps(mess))

        elif self.me == metadata["id_connection"]["DST"]:
            # I am Receiver

            logging.info("Behaving like receiver of the communication")

            active_con = Active_Connection()

            active_con.mess_id = uuid.uuid4()
            active_con.destination = destination
            active_con.source = source
            

            if(metadata["protocol"] == "bb84"):

                #First Message Received if I am a Receiver for BB84 Simulation
                active_con.params = BB84_Parameters()
                params = active_con.params

                key_length = metadata["key_length"]

                params.alice_key, params.alice_table, params.temp_alice_key,res = self.getQuantumKey_R(msg,key_length,params.alice_key,params.alice_table,params.temp_alice_key)

                #Save all changes to the parameters and rest:
                active_con.params = params
                active_con.mess_id = uuid.uuid4()
                sim = dict()
                sim[sim_id] = active_con

                self.l_acon.acquire()
                if  conn_id in self.active_connections.keys():
                    internal_dict = self.active_connections[conn_id]
                    internal_dict.update(sim)
                    self.active_connections[conn_id] = internal_dict
                else:
                    sim["start_time"] = time.time()
                    self.active_connections[conn_id] = sim
                self.l_acon.release()
                
                #Retrieve com_channel to use for communication:
                com_chan = self.send_channel
                queueResult = com_chan.queue_declare(queue=metadata["com_channel"],auto_delete=True)
                com_name = queueResult.method.queue

                #Building mesage to send:
                meta = metadata
                meta["id_message"] = active_con.mess_id
                mess = ["sendRegister",destination,source,meta,res]

                #Sending answer to Eve
                com_chan.basic_publish(exchange='',routing_key=metadata["com_channel"],body=pickle.dumps(mess))

        return

    def compareBasis_H(self,source,destination,metadata,msg):

        #Check Parameters
        sim_id = metadata["id_simulation"]
        conn_id = metadata["id_connection"]["ID"]

        self.l_acon.acquire()
        active_con = self.active_connections[conn_id][sim_id]
        self.l_acon.release()
        logging.info(f"Prameters are: {active_con}")
        logging.info(f"Active Connections: {self.active_connections}")
        active_con.mess_id = uuid.uuid4()
        
        #Get params of the specified connection
        params = active_con.params

        if self.me == metadata["id_connection"]["SRC"]:
            # I am Source

            if(metadata["protocol"] == "bb84"):
                
                key_length = metadata["key_length"]
                chunk = metadata["chunk_size"]

                #CompareBasis Finished
                end = time.time()
                logging.info("/compareBasis time: " + str(end - params.start))

                params, keySign, pickSign = self.compareBasisAndPrepareForKeyVer(msg,metadata["authentication"],metadata["id_connection"]["DST"],params,key_length,chunk)

                #Build message to be sent:
                meta = metadata #add com channel inside for sure
                meta["id_message"] = active_con.mess_id
                mess = ["verifyKey",destination,source,meta,[params.verifyingKey,keySign,params.picked,pickSign]]

                #Save all changes to the parameters and rest:
                active_con.params = params

                self.l_acon.acquire()
                internal_dict = self.active_connections[conn_id]
                internal_dict[sim_id] = active_con
                self.active_connections[conn_id]= internal_dict
                self.l_acon.release()

                #Retrieve com_channel to use for communication:
                com_chan = self.send_channel
                com_chan.basic_publish(exchange='',routing_key=meta["com_channel"],body=pickle.dumps(mess))

        elif self.me == metadata["id_connection"]["DST"]:

            #I am Receiver

            if metadata["protocol"] == "bb84":

                params.alice_key,params.alice_table,params.temp_alice_key,rep = self.compareBasis_R(msg[0],msg[1],params.alice_key,params.alice_table,params.temp_alice_key,metadata,metadata["id_connection"]["SRC"])


                #Building message to send:
                meta = metadata
                meta["id_message"] = active_con.mess_id
                mess = ["compareBasis",destination,source,meta,rep]

                #Save all changes to the parameters and rest:
                active_con.params = params

                self.l_acon.acquire()
                internal_dict = self.active_connections[conn_id]
                internal_dict[sim_id] = active_con
                self.active_connections[conn_id]= internal_dict
                self.l_acon.release()

                #Retrieve com_channel to use for communication:
                com_chan = self.send_channel
                com_chan.basic_publish(exchange='',routing_key=metadata["com_channel"],body=pickle.dumps(mess))
        
        return

    def verifyKey_H(self,source,destination,metadata,msg):
        #Check Parameters
        sim_id = metadata["id_simulation"]
        conn_id = metadata["id_connection"]["ID"]
        logging.info(f"Simulation ID: {sim_id}")
        logging.info(f"1st dict: {self.active_connections}")
        logging.info(f"2nd dict: {self.active_connections[conn_id][sim_id]}")

        self.l_acon.acquire()
        active_con = self.active_connections[conn_id][sim_id]
        start_time = self.active_connections[conn_id]["start_time"]
        self.l_acon.release()

        active_con.mess_id = uuid.uuid4()
        
        #Get params of the specified connection
        params = active_con.params

        if self.me == metadata["id_connection"]["SRC"]:
            # I am Source

            if metadata["protocol"] == "bb84":
                
                params = self.verifyAndSetSimResults(msg,metadata["authentication"],metadata["id_connection"]["DST"],params)
                end = time.time()

                #Save all changes to the parameters and rest:
                active_con.params = params

                self.l_acon.acquire()
                internal_dict = self.active_connections[conn_id]
                internal_dict[sim_id] = active_con
                self.active_connections[conn_id]= internal_dict
                self.l_acon.release()

                #PROPERLY HANDLE RETURN OF THE RESULTS TO THE USER USING RABBITMQ
                logging.info("Return values:  " + repr([(end-start_time),params.return_flag, params.qber]))
                mess = ["Result",destination,source,metadata,[params.alice_key,(end-start_time),params.return_flag, params.qber]]
                res_ch = self.send_channel
                ress_queue = res_ch.queue_declare(queue=str(metadata["id_connection"]["ID"]),durable=True,auto_delete=True)
                resr_queue = res_ch.queue_declare(queue=str(metadata["id_connection"]["ID"])+"-R",durable=True,auto_delete=True)
                res_ch.basic_publish(exchange='',routing_key=str(metadata["id_connection"]["ID"]),body=pickle.dumps(mess))
                res_ch.basic_publish(exchange='',routing_key=str(metadata["id_connection"]["ID"])+"-R",body=pickle.dumps(mess))
                #Clean data structure for the current sim
                self.l_acon.acquire()
                internal_dict = self.active_connections[conn_id]
                del internal_dict[sim_id]
                if len(internal_dict) == 1: # last simulation ending + start time parameter remained as only entry
                    del self.active_connections[conn_id]
                else:
                    self.active_connections[conn_id]= internal_dict
                self.l_acon.release()

        elif self.me == metadata["id_connection"]["DST"]:

            #I am Receiver

            if metadata["protocol"] == "bb84":

                params.alice_key, res = self.verifyKey_R(msg[0],msg[1],msg[2],msg[3],params.alice_key,metadata,metadata["id_connection"]["SRC"])
                logging.info("VERIFY KEY H AFTER VERIFY KEY R")
                #Build message to send:
                meta = metadata # remember to add the com channel in
                meta["id_message"] = active_con.mess_id
                mess = ["verifyKey",destination,source,meta,res]

                #Save all changes to the parameters and rest:
                active_con.params = params
                logging.info("VERIFY KEY H SETTING SHARED PARAMETERS")
                self.l_acon.acquire()
                internal_dict = self.active_connections[conn_id]
                internal_dict[sim_id] = active_con
                self.active_connections[conn_id]= internal_dict
                self.l_acon.release()

                #Retrieve com_channel to use for communication:
                com_chan = self.send_channel
                com_chan.basic_publish(exchange='',routing_key=metadata["com_channel"],body=pickle.dumps(mess))
                #Clean data structure for the current sim
                self.l_acon.acquire()
                internal_dict = self.active_connections[conn_id]
                del internal_dict[sim_id]
                if len(internal_dict) == 1: # last simulation ending + start time parameter remained as only entry
                    del self.active_connections[conn_id]
                else:
                    self.active_connections[conn_id]= internal_dict
                self.l_acon.release()
                #receive_channel.stop_consuming()
        
        return		

    def startListening(self):

        #Indipendently of me acting as Alice or Bob i set up myself as a consumer of my queue

        #Set up the channel to listen to message on my queue
        rec_ch = self.rec_channel

        #Set up my queue in case it doesn't exist
        queueResult = rec_ch.queue_declare(queue=self.me,auto_delete=True)
        rec_name = queueResult.method.queue

        #Message Handler Function, where all the magic is gonna happen

        def message_handler(ch,method,properties,body):

            #We assume the messages flowing on the queue will have the following predefiend structure:
            #	[type string, source string, destination string, metedata map[string][object], msg object]

            res = pickle.loads(body)

            type = res[0]
            source = res[1]
            destination = res[2]
            metadata = res[3]
            msg = res[4]
            
            logging.info("Received message: Type-> " + str(type) + "  S-> " + str(source) + "  D-> " + str(destination))
            #Check if i have keys for authentication required
            #if self.me == source and type != "Keys":
                #if metadata["authentication"] != "none" and (self.authN_data["privateKey"] == None or destination not in self.authN_data.keys()):
                    #mess = ["Keys",source,destination,metadata,msg]
                    #self.send_channel.basic_publish(exchange='',routing_key="manager",body=pickle.dumps(mess))
                    #ch.basic_ack(delivery_tag=method.delivery_tag)
                    #return
            #elif self.me == destination and type != "Keys":
                #if metadata["authentication"] != "none" and (self.authN_data["privateKey"] == None or source not in self.authN_data.keys()):
                    #mess = ["Keys",source,destination,metadata,msg]
                    #self.send_channel.basic_publish(exchange='',routing_key="manager",body=pickle.dumps(mess))
                    #ch.basic_ack(delivery_tag=method.delivery_tag)
                    #return
            #Now depending on the type, role fields of the message we will evaluate what to do:

            #Analyze messages of communication start from manager
            handler = self.type_switcher(type)
            handler(source,destination,metadata,msg)
            #Done processing message, I can acknowledge it
            ch.basic_ack(delivery_tag=method.delivery_tag)
                                        

        #Starting to consume messages
        logging.info('Starting to listen for messages on queue ' + str(self.me))
        rec_ch.basic_consume(on_message_callback=message_handler, queue=rec_name) #Manual acknowledgement on by default
        rec_ch.start_consuming()

        return

#Wrapper Function For Set Up Of Each Process
def RMQ_Consumer(rhost,rport,me,a_con,authN_data,l_acon,l_authN):

    #Set Up
    simulator = Simulator(rhost,rport,me,a_con,authN_data,l_acon,l_authN)
    simulator.startListening()

    return

def main():

    #Logging Set up
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[
        logging.FileHandler('endpoint.log', mode="w"),
        logging.StreamHandler()
    ])

    #Fetch Environment variables
    p_num = int(os.environ.get("PNUM",5))
    me = os.environ.get('ME',"endpoint-default")
    rabbit_host = os.environ.get("RABBIT_HOST","rabbitmq")
    rabbit_port = os.environ.get("RABBIT_PORT",5672)

    #Pool set up  
    pool = multiprocessing.Pool(p_num)

    #Shared Data Structures Set Up
    manager = multiprocessing.Manager()
    active_connections = manager.dict()
    l_actcon = manager.Lock()
    authN_data = manager.dict()
    l_authN = manager.Lock()

    results = []

    #Start the consumers
    for i in range(p_num):
        r = pool.apply_async(RMQ_Consumer,args=(rabbit_host,rabbit_port,me,active_connections,authN_data,l_actcon,l_authN))
        results.append(r)

    #Wait for processes to finish
    for r in results:
        r.wait()

    pool.close()
    pool.join()


    logging.info('Correctly quit the application')

if __name__ == "__main__":
	main()
