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

// QKDSimulatorSpec defines the desired state of QKDSimulator
type QKDSimulatorSpec struct {
	// INSERT ADDITIONAL SPEC FIELDS - desired state of cluster
	// Important: Run "make" to regenerate code after modifying this file

	// Foo is an example field of QKDSimulator. Edit qkdsimulator_types.go to remove/update
	//Foo string `json:"foo,omitempty"`

	/*
		For the Barebones version of the simulator we will just create a controller that will spawn 4 pods being this pods Alice, Bob, Eve/Clear Channel and an instace of RabbitMq that will have to take care of
		the communications among them since we want to replace the previous Rest API way of exchanging information. Moreover we won't think about different methods of authenticating classical messages exchanged yet.

		This below is a mix of config parameters for Both Eve Bob and Alice
	*/

	//Probably here we will just receive parameetr regarding manager and RabbitMq instances such as the ports on which we wanna expose their pods with
	//related services and the names of the services we wanna use

	// If any of these parameter sare left blankwe will use the default values for them
	//These values will be indicated in the relative documentation of the code

	RabbitMQ_Host     string `json:"rabbit-host,omitempty"`
	RabbitMQ_Port     int32  `json:"rabbit-port,omitempty"`
	Manager_Host      string `json:"manager-host,omitempty"`
	Manager_Rest_Port int32  `json:"manager-rest-port,omitempty"`
	Manager_Gui_Port  int32  `json:"manager-gui-port,omitempty"`
}

// QKDSimulatorStatus defines the observed state of QKDSimulator
type QKDSimulatorStatus struct {
	// INSERT ADDITIONAL STATUS FIELD - define observed state of cluster
	// Important: Run "make" to regenerate code after modifying this file
	Status string `json:"status,omitempty"`
}

//+kubebuilder:object:root=true
//+kubebuilder:subresource:status
//+kubebuilder:printcolumn:name="Protocol",type=string,JSONPath=`.spec.protocol`
//+kubebuilder:printcolumn:name="Status",type=string,JSONPath=`.status.status`

// QKDSimulator is the Schema for the qkdsimulators API
type QKDSimulator struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`

	Spec   QKDSimulatorSpec   `json:"spec,omitempty"`
	Status QKDSimulatorStatus `json:"status,omitempty"`
}

//+kubebuilder:object:root=true

// QKDSimulatorList contains a list of QKDSimulator
type QKDSimulatorList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []QKDSimulator `json:"items"`
}

func init() {
	SchemeBuilder.Register(&QKDSimulator{}, &QKDSimulatorList{})
}
