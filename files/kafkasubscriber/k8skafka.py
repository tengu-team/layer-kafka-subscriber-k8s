import os
import yaml
from kubernetes import client
from kubernetes.client.rest import ApiException


class K8sKafka(object):

    def __init__(self, host, key, namespace='default'):
        if not host.startswith('https'):
            host = 'https://' + host
        client.configuration.host = host
        client.configuration.api_key['authorization'] = key
        client.configuration.api_key_prefix['authorization'] = 'Bearer'
        client.configuration.verify_ssl = False
        self.api_instance = client.AppsV1beta1Api()
        self.namespace = namespace

    def create_deployment(self, file):
        try:
            with open(file) as f:
                dep = yaml.load(f)
                resp = self.api_instance.create_namespaced_deployment(body=dep, namespace=self.namespace)
                return True 
        except (IOError, ApiException) as e:
            return False

    def replace_deployment_dict(self, dep):
        try:
            resp = self.api_instance.replace_namespaced_deployment(name=dep['metadata']['name'],
                                                                   namespace=self.namespace,
                                                                   body=dep)
            return True
        except ApiException as e:
            return False

    def delete_deployment(self, file):
        try:
            with open(file) as f:
                dep = yaml.load(f)
                dep['spec']['replicas'] = 0
                if self.replace_deployment_dict(dep):
                    body = client.V1DeleteOptions()
                    body.propagation_policy = 'Background'
                    resp = self.api_instance.delete_namespaced_deployment(dep['metadata']['name'],
                                                                         self.namespace, 
                                                                         body, 
                                                                         grace_period_seconds=0)
                    return True
            return False
        except (IOError, ApiException) as e:
            return False
