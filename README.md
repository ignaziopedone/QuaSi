# QuaSi

This project aim at developing a full fledged QKD simulator based on either available or custom backends.

This implementation leverages two custom Kubernetes Operators to allow the deployment of all of the simulator's modules on a Kubernetes cluster.
Each of the different modules is implemented by its own custom Docker Image:

- Communication Channel Image
- Endpoint Image
- SimManager Image
- Jupyter Notebook Image

The **Endpoint** and **Communication Channel** modules allow during the deployment phase of the simulator to model a full-fledged network topology to perform point-to-point QKD simualtions on.
To be specific, the **Endpoint** image is used to implement each node of the modelled topology, while the **Communication Channel** one represents each direct link between the nodes of the topology.

The **SimManager** module is in charge of handling all of the external requests to the simulator. It allows any external entity to interact and use the simulator.

The **Jupyter Notebook** module introduces a simple GUI to the simulator that can be used to develop and custom Python scripts to interact with the simulator and perform QKD simulations.

The RabbitMQ message broker is used to handle all of the internal communications between the different modules of the simulator.

For the time being, there is  only a single backend available that allows the simulation of the BB84 protocol on any directly linked pair of the modelled network topology.

# Simulator Set Up

## Installing K3s

The first step to correctly run the QKD Simulator consists of installing any Kubernetes distribution. K3s1
is the suggested distribution to install since it is very lightweight and versatile and it
was also the one used during the development of the simulator. The easiest way to install K3s
consists of issuing the following command inside of the Linux terminal:

    curl -sfL https://get.k3s.io | sh -

## Installing Go

The next step to be able to have a working instance of the QKD Simulator consists of installing
the Go2 programming language. As listed by the documentation, in order to install Go, the first
thing to do is download the archive containing its installer.
Once downloaded, the archive will
need to be extracted into `/usr/local` thus creating a tree in `/usr/local/go`. Next, Go will need
to be added to the PATH environment variable and, to have a system-wide installation, it will be
sufficient to add to /etc/profile file the following line:

    export PATH=$PATH:/usr/local/go/bin

## Inserting Custom Operators in the Kubernetes Cluster

After having opened a terminal window inside the Kubernetes Operators folder we will need to move inside the folder containing the custom Operators and run the following commands:

    make manifests
    make generate
    make install

These commands are needed to let the K3s Kubernetes cluster know the Operators CRDs, that is to say the structure of the custom YAML configuration files to be used for the deployment. Finally, to start
the Operators it will be sufficient to build and run them through the following commands:

    make build
    make run

Now that the custom Kubernetes Operators are running, it is possible to write the two custom YAML configuration files to be used for the deployment of the simulator.

## Simulator Deployment

The first YAML file needed is the one that
will allow the user to deploy all of the QKD Simulator’s modules except the network topology to
model. The following is an example of such YAML file:

    apiVersion: qkdsim.s276624.qkdsim.dev/v1
    kind: QKDSimulator
    metadata:
    name: qkdsimulator-sample
    spec:
    rabbit-host: rabbittmq
    rabbit-port: 5672
    manager-host: sim-manager
    manager-rest-port: 6969
    manager-gui-port: 6997
    trng: 0
    pnum: 8

The structure of the file needs to be as the one shown above, but the user can easily edit the configuration of the simulator by editing the values of the fields specified under the spec part of the file. The following table shows the different editable fields and what they represent:

| Field name   |     Description      |
|----------|-------------|
| **rabbit-host** |  Name of the Kubernetes component running RabbitMQ |
| **rabbit-port** |  Port Number for the AMQP Protocol exposed by the Kubernetes component running RabbitMQ |
| **manager-host** | Name of the Kubernetes component running the Simulator Manager           |
| **manager-rest-port**             |  Port Number exposed by the Kubernetes component running the Simulator Manager to reach the Flask Web Server            |
| **manager-gui-port**              |   Port number exposed by the Kubernetes component running the Simulator Manager to access Jupyter Notebook          |
| **trng**            |  Boolean numerical parameter to choose to use a true quantum random number generator in the simulations or not  |
| **pnum**            |  Numerical parameter expressing the amount of parallelism desired for each topology node and link        |

Finally, one more field value of the file that the user can easily edit is the name under the metadata part of the file since it just represents the name the CRD symbolized by the file will have inside of the Kubernetes cluster.

Once the custom YAML file is ready, it will be sufficient to feed it to the K3s Kubernetes cluster through the following command:

    k3s kubectl apply -f NameOfSimulatorCustomYamlFile.yaml

In response to this command, the custom Kubernetes Operators that were started before and are still running will react and spawn the requested QKDSimulator custom resource and all of the different modules of the simulator associated with it, that is to say all of the modules except the network topology to model. In particular, the Kubernetes component that will be spawned inside of the cluster as a result of the previous operation, are:

- *Ingress Rule* component for the simulator;
- *ConfigMap* component for the topology nodes;
- *ConfigMap* component for the topology links;
- *Deployment* component for the Simulator Manager module;
- *StatefulSet* component for the RabbitMQ module;
- *Service* component associated to the Simulator Manager Deployment;
- *Service* component associated to the RabbitMQ StatefulSet.

## Topology Deployment

Once sure that all of the previous resources were deployed correctly and are up and running, it
is possible to work on the second custom YAML configuration file to deploy the desired network
topology. The following is an example of such YAML file:

    apiVersion: qkdsim.s276624.qkdsim.dev/v1
    kind: NetTopology
    metadata:
    name: nettopology-sample
    spec:
    adjacency:
      - - id: node2
        - id: node3
        - id: node4
      - - id: node1
        - id: node4
      - - id: node1
        - id: node4
      - - id: node1
        - id: node2
        - id: node3
    nodes:
      - id: node1
      - id: node2
      - id: node3
      - id: node4

The structure of the file needs to be as the one shown above, but the user can easily edit the network he wants the simulator to model by editing the values of the fields specified under the spec part of the file. The following table shows the different editable fields and what they represent:

| Field name   |     Description      |
|----------|-------------|
| **adjacency** |  Adjacency list of the undirected Graph representation for the network topology to model |
| **nodes**     |   List of the nodes of the network topology to model        |

Finally, it is important to note that the name of the nodes used inside the custom YAML configuration file can be changed to anything the user desires since they simply represent placeholders. Once deployed inside the cluster the name that each node of the topology will have is
*endpoint-index_of_node_in_nodes_list*. 

The same will happen for the links of the modelled topology,
each of them will have the following name: *ccindex1-index2* where the two indexes specified will be the ones of the nodes that specific link connects.

Once the custom YAML file is ready, it will be sufficient to feed it to the K3s Kubernetes cluster through the following command:

    k3s kubectl apply -f NameOfTopologyCustomYamlFile.yaml

In response to this command, the custom Kubernetes Operators that were started before and are still running will react and spawn the requested NetTopology custom resource and all of the different modules of the described network topology associated with it.

In particular, the Kubernetes components that will be spawned inside of the cluster as a result of the previous operation, are:

- a *Deployment* component for each node of the modelled topology
- a *Deployment* component for each link of the modelled topology
  
Furthermore, it will also be possible to check the successful deployment of the network topology onto the K3s Kubernetes cluster through the management interface exposed by RabbitMQ.

In order to access such interface, the first thing to do will be using the following command to check the public IP address the K3s Kubernetes cluster associated to the Service component for RabbitMQ.

Next, it will be sufficient to connect to the external IP address on the default port RabbitMQ
uses for exposing the management interface (15672) and use the default credentials to access:

    username: guest
    password: guest

## Simulator Usage

### Init Phase

Before actually being able to start one or more QKD Simulation, an initialization phase to properly set up the QKD Simulator has to be carried out.

The first thing to do consists of notifying the Simulator Manager about the network topology just modelled and deployed. To do so, it will be sufficient to leverage the appropriate REST API exposed by the Simulator Manager.

In particular, the following POST HTTP request has to be sent:

    http://qkdsim.com/netTopology

The appropriate representation of the modelled topology has to be sent as the body of the request.
The following is an example of the JSON serialized representation of the modelled topology to be sent to the Simulator Manager:

    {
        "directed": false,
        "multigraph": false,
        "graph": [],
        "nodes": [
            {"id": "node1"},
            {"id": "node2"},
            {"id": "node3"},
            {"id": "node4"}
        ],
        "adjacency": [
            [
                {"id": "node2"},
                {"id": "node3"},
                {"id": "node4"}
            ],
            [
                {"id": "node1"},
                {"id": "node4"}
            ],
            [
                {"id": "node1"},
                {"id": "node4"}
            ],
            [
                {"id": "node1"},
                {"id": "node2"},
                {"id": "node3"}
            ]
        ]
    }

It is important to note that such representation can easily be obtained by leveraging the NetworkX Python library as well:

    import networkx
    from networkx.readwrite import json_graph
    import json
    graph = networkx.Graph()
    graph.add_node("node1")
    graph.add_node("node2")
    graph.add_node("node3")
    graph.add_node("node4")
    graph.add_edge("node1","node2")
    graph.add_edge("node1","node3")
    graph.add_edge("node1","node4")
    graph.add_edge("node2","node4")
    graph.add_edge("node3","node4")
    topology_rep = json.dumps(json_graph.adjacency_data(graph))

As a response to the request, the user will receive the JSON serialized representation of the custom Kubernetes YAML file to feed the cluster to model the specified topology.
This happens because this REST API can also be used as a utility function before deploying the topology to be sure to obtain the correct syntax of the custom YAML file to feed the cluster.

Once notified the Simulator Manager about the modelled network topology, the next step consists of properly setting up the nodes and links of the topology with the proper parameters in case the user wants to select a specific authentication method for the classical channel communication during a QKD simulation. To do so, it will be sufficient to use the appropriate REST API exposed by the SimManager module.

In particular, the following POST HTTP request will need to be sent:

    http://qkdsim.com/distributeKeys

The body of the request will contain the desired authentication method for which the user wants to configure the nodes and link of the topology.

    {"authentication": "sphincs"}

As a consequence of this request, the Simulator Manager will send the appropriate messages of type Keys containing the needed parameters for the selected authentication method to all of the different nodes and links of the modelled topology. 

Now, if during any QKD simulation the user will want to use such authentication method, the entities of the topology involved in it will
have the appropriate parameters to apply such a method.
As a response to this request, the user will receive the outcome of the required operation.

It is important to note that the only currently supported authentication method is SPHINCS+, a post-quantum cryptography hash-based signature scheme.

Now it will be possible to carry out QKD Simulations on the network topology modelled by the simulator.

### Carrying out QKD Simulations

To carry out one or more QKD simulations on the modelled network topology, the first thing to do will be choosing two connected nodes to start one or more simulations between. This goal can be easily achieved by using the appropriate REST API exposed by the Simulator Manager and
issuing the following POST HTTP request:

    http://qkdsim.com/begin

The body of the request will need to contain the two endpoints of the modelled topology the user wants to carry out QKD simulations between:

    { "SRC": "endpoint-1", "DST": "endpoint-3" }

As a consequence of this request, the Simulator Manager will check if the two specified nodes of the topology are connected directly by a link and if this is the case will create and store a unique UUID associated with the pair of endpoints specified. The user will receive as a response
to the request the outcome of the operation required.

Once successfully created a UUID associated with the specified pair of endpoints specified, it will be possible to start one or more QKD simulations between them to generate one or more keys. To do so, it will be sufficient to use the appropriate REST API exposed by the Simulator
Manager and issue the following POST HTTP request:

    http://qkdsim.com/startKeyExchange

The body of this request will need to contain all of the configuration parameters for the QKD simulation, the name of the endpoints to carry the simulation between and the one of the communication channel connecting them. The following is an example of body for such request:

    {
        "protocol": "bb84",
        "key_length": 4096,
        "chunk_size": 5,
        "authentication": "sphincs",
        "com_channel": "cc1-3",
        "interceptAndResend": 0,
        "manInTheMiddle": 0,
        "source": "endpoint-1",
        "destination": "endpoint-3",
        "key_number": 25
    }

It is important to note that the following parameters are mandatory:

- *protocol*
- *key_length*
- *source*
- *destination*
- *com_channel*
- *key_number*
  
On the other hand, a default value will be used for the remaining ones if omitted. In particular:

- *chunk_size* default value is 5
- *authentication* default value is “none”
- *interceptAndResend* dafult value is 0 meaning false
- *manInTheMiddle* default value is 0 meaning false

As a response to this request, if everything was successful, the user will receive the UUID associated with the endpoints of the topology specified which will also be the name of the RabbitMQ
queue the user will be able to find the results of the requested QKD simulations. On the other hand, if any errors occurred the response will be used to notify the user.

It is important to note that the results of the requested QKD simulations will be put on two different queues by RabbitMQ. The name of the queues will be:

- *UUID*, the one associated to the pair of endpoints the QKD simulations were carried between
- *UUID_R*.

A copy of the result of each simulation will be put on both of the queues to easily allow two higher-level entities wanting to use the simulator to each consume a copy of the outcomes of the simulations.

Finally, once the user is satisfied with the amount of QKD simulations carried out between two nodes of the topology, it will be sufficient to use the appropriate REST API provided by the SimManager module to clean up. In particular, the following POST HTTP request will need to be
sent:

    http://qkdsim.com/end

The body of this request will need to contain the UUID associated with the two specific topology nodes the user wants to stop carrying QKD simulations between: The following is an example of such a body:

    { "ID": "b5bbac53-dd63-4580-8a08-6e0243f95a0a" }

If the provided ID exists between the ones stored by the SimManager module, that is to say it was generated by a successful corresponding *begin* operation, the provided ID will be deleted and the user won’t be able to carry out more QKD simulations between the corresponding nodes of
the topology unless he performs a new *begin* operation. As a response, the user will receive the outcome of the requested operation.









