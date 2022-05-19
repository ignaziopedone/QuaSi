/*
Copyright 2021.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
*/

package v1

import (
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

// EDIT THIS FILE!  THIS IS SCAFFOLDING FOR YOU TO OWN!
// NOTE: json tags are required.  Any new fields you add must have json tags for the fields to be serialized.

//Add node struct type for Python Networkx Topology import
type Node struct {
	Id string `json:"id"`
}

// QKDSimulatorSpec defines the desired state of QKDSimulator
type NetTopologySpec struct {
	// INSERT ADDITIONAL SPEC FIELDS - desired state of cluster
	// Important: Run "make" to regenerate code after modifying this file

	// Foo is an example field of QKDSimulator. Edit qkdsimulator_types.go to remove/update
	//Foo string `json:"foo,omitempty"`

	/*
		For the Barebones version of the simulator we will just create a controller that will spawn 4 pods being this pods Alice, Bob, Eve/Clear Channel and an instace of RabbitMq that will have to take care of
		the communications among them since we want to replace the previous Rest API way of exchanging information. Moreover we won't think about different methods of authenticating classical messages exchanged yet.

		This below is a mix of config parameters for Both Eve Bob and Alice
	*/
	Nodes     []Node   `json:"nodes"`
	Adjacency [][]Node `json:"adjacency"`

	/* RabbitMQ Config Parameters if different from defaults, for the basic version we will stick to ususal ones and do not add anything more */

}

// QKDSimulatorStatus defines the observed state of QKDSimulator
type NetTopologyStatus struct {
	// INSERT ADDITIONAL STATUS FIELD - define observed state of cluster
	// Important: Run "make" to regenerate code after modifying this file
	Status string `json:"status,omitempty"`
}

//+kubebuilder:object:root=true
//+kubebuilder:subresource:status
//+kubebuilder:printcolumn:name="Protocol",type=string,JSONPath=`.spec.protocol`
//+kubebuilder:printcolumn:name="Status",type=string,JSONPath=`.status.status`

// QKDSimulator is the Schema for the qkdsimulators API
type NetTopology struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`

	Spec   NetTopologySpec   `json:"spec,omitempty"`
	Status NetTopologyStatus `json:"status,omitempty"`
}

//+kubebuilder:object:root=true

// QKDSimulatorList contains a list of QKDSimulator
type NetTopologyList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []NetTopology `json:"items"`
}

func init() {
	SchemeBuilder.Register(&NetTopology{}, &NetTopologyList{})
}
