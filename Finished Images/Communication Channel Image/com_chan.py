from qiskit import QuantumCircuit, ClassicalRegister, QuantumRegister
import logging
import pickle
from trng import randomStringGen
import numpy as np
import pika
import os
import logging


class Communication_Channel():

	connection = None
	rec_ch = None
	send_ch = None
	me = ""
	first_endp = None
	second_endp = None

	def __init__(self):
		
		rabbit_host = os.environ.get("RABBIT_HOST","rabbitmq")
		rabbit_port = os.environ.get("RABBIT_PORT",5672)

		self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbit_host,port=rabbit_port))
		self.send_ch = self.connection.channel()
		self.rec_ch = self.connection.channel()

		#Setup Endpoint
		self.me = os.environ.get('ME',"cc-default")

		#Check proper name for com channel since we need it to set up rabbit communication properly--TO DO

		#Setup Channels for the endpoints i connect:
		self.first_endp = os.environ.get("NODE0","endpoint-default")
		self.second_endp = os.environ.get("NODE1","endpoint-default")

		#Check queue existence and creating them in case it hasn't been done yet
		self.send_ch.queue_declare(queue="endpoint-" + str(self.first_endp),durable=True)
		self.send_ch.queue_declare(queue="endpoint-" + str(self.second_endp),durable=True)

	def type_switcher(self,argument):
		switcher = {
			"sendRegister": self.sendRegister,
			"compareBasis": self.compareBasis,
			"verifyKey": self.verifyKey,
		}

		return switcher.get(argument,"Invalid Mssage Type Received")
	
	def sendRegister(self,type,source,destination,direction,metadata,msg):
	
		qubits = msg

		interceptAndResend = metadata['interceptAndResend']
		

		# Do attacks on quantum channel here
		if interceptAndResend and direction == "Forward":
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
		mess = [type,source,destination,direction,metadata,qubits]

		#Sending answer to proper destination according to direction parameter:
		com_chan = self.send_ch
		if direction == "Forward":
			com_chan.basic_publish(exchange='',routing_key=destination,body=pickle.dumps(mess))
		elif direction == "Backward":
			com_chan.basic_publish(exchange='',routing_key=source,body=pickle.dumps(mess))


	def compareBasis(self,type,source,destination,direction,metadata,msg):
		forward = msg

		if len(forward) == 2 and direction == "Backward": 
			# sphincs+
			basis_table = forward[0]
			table_sign = forward[1]
			forward = [basis_table, table_sign]

		manInTheMiddle = metadata['manInTheMiddle']
	
		# Do attacks on classical channel here
		if manInTheMiddle:
			pass
		
		mess = [type,source,destination,direction,metadata,forward]

		#Sending answer to proper destination according to direction parameter:
		com_chan = self.send_ch
		if direction == "Forward":
			com_chan.basic_publish(exchange='',routing_key=destination,body=pickle.dumps(mess))
		elif direction == "Backward":
			com_chan.basic_publish(exchange='',routing_key=source,body=pickle.dumps(mess))


	def verifyKey(self,type,source,destination,direction,metadata,msg):
		forward = msg

		if len(forward) == 4 and direction == "Forward": # O Direction Andata
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

		mess = [type,source,destination,direction,metadata,forward]
		
		#Sending answer to proper destination according to direction parameter:
		com_chan = self.send_ch
		if direction == "Forward":
			com_chan.basic_publish(exchange='',routing_key=destination,body=pickle.dumps(mess))
		elif direction == "Backward":
			com_chan.basic_publish(exchange='',routing_key=source,body=pickle.dumps(mess))

	def startListening(self):

		#Define my queue to listen for messages on
		rec_ch = self.rec_ch	
		queueResult = rec_ch.queue_declare(queue=self.me,durable=True)
		rec_name = queueResult.method.queue

		logging.info("Connected to queue called " + rec_name)


		def message_handler(ch, method, properties, body):
			# Struct of the message is [type, message]
			
			res = pickle.loads(body)		
			
			#According to the type of message received, we will execute the appropriate function
			type = res[0]
			source = res[1]
			destination = res[2]
			direction = res[3]
			metadata = res[4]
			msg = res[5]

			logging.info("Received message: Type-> " + str(type) + "  S-> " + str(source) + "  D-> " + str(destination) + "  Dir-> " + str(direction))

			handler = self.type_switcher(type)
			handler(type,source,destination,direction,metadata,msg)
				
		logging.info('Starting to listen for messages on queue ' + str(rec_name))
		rec_ch.basic_consume(on_message_callback=message_handler, queue=rec_name, auto_ack=True)			
		rec_ch.start_consuming()

def main():
	logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[
		logging.FileHandler('com_chan.log', mode="w"),
		logging.StreamHandler()
	])

	logging.info("Starting the listening...")

	com_chan = Communication_Channel()
	com_chan.startListening()

	logging.info("Correctly quit the applictaion")

if __name__ == "__main__":
	main()
