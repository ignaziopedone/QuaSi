from unittest import result
from qiskit import QuantumCircuit, ClassicalRegister, QuantumRegister
import logging
import pickle
from trng import randomStringGen
import numpy as np
import pika
import os
import logging
import multiprocessing


class Communication_Channel():

	connection = None
	rec_ch = None
	send_ch = None
	me = ""
	first_endp = None
	second_endp = None

	def __init__(self,rhost,rport,me,fendp,sendp):
		
		self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=rhost,port=rport))
		self.send_ch = self.connection.channel()
		self.rec_ch = self.connection.channel()

		#Setup Endpoint
		self.me = me

		#Setup Channels for the endpoints i connect:
		self.first_endp = fendp
		self.second_endp = sendp

		#Check queue existence and creating them in case it hasn't been done yet
		self.send_ch.queue_declare(queue="endpoint-" + str(self.first_endp),auto_delete=True)
		self.send_ch.queue_declare(queue="endpoint-" + str(self.second_endp),auto_delete=True)

	def type_switcher(self,argument):
		switcher = {
			"sendRegister": self.sendRegister,
			"compareBasis": self.compareBasis,
			"verifyKey": self.verifyKey,
		}

		return switcher.get(argument,"Invalid Mssage Type Received")
	
	def sendRegister(self,type,source,destination,metadata,msg):
	
		qubits = msg

		interceptAndResend = metadata['interceptAndResend']
		

		# Do attacks on quantum channel here
		if interceptAndResend and destination == metadata["id_connection"]["DST"]: # Forward
			chunk = qubits[0].num_qubits
			eveTable = np.array([])
			eveMeasurements = []
			for i in range(len(qubits)):
				# generate a quantum circuit random basis for measurements
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
				eveTable = np.append(eveTable, table)
				eveMeasurements.append(qubits[i].evolve(circuit))

			# replace data to be forwarded
			qubits = eveMeasurements
		
		#Building message to send:		
		mess = [type,source,destination,metadata,qubits]

		#Sending answer to proper destination according to direction parameter:
		com_chan = self.send_ch
		com_chan.basic_publish(exchange='',routing_key=destination,body=pickle.dumps(mess))

	def compareBasis(self,type,source,destination,metadata,msg):
		forward = msg

		if len(forward) == 2 and destination == metadata["id_connection"]["SRC"]: # Backward
			# sphincs+ or no authentication
			basis_table = forward[0]
			table_sign = forward[1]
			forward = [basis_table, table_sign]

		manInTheMiddle = metadata['manInTheMiddle']
	
		# Do attacks on classical channel here
		if manInTheMiddle:
			pass
		
		mess = [type,source,destination,metadata,forward]

		#Sending answer to proper destination according to direction parameter:
		com_chan = self.send_ch
		com_chan.basic_publish(exchange='',routing_key=destination,body=pickle.dumps(mess))

	def verifyKey(self,type,source,destination,metadata,msg):
		forward = msg

		if len(forward) == 4 and destination == metadata["id_connection"]["DST"]: # Forward
			# sphincs+
			subkey = forward[0]
			key_sign = forward[1]
			picked = forward[2]
			pick_sign = forward[3]
			forward = [subkey, key_sign, picked, pick_sign]

		manInTheMiddle = metadata['manInTheMiddle']

		# Do attacks on classical channel here
		if manInTheMiddle:
			pass

		mess = [type,source,destination,metadata,forward]
		
		#Sending answer to proper destination according to direction parameter:
		com_chan = self.send_ch
		com_chan.basic_publish(exchange='',routing_key=destination,body=pickle.dumps(mess))

	def startListening(self):

		#Define my queue to listen for messages on
		rec_ch = self.rec_ch	
		queueResult = rec_ch.queue_declare(queue=self.me,auto_delete=True)
		rec_name = queueResult.method.queue

		logging.info("Connected to queue called " + rec_name)


		def message_handler(ch, method, properties, body):
			# Struct of the message is [type, message]
			
			res = pickle.loads(body)		
			
			#According to the type of message received, we will execute the appropriate function
			type = res[0]
			source = res[1]
			destination = res[2]
			metadata = res[3]
			msg = res[4]

			logging.info("Received message: Type-> " + str(type) + "  S-> " + str(source) + "  D-> " + str(destination))

			handler = self.type_switcher(type)
			handler(type,source,destination,metadata,msg)
			#Done procesisng message, I can acknowledge it
			ch.basic_ack(delivery_tag=method.delivery_tag)
				
		logging.info('Starting to listen for messages on queue ' + str(rec_name))
		rec_ch.basic_consume(on_message_callback=message_handler, queue=rec_name) #Manual acknowledgement on by default
		rec_ch.start_consuming()

def RMQ_Consumer(rhost,rport,me,fendp,sendp):

    com_chan = Communication_Channel(rhost,rport,me,fendp,sendp)
    com_chan.startListening()

    return

def main():

	logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[
		logging.FileHandler('com_chan.log', mode="w"),
		logging.StreamHandler()
	])

	#Fetch Environment variables
	p_num = int(os.environ.get("PNUM",5))
	me = os.environ.get('ME',"endpoint-default")
	rabbit_host = os.environ.get("RABBIT_HOST","rabbitmq")
	rabbit_port = os.environ.get("RABBIT_PORT",5672)
	first_endp = os.environ.get("NODE0","endpoint-default")
	second_endp = os.environ.get("NODE1","endpoint-default")

	#Pool set up  
	pool = multiprocessing.Pool(p_num)

	results = []

	#Start the consumers
	for i in range(p_num):
		r = pool.apply_async(RMQ_Consumer,args=(rabbit_host,rabbit_port,me,first_endp,second_endp))
		results.append(r)

	#Wait for processes to finish
	for r in results:
		r.wait()

	pool.close()
	pool.join()


	logging.info("Correctly quit the applictaion")

if __name__ == "__main__":
	main()
