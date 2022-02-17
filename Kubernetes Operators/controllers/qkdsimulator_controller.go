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

package controllers

import (
	"context"
	"strconv"

	//appsv1 "k8s.io/api/apps/v1"
	//corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/runtime"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/log"

	qkdsimv1 "s276624.qkdsim.dev/qkdsim/api/v1"
)

// QKDSimulatorReconciler reconciles a QKDSimulator object
type QKDSimulatorReconciler struct {
	client.Client
	Scheme *runtime.Scheme
}

//+kubebuilder:rbac:groups=qkdsim.s276624.qkdsim.dev,resources=qkdsimulators,verbs=get;list;watch;create;update;patch;delete
//+kubebuilder:rbac:groups=qkdsim.s276624.qkdsim.dev,resources=qkdsimulators/status,verbs=get;update;patch
//+kubebuilder:rbac:groups=qkdsim.s276624.qkdsim.dev,resources=qkdsimulators/finalizers,verbs=update

// Reconcile is part of the main kubernetes reconciliation loop which aims to
// move the current state of the cluster closer to the desired state.
// TODO(user): Modify the Reconcile function to compare the state specified by
// the QKDSimulator object against the actual cluster state, and then
// perform operations to make the cluster state reflect the state specified by
// the user.
//
// For more details, check Reconcile and its Result here:
// - https://pkg.go.dev/sigs.k8s.io/controller-runtime@v0.8.3/pkg/reconcile
func (r *QKDSimulatorReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
	logger := log.FromContext(ctx)

	// your logic here
	logger.Info("Starting QKDSimulator Controller !!", "name", req.NamespacedName)

	//Get CRD data

	var qkdsimulator qkdsimv1.QKDSimulator

	if err := r.Get(ctx, req.NamespacedName, &qkdsimulator); err != nil {
		logger.Error(err, "name")
		return ctrl.Result{}, client.IgnoreNotFound(err)
	}

	//Spawn the pods we need using the helpers function

	//First of all let's spawn RabbitMQ deployment and service
	rabbitmqdepl, err := r.desiredRabbitMQ(qkdsimulator, qkdsimulator.Spec.RabbitMQ_Host, qkdsimulator.Spec.RabbitMQ_Port)
	if err != nil {
		return ctrl.Result{}, err
	}
	rabbitmqsvc, err := r.desiredRabbitMQService(qkdsimulator, qkdsimulator.Spec.RabbitMQ_Host, qkdsimulator.Spec.RabbitMQ_Port)
	if err != nil {
		return ctrl.Result{}, err
	}

	//apply ownership of these resources to the qkdsimulator
	applyOpts := []client.PatchOption{client.ForceOwnership, client.FieldOwner("QKDSimulator")}
	err = r.Patch(ctx, &rabbitmqdepl, client.Apply, applyOpts...)
	if err != nil {
		return ctrl.Result{}, err
	}
	err = r.Patch(ctx, &rabbitmqsvc, client.Apply, applyOpts...)
	if err != nil {
		return ctrl.Result{}, err
	}

	//Spawn the configmaps for the endpoints and com_channels
	var nodes_data = make(map[string]string)
	nodes_data["rabbit.host"] = qkdsimulator.Spec.RabbitMQ_Host + "-service"
	nodes_data["rabbit.port"] = strconv.Itoa(int(qkdsimulator.Spec.RabbitMQ_Port))

	nodes_conf, err := r.desiredConfigMap(qkdsimulator, "nodes", nodes_data)
	if err != nil {
		return ctrl.Result{}, err
	}

	err = r.Patch(ctx, &nodes_conf, client.Apply, applyOpts...)
	if err != nil {
		return ctrl.Result{}, err
	}

	var comchans_data = make(map[string]string)
	comchans_data["rabbit.host"] = qkdsimulator.Spec.RabbitMQ_Host + "-service"
	comchans_data["rabbit.port"] = strconv.Itoa(int(qkdsimulator.Spec.RabbitMQ_Port))

	comchans_conf, err := r.desiredConfigMap(qkdsimulator, "comchans", comchans_data)
	if err != nil {
		return ctrl.Result{}, err
	}

	err = r.Patch(ctx, &comchans_conf, client.Apply, applyOpts...)
	if err != nil {
		return ctrl.Result{}, err
	}

	// Now we deploy the Simulation Manager Pod
	simmanagerdepl, err := r.desiredManagerDeployment(qkdsimulator, qkdsimulator.Spec.RabbitMQ_Host, qkdsimulator.Spec.RabbitMQ_Port, qkdsimulator.Spec.Manager_Host, qkdsimulator.Spec.Manager_Rest_Port, qkdsimulator.Spec.Manager_Gui_Port)
	if err != nil {
		return ctrl.Result{}, err
	}
	simmanagersvc, err := r.desiredManagerService(qkdsimulator, qkdsimulator.Spec.Manager_Host, qkdsimulator.Spec.Manager_Rest_Port, qkdsimulator.Spec.Manager_Gui_Port)
	if err != nil {
		return ctrl.Result{}, err
	}

	//Deploy and apply ownership
	err = r.Patch(ctx, &simmanagerdepl, client.Apply, applyOpts...)
	if err != nil {
		return ctrl.Result{}, err
	}
	err = r.Patch(ctx, &simmanagersvc, client.Apply, applyOpts...)
	if err != nil {
		return ctrl.Result{}, err
	}

	//Set up Manager Ingress
	simmanageringress, err := r.desiredManagerIngress(qkdsimulator, qkdsimulator.Spec.Manager_Host, qkdsimulator.Spec.Manager_Rest_Port, qkdsimulator.Spec.Manager_Gui_Port)
	if err != nil {
		return ctrl.Result{}, err
	}

	//Deploy manager ingress and apply ownership
	err = r.Patch(ctx, &simmanageringress, client.Apply, applyOpts...)
	if err != nil {
		return ctrl.Result{}, err
	}

	//Finally update the status and after return

	return ctrl.Result{}, nil
}

// SetupWithManager sets up the controller with the Manager.
func (r *QKDSimulatorReconciler) SetupWithManager(mgr ctrl.Manager) error {
	return ctrl.NewControllerManagedBy(mgr).
		For(&qkdsimv1.QKDSimulator{}).
		Complete(r)
}
