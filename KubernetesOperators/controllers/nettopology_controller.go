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
	//"time"
	"fmt"

	//appsv1 "k8s.io/api/apps/v1"
	//corev1 "k8s.io/api/core/v1"
	//metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/log"

	qkdsimv1 "s276624.qkdsim.dev/qkdsim/api/v1"
)

// NetTopologyReconciler reconciles a NetTopology object
type NetTopologyReconciler struct {
	client.Client
	Scheme *runtime.Scheme
}

//+kubebuilder:rbac:groups=qkdsim.s276624.qkdsim.dev,resources=nettopologys,verbs=get;list;watch;create;update;patch;delete
//+kubebuilder:rbac:groups=qkdsim.s276624.qkdsim.dev,resources=nettopologys/status,verbs=get;update;patch
//+kubebuilder:rbac:groups=qkdsim.s276624.qkdsim.dev,resources=nettopologys/finalizers,verbs=update

// Reconcile is part of the main kubernetes reconciliation loop which aims to
// move the current state of the cluster closer to the desired state.
// TODO(user): Modify the Reconcile function to compare the state specified by
// the QKDSimulator object against the actual cluster state, and then
// perform operations to make the cluster state reflect the state specified by
// the user.
//
// For more details, check Reconcile and its Result here:
// - https://pkg.go.dev/sigs.k8s.io/controller-runtime@v0.8.3/pkg/reconcile
func (r *NetTopologyReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
	logger := log.FromContext(ctx)

	// your logic here
	logger.Info("Starting NetTopology Controller !!", "name", req.NamespacedName)

	//Get CRD data
	var nettopology qkdsimv1.NetTopology

	//Fetch the newly provided resource
	if err := r.Get(ctx, req.NamespacedName, &nettopology); err != nil {
		logger.Error(err, "Error fetching the resource")
		return ctrl.Result{}, client.IgnoreNotFound(err)
	}

	//List modified topology received just for debugging purposes
	logger.Info(fmt.Sprint(nettopology.Spec.Nodes))
	logger.Info(fmt.Sprint(nettopology.Spec.Adjacency))

	//Fetch any already existing topologies
	var topologies qkdsimv1.NetTopologyList
	if err := r.List(ctx, &topologies); err != nil {
		logger.Error(err, "Error is when listing")
		return ctrl.Result{}, client.IgnoreNotFound(err)
	}

	if len(topologies.Items) > 1 {
		for _, top := range topologies.Items {
			if nettopology.Name != top.Name {
				if err := r.Delete(ctx, &top); err != nil {
					logger.Error(err, "Error is when setting the deletion timestamp")
					return ctrl.Result{}, client.IgnoreNotFound(err)
				}
			}
		}
	}

	//Deploy newly provided resource

	//Configure Patch Options
	applyOpts := []client.PatchOption{client.ForceOwnership, client.FieldOwner("NetTopology")}

	//For each node i go and deploy an endpoint
	for index := range nettopology.Spec.Nodes {
		endpdepl, err := r.desiredEndpointDeployment(nettopology, int32(index))
		if err != nil {
			return ctrl.Result{}, err
		}
		err = r.Patch(ctx, &endpdepl, client.Apply, applyOpts...)
		if err != nil {
			return ctrl.Result{}, err
		}
	}

	//Now we have to deploy the Toplogy's Communication Channels, one for each edge of the graph
	for index, connections := range nettopology.Spec.Adjacency {
		for _, n := range connections {
			i := r.indexOf(n, nettopology.Spec.Nodes)
			if i > index {
				com_chandepl, err := r.desiredComChanDeployment(nettopology, int32(index), int32(i))
				if err != nil {
					return ctrl.Result{}, err
				}
				err = r.Patch(ctx, &com_chandepl, client.Apply, applyOpts...)
				if err != nil {
					return ctrl.Result{}, err
				}
			}
		}
	}

	//Finally update the status and after return

	return ctrl.Result{}, nil
}

// SetupWithManager sets up the controller with the Manager.
func (r *NetTopologyReconciler) SetupWithManager(mgr ctrl.Manager) error {
	return ctrl.NewControllerManagedBy(mgr).
		For(&qkdsimv1.NetTopology{}).
		Complete(r)
}
