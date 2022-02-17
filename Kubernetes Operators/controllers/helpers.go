package controllers

import (
	//"context"
	"fmt"
	//"net"
	"strconv"

	appsv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"
	networkingv1 "k8s.io/api/networking/v1"

	//"k8s.io/apimachinery/pkg/api/resource"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/util/intstr"
	ctrl "sigs.k8s.io/controller-runtime"

	//"sigs.k8s.io/controller-runtime/pkg/client"
	//"sigs.k8s.io/controller-runtime/pkg/handler"

	qkdsimv1 "s276624.qkdsim.dev/qkdsim/api/v1"
)

func (r *QKDSimulatorReconciler) desiredConfigMap(qkds qkdsimv1.QKDSimulator, who_conf string, data map[string]string) (corev1.ConfigMap, error) {

	//Configure data map with parameters neede by Alice, Eve and Bob

	cmap := corev1.ConfigMap{
		TypeMeta: metav1.TypeMeta{APIVersion: "v1", Kind: "ConfigMap"},
		ObjectMeta: metav1.ObjectMeta{
			Name:      who_conf + "-config",
			Namespace: "default",
		},
		Data: data,
	}

	if err := ctrl.SetControllerReference(&qkds, &cmap, r.Scheme); err != nil {
		return cmap, err
	}

	return cmap, nil
}

func (r *QKDSimulatorReconciler) desiredRabbitMQPVC(qkdsim qkdsimv1.QKDSimulator, name string, port int32) (corev1.PersistentVolumeClaim, error) {
	labels := make(map[string]string)

	labels["app"] = name

	stset := corev1.PersistentVolumeClaim{
		TypeMeta: metav1.TypeMeta{APIVersion: appsv1.SchemeGroupVersion.String(), Kind: "StatefulSet"},
		ObjectMeta: metav1.ObjectMeta{
			Name:      name,
			Namespace: "default",
		},
		Spec: corev1.PersistentVolumeClaimSpec{
			Resources: corev1.ResourceRequirements{
				Requests: corev1.ResourceList{},
			},
		},
	}

	if err := ctrl.SetControllerReference(&qkdsim, &stset, r.Scheme); err != nil {
		return stset, err
	}

	return stset, nil
}

func (r *QKDSimulatorReconciler) desiredRabbitMQ(qkdsim qkdsimv1.QKDSimulator, name string, port int32) (appsv1.StatefulSet, error) {
	labels := make(map[string]string)

	labels["app"] = name

	stset := appsv1.StatefulSet{
		TypeMeta: metav1.TypeMeta{APIVersion: appsv1.SchemeGroupVersion.String(), Kind: "StatefulSet"},
		ObjectMeta: metav1.ObjectMeta{
			Name:      name,
			Namespace: "default",
			Labels:    labels,
		},
		Spec: appsv1.StatefulSetSpec{
			Selector: &metav1.LabelSelector{
				MatchLabels: labels,
			},
			ServiceName: name,
			Template: corev1.PodTemplateSpec{
				ObjectMeta: metav1.ObjectMeta{
					Labels: labels,
				},
				Spec: corev1.PodSpec{
					Volumes: []corev1.Volume{
						corev1.Volume{
							Name: name,
							VolumeSource: corev1.VolumeSource{
								PersistentVolumeClaim: &corev1.PersistentVolumeClaimVolumeSource{
									ClaimName: name,
								},
							},
						},
					},
					Containers: []corev1.Container{
						corev1.Container{Name: name, VolumeMounts: []corev1.VolumeMount{corev1.VolumeMount{MountPath: "/var/lib/rabbitmq", Name: name}}, Image: "rabbitmq:3.8.3-management", Ports: []corev1.ContainerPort{corev1.ContainerPort{ContainerPort: 15672, Name: "http", Protocol: corev1.ProtocolTCP}, corev1.ContainerPort{ContainerPort: 5672, Name: "amqp", Protocol: corev1.ProtocolTCP}}, LivenessProbe: &corev1.Probe{Handler: corev1.Handler{Exec: &corev1.ExecAction{Command: []string{"rabbitmq-diagnostics", "ping"}}}, InitialDelaySeconds: 10, PeriodSeconds: 30, TimeoutSeconds: 15}, ReadinessProbe: &corev1.Probe{Handler: corev1.Handler{Exec: &corev1.ExecAction{Command: []string{"rabbitmq-diagnostics", "check_port_connectivity"}}}, InitialDelaySeconds: 10, TimeoutSeconds: 15, PeriodSeconds: 30}},
					},
				},
			},
		},
	}

	if err := ctrl.SetControllerReference(&qkdsim, &stset, r.Scheme); err != nil {
		return stset, err
	}

	return stset, nil
}

func (r *QKDSimulatorReconciler) desiredRabbitMQService(qkdsim qkdsimv1.QKDSimulator, name string, port int32) (corev1.Service, error) {
	labels := make(map[string]string)

	labels["app"] = name

	svc := corev1.Service{
		TypeMeta: metav1.TypeMeta{APIVersion: corev1.SchemeGroupVersion.String(), Kind: "Service"},
		ObjectMeta: metav1.ObjectMeta{
			Name:      name + "-service",
			Namespace: "default",
			Labels:    labels,
		},
		Spec: corev1.ServiceSpec{
			Ports: []corev1.ServicePort{
				{Name: "http", Port: 15672, Protocol: corev1.ProtocolTCP, TargetPort: intstr.FromInt(15672)},
				corev1.ServicePort{Name: "amqp", Port: port, Protocol: corev1.ProtocolTCP, TargetPort: intstr.FromInt(5672)},
			},
			Selector: labels,
			Type:     corev1.ServiceTypeLoadBalancer,
		},
	}

	// always set the controller reference so that we know which object owns this.
	if err := ctrl.SetControllerReference(&qkdsim, &svc, r.Scheme); err != nil {
		return svc, err
	}

	return svc, nil
}

func (r *NetTopologyReconciler) desiredEndpointDeployment(net qkdsimv1.NetTopology, number int32) (appsv1.Deployment, error) {
	labels := make(map[string]string)

	labels["app"] = "simendpoint-" + fmt.Sprint(number)

	depl := appsv1.Deployment{
		TypeMeta: metav1.TypeMeta{APIVersion: appsv1.SchemeGroupVersion.String(), Kind: "Deployment"},
		ObjectMeta: metav1.ObjectMeta{
			Name:      "simendpoint-" + fmt.Sprint(number),
			Namespace: "default",
			//Labels: labels,
		},
		Spec: appsv1.DeploymentSpec{
			// Replicas value won't be nil because defaulting
			Selector: &metav1.LabelSelector{
				MatchLabels: labels,
			},
			Template: corev1.PodTemplateSpec{
				ObjectMeta: metav1.ObjectMeta{
					Labels: labels,
				},
				Spec: corev1.PodSpec{
					Containers: []corev1.Container{
						corev1.Container{
							Name:            "simendpoint-" + fmt.Sprint(number),
							Image:           "s276624/testingqkdsimulator:endpoint",
							ImagePullPolicy: corev1.PullAlways,
							Env: []corev1.EnvVar{
								corev1.EnvVar{
									Name:  "ME",
									Value: "endpoint-" + fmt.Sprint(number),
								},
								corev1.EnvVar{
									Name: "RABBIT_HOST",
									ValueFrom: &corev1.EnvVarSource{
										ConfigMapKeyRef: &corev1.ConfigMapKeySelector{
											LocalObjectReference: corev1.LocalObjectReference{
												Name: "nodes-config",
											},
											Key: "rabbit.host",
										},
									},
								},
								corev1.EnvVar{
									Name: "RABBIT_PORT",
									ValueFrom: &corev1.EnvVarSource{
										ConfigMapKeyRef: &corev1.ConfigMapKeySelector{
											LocalObjectReference: corev1.LocalObjectReference{
												Name: "nodes-config",
											},
											Key: "rabbit.port",
										},
									},
								},
							},
						},
					},
				},
			},
		},
	}

	if err := ctrl.SetControllerReference(&net, &depl, r.Scheme); err != nil {
		return depl, err
	}

	return depl, nil
}

//Helper to spawn ComChannel Instance
func (r *NetTopologyReconciler) desiredComChanDeployment(net qkdsimv1.NetTopology, s int32, d int32) (appsv1.Deployment, error) {
	labels := make(map[string]string)

	name := "cc" + fmt.Sprint(s) + "-" + fmt.Sprint(d)

	labels["app"] = name

	depl := appsv1.Deployment{
		TypeMeta: metav1.TypeMeta{APIVersion: appsv1.SchemeGroupVersion.String(), Kind: "Deployment"},
		ObjectMeta: metav1.ObjectMeta{
			Name:      name,
			Namespace: "default",
			//Labels: labels,
		},
		Spec: appsv1.DeploymentSpec{
			// Replicas value won't be nil because defaulting
			Selector: &metav1.LabelSelector{
				MatchLabels: labels,
			},
			Template: corev1.PodTemplateSpec{
				ObjectMeta: metav1.ObjectMeta{
					Labels: labels,
				},
				Spec: corev1.PodSpec{
					Containers: []corev1.Container{
						corev1.Container{
							Name:            name,
							Image:           "s276624/testingqkdsimulator:com_chan",
							ImagePullPolicy: corev1.PullAlways,
							Env: []corev1.EnvVar{
								corev1.EnvVar{
									Name:  "NODE0",
									Value: strconv.Itoa(int(s)),
								},
								corev1.EnvVar{
									Name:  "NODE1",
									Value: strconv.Itoa(int(d)),
								},
								corev1.EnvVar{
									Name:  "ME",
									Value: name,
								},
								corev1.EnvVar{
									Name: "RABBIT_HOST",
									ValueFrom: &corev1.EnvVarSource{
										ConfigMapKeyRef: &corev1.ConfigMapKeySelector{
											LocalObjectReference: corev1.LocalObjectReference{
												Name: "comchans-config",
											},
											Key: "rabbit.host",
										},
									},
								},
								corev1.EnvVar{
									Name: "RABBIT_PORT",
									ValueFrom: &corev1.EnvVarSource{
										ConfigMapKeyRef: &corev1.ConfigMapKeySelector{
											LocalObjectReference: corev1.LocalObjectReference{
												Name: "comchans-config",
											},
											Key: "rabbit.port",
										},
									},
								},
							},
						},
					},
				},
			},
		},
	}

	if err := ctrl.SetControllerReference(&net, &depl, r.Scheme); err != nil {
		return depl, err
	}

	return depl, nil
}

func (r *QKDSimulatorReconciler) desiredManagerDeployment(qkds qkdsimv1.QKDSimulator, rabbit_host string, rabbit_port int32, host_name string, host_port int32, gui_port int32) (appsv1.Deployment, error) {
	labels := make(map[string]string)

	labels["app"] = host_name

	depl := appsv1.Deployment{
		TypeMeta: metav1.TypeMeta{APIVersion: appsv1.SchemeGroupVersion.String(), Kind: "Deployment"},
		ObjectMeta: metav1.ObjectMeta{
			Name:      host_name,
			Namespace: "default",
			//Labels: labels,
		},
		Spec: appsv1.DeploymentSpec{
			// Replicas value won't be nil because defaulting
			Selector: &metav1.LabelSelector{
				MatchLabels: labels,
			},
			Template: corev1.PodTemplateSpec{
				ObjectMeta: metav1.ObjectMeta{
					Labels: labels,
				},
				Spec: corev1.PodSpec{
					Containers: []corev1.Container{
						corev1.Container{
							Name:            host_name,
							Image:           "s276624/testingqkdsimulator:manager",
							ImagePullPolicy: corev1.PullAlways,
							Ports: []corev1.ContainerPort{
								corev1.ContainerPort{
									Name:          "http",
									ContainerPort: host_port,
									Protocol:      corev1.ProtocolTCP,
								},
							},
							Env: []corev1.EnvVar{
								corev1.EnvVar{
									Name:  "PORT",
									Value: strconv.Itoa(int(host_port)),
								},
								corev1.EnvVar{
									Name:  "RABBIT_HOST",
									Value: rabbit_host + "-service",
								},
								corev1.EnvVar{
									Name:  "RABBIT_PORT",
									Value: strconv.Itoa(int(rabbit_port)),
								},
							},
						},
						corev1.Container{
							Name:            "jupyter",
							Image:           "s276624/testingqkdsimulator:jupyter",
							ImagePullPolicy: corev1.PullAlways,
							Ports: []corev1.ContainerPort{
								corev1.ContainerPort{
									Name:          "jupyter",
									ContainerPort: gui_port,
									Protocol:      corev1.ProtocolTCP,
								},
							},
							Env: []corev1.EnvVar{
								corev1.EnvVar{
									Name:  "PORT",
									Value: strconv.Itoa(int(gui_port)),
								},
								corev1.EnvVar{
									Name:  "RABBIT_HOST",
									Value: rabbit_host + "-service",
								},
								corev1.EnvVar{
									Name:  "RABBIT_PORT",
									Value: strconv.Itoa(int(rabbit_port)),
								},
							},
						},
					},
				},
			},
		},
	}

	if err := ctrl.SetControllerReference(&qkds, &depl, r.Scheme); err != nil {
		return depl, err
	}

	return depl, nil
}

func (r *QKDSimulatorReconciler) desiredManagerService(qkds qkdsimv1.QKDSimulator, host_name string, host_port int32, gui_port int32) (corev1.Service, error) {
	labels := make(map[string]string)

	labels["app"] = host_name

	svc := corev1.Service{
		TypeMeta: metav1.TypeMeta{APIVersion: corev1.SchemeGroupVersion.String(), Kind: "Service"},
		ObjectMeta: metav1.ObjectMeta{
			Name:      host_name + "-service",
			Namespace: "default",
		},
		Spec: corev1.ServiceSpec{
			Ports: []corev1.ServicePort{
				{Name: "http", Port: host_port, Protocol: corev1.ProtocolTCP, TargetPort: intstr.FromInt(int(host_port))},
				{Name: "jupyter", Protocol: corev1.ProtocolTCP, Port: gui_port, TargetPort: intstr.FromInt(int(gui_port))},
			},
			Selector: labels,
			Type:     corev1.ServiceTypeClusterIP,
		},
	}

	// always set the controller reference so that we know which object owns this.
	if err := ctrl.SetControllerReference(&qkds, &svc, r.Scheme); err != nil {
		return svc, err
	}

	return svc, nil
}

func (r *QKDSimulatorReconciler) desiredManagerIngress(qkds qkdsimv1.QKDSimulator, host_name string, host_port int32, gui_port int32) (networkingv1.Ingress, error) {

	pathType := networkingv1.PathTypePrefix
	annot := make(map[string]string)
	annot["kubernetes.io/ingress.class"] = "traefik"

	svc := networkingv1.Ingress{
		TypeMeta: metav1.TypeMeta{APIVersion: networkingv1.SchemeGroupVersion.String(), Kind: "Ingress"},
		ObjectMeta: metav1.ObjectMeta{
			Annotations: annot,
			Name:        "simmanager-ingress",
			Namespace:   "default",
		},
		Spec: networkingv1.IngressSpec{
			Rules: []networkingv1.IngressRule{
				networkingv1.IngressRule{
					Host: "qkdsim.com",
					IngressRuleValue: networkingv1.IngressRuleValue{
						HTTP: &networkingv1.HTTPIngressRuleValue{
							Paths: []networkingv1.HTTPIngressPath{
								networkingv1.HTTPIngressPath{
									Path:     "/startSimulation",
									PathType: &pathType,
									Backend: networkingv1.IngressBackend{
										Service: &networkingv1.IngressServiceBackend{
											Name: host_name + "-service",
											Port: networkingv1.ServiceBackendPort{
												Number: host_port,
											},
										},
									},
								},
								networkingv1.HTTPIngressPath{
									Path:     "/getTopology",
									PathType: &pathType,
									Backend: networkingv1.IngressBackend{
										Service: &networkingv1.IngressServiceBackend{
											Name: host_name + "-service",
											Port: networkingv1.ServiceBackendPort{
												Number: host_port,
											},
										},
									},
								},
								networkingv1.HTTPIngressPath{
									Path:     "/distributeKeys",
									PathType: &pathType,
									Backend: networkingv1.IngressBackend{
										Service: &networkingv1.IngressServiceBackend{
											Name: host_name + "-service",
											Port: networkingv1.ServiceBackendPort{
												Number: host_port,
											},
										},
									},
								},
								networkingv1.HTTPIngressPath{
									Path:     "/",
									PathType: &pathType,
									Backend: networkingv1.IngressBackend{
										Service: &networkingv1.IngressServiceBackend{
											Name: host_name + "-service",
											Port: networkingv1.ServiceBackendPort{
												Number: gui_port,
											},
										},
									},
								},
							},
						},
					},
				},
			},
		},
	}

	// always set the controller reference so that we know which object owns this.
	if err := ctrl.SetControllerReference(&qkds, &svc, r.Scheme); err != nil {
		return svc, err
	}

	return svc, nil
}

func (r *NetTopologyReconciler) indexOf(element qkdsimv1.Node, data []qkdsimv1.Node) int {
	for k, v := range data {
		if element == v {
			return k
		}
	}
	return -1 //not found.
}

/* Could be useful
func (r *GuestBookReconciler) booksUsingRedis(obj handler.MapObject) []ctrl.Request {
	listOptions := []client.ListOption{
		// matching our index
		client.MatchingField(".spec.redisName", obj.Meta.GetName()),
		// in the right namespace
		client.InNamespace(obj.Meta.GetNamespace()),
	}
	var list webappv1.GuestBookList
	if err := r.List(context.Background(), &list, listOptions...); err != nil {
		// TODO: we should log here!
		return nil
	}
	res := make([]ctrl.Request, len(list.Items))
	for i, book := range list.Items {
		res[i].Name = book.Name
		res[i].Namespace = book.Namespace
	}
	return res
}
*/
