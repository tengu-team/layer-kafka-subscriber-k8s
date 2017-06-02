import os
import shutil
import re
import yaml
from charms.reactive import when, when_not, hook
from charms.reactive import set_state, remove_state
from charmhelpers.core import hookenv, host, templating, unitdata
from charmhelpers.core.hookenv import open_port, close_port, charm_dir, status_set
from charms.layer.flaskhelpers import start_api, install_requirements, stop_api
from charms.layer.kafkahelper import zookeepers_as_string, brokers_as_string
from charmhelpers.contrib.python.packages import pip_install
try:
    from kubernetes import client
    from kubernetes.client.rest import ApiException
except ImportError:
    pip_install('kubernetes')

config = hookenv.config()
db = unitdata.kv()
project_path = "/home/ubuntu/kafkasubscriber"

@when_not('kafka.configured')
def status_kafka():
    status_set('blocked', 'Waiting for Kafka relation')


@when_not('kube-api.available')
def status_kube():
    status_set('blocked', 'Waiting for kubernetes-api relation')


@when('flask.nginx.installed', 'kafka.configured', 'kube-api.available')
@when_not('kafkasubscriber.installed')
def install(kube):
    hookenv.log("Installing Flask API")
    pkgs = ['requests', 'backoff', 'kazoo']
    for pkg in pkgs:
        pip_install(pkg)
    if os.path.exists('/home/ubuntu/kafkasubscriber'):
        shutil.rmtree('/home/ubuntu/kafkasubscriber')
    shutil.copytree('files/kafkasubscriber', '/home/ubuntu/kafkasubscriber')
    install_requirements(project_path + "/requirements.txt")

    if not os.path.exists('/home/ubuntu/.config/kafkasubscriber'):
        dirs = ['deployments', 'services', 'endpoints']
        for d in dirs:
            os.makedirs('/home/ubuntu/.config/kafkasubscriber/' + d)
            shutil.chown('/home/ubuntu/.config/kafkasubscriber/' + d, user='ubuntu', group='ubuntu')
    
    services = kube.services()
    hookenv.log('SERVICES from kubernetes master')
    hookenv.log(services)
    db.set('k8s-api', services[0]['hosts'][0]['hostname'] 
                      + ':' 
                      + services[0]['hosts'][0]['port'])

    create_k8_zookeeper_service()
    create_k8_kafka_service()

    set_state('kafkasubscriber.installed')


@hook('upgrade-charm')
def upgrade_charm():
    hookenv.log('Upgrading charm')
    remove_state('kafkasubscriber.installed')
    remove_state('kafkasubscriber.stopped')
    remove_state('kafkasubscriber.running')


@when('kafkasubscriber.running')
@when_not('kafka.configured', 'kafkasubscriber.stopped')
def update_status():
    stop_api()
    remove_state('kafkasubscriber.running')
    set_state('kafkasubscriber.stopped')
    status_set('blocked', 'Waiting for Kafka relation')


# k8s key hardcoded, generate of move to config options
@when('kafkasubscriber.installed', 'kafka.configured')
@when_not('kafkasubscriber.running')
def start():
    hookenv.log("Starting API")
    context = {
        'kafka': brokers_as_string(','),
        'k8shost': 'https://' + db.get('k8s-api'),
        'k8skey': 'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJrdWJlcm5ldGVzL3NlcnZpY2VhY2NvdW50Iiwia3ViZXJuZXRlcy5pby9zZXJ2aWNlYWNjb3VudC9uYW1lc3BhY2UiOiJkZWZhdWx0Iiwia3ViZXJuZXRlcy5pby9zZXJ2aWNlYWNjb3VudC9zZWNyZXQubmFtZSI6InN2YTEtdG9rZW4tMHI0NTMiLCJrdWJlcm5ldGVzLmlvL3NlcnZpY2VhY2NvdW50L3NlcnZpY2UtYWNjb3VudC5uYW1lIjoic3ZhMSIsImt1YmVybmV0ZXMuaW8vc2VydmljZWFjY291bnQvc2VydmljZS1hY2NvdW50LnVpZCI6Ijc1OWE1YWNlLTQ0NGYtMTFlNy1iOTc4LTQyMDEwYTg0MDAyMyIsInN1YiI6InN5c3RlbTpzZXJ2aWNlYWNjb3VudDpkZWZhdWx0OnN2YTEifQ.JWPMOWQxlqhD2vuhnxxU03yFn54TzrRk-Yly9nmHNyWkC5JjTRD3q8S-30eO6-MbLB3CZ4IIr2V44_D-RxvLBfOA_PM9CUZ7wnOeGkvi8j4pvks7vzk0ewNIkfGJaYrAFDVcKnsYeTWbhfLYAoJqAeFHNwx5agrMFv8WvDE4CdXsyznlmfYeyUgcxcBKGXcRFyR7ei3di7aUMPRC-flttwO1qOXgvaEqtVOkycXs1ejz8tZZAfb1qcxATgMIIpcusXZGVNA47bixzTsy5ieZ7lqUpv4lTkYfLl_7w2pBlFCjib3fQKQzsSt8BHJ0FntOKUKFaxl8EDI9UIH5eJyKQQ',
        'zookeeper': zookeepers_as_string(',')
    }
    hookenv.log('FLASK CONTEXT')
    hookenv.log(context)
    start_api(project_path + "/server.py", "app", config["flask-port"], 'subscriber.flask.tmpl', context)
    status_set('active', 'Ready')
    remove_state('kafkasubscriber.stopped')
    set_state('kafkasubscriber.running')

@when('kafka.changed', 'kafkasubscriber.running')
def kafka_config_changed():     # Change to gracefull reload and restart pods
    hookenv.log('Kafka config changed, restarting subscriber and consumers')
    start_api(project_path + "/server.py", "app", config["flask-port"])
    remove_state('kafka.changed')


def create_k8_zookeeper_service():
    service_context = {
        'name': 'zookeeper',
        'port': 2181
    }
    zookeepers  = []
    for zoo in db.get('zookeeper'):
        zookeepers.append(zoo['host'])
    endpoints_context = {
        'name': 'zookeeper',
        'port': db.get('zookeeper')[0]['port'],
        'ips': zookeepers
    }
    create_k8s_service('zookeeper', service_context, endpoints_context)


def create_k8_kafka_service():
    service_context = {
        'name': 'kafka',
        'port': 9092
    }
    kafkas = []
    for kafka in db.get('kafka'):
        kafkas.append(kafka['host'])
    endpoints_context = {
        'name': 'kafka',
        'port': db.get('kafka')[0]['port'],
        'ips': kafkas
    }
    create_k8s_service('kafka', service_context, endpoints_context)


# hard coded key !
def create_k8s_service(name, service_context, endpoints_context):
    client.configuration.host = 'https://' + db.get('k8s-api') 
    client.configuration.api_key['authorization'] = 'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJrdWJlcm5ldGVzL3NlcnZpY2VhY2NvdW50Iiwia3ViZXJuZXRlcy5pby9zZXJ2aWNlYWNjb3VudC9uYW1lc3BhY2UiOiJkZWZhdWx0Iiwia3ViZXJuZXRlcy5pby9zZXJ2aWNlYWNjb3VudC9zZWNyZXQubmFtZSI6InN2YTEtdG9rZW4tMHI0NTMiLCJrdWJlcm5ldGVzLmlvL3NlcnZpY2VhY2NvdW50L3NlcnZpY2UtYWNjb3VudC5uYW1lIjoic3ZhMSIsImt1YmVybmV0ZXMuaW8vc2VydmljZWFjY291bnQvc2VydmljZS1hY2NvdW50LnVpZCI6Ijc1OWE1YWNlLTQ0NGYtMTFlNy1iOTc4LTQyMDEwYTg0MDAyMyIsInN1YiI6InN5c3RlbTpzZXJ2aWNlYWNjb3VudDpkZWZhdWx0OnN2YTEifQ.JWPMOWQxlqhD2vuhnxxU03yFn54TzrRk-Yly9nmHNyWkC5JjTRD3q8S-30eO6-MbLB3CZ4IIr2V44_D-RxvLBfOA_PM9CUZ7wnOeGkvi8j4pvks7vzk0ewNIkfGJaYrAFDVcKnsYeTWbhfLYAoJqAeFHNwx5agrMFv8WvDE4CdXsyznlmfYeyUgcxcBKGXcRFyR7ei3di7aUMPRC-flttwO1qOXgvaEqtVOkycXs1ejz8tZZAfb1qcxATgMIIpcusXZGVNA47bixzTsy5ieZ7lqUpv4lTkYfLl_7w2pBlFCjib3fQKQzsSt8BHJ0FntOKUKFaxl8EDI9UIH5eJyKQQ'
    client.configuration.api_key_prefix['authorization'] = 'Bearer'
    client.configuration.verify_ssl = False
    api_client = client.CoreV1Api()

    templating.render(source='k8s.service.tmpl',
                      target='/home/ubuntu/.config/kafkasubscriber/services/' + name + '-service',
                      context=service_context)
    templating.render(source='k8s.endpoints.tmpl',
                      target='/home/ubuntu/.config/kafkasubscriber/endpoints/' + name + '-endpoint',
                      context=endpoints_context)

    try:
        with open('/home/ubuntu/.config/kafkasubscriber/services/zookeeper-service') as f:
            dep = yaml.load(f)
            resp = api_client.create_namespaced_service(body=dep, namespace='default')
            hookenv.log(resp)
        with open('/home/ubuntu/.config/kafkasubscriber/endpoints/zookeeper-endpoint') as f:
            dep = yaml.load(f)
            resp = api_client.create_namespaced_endpoints(body=dep, namespace='default')
            hookenv.log(resp)
    except (IOError, ApiException) as e:
        hookenv.log('Error creating k8s zookeeper service.')
        hookenv.log(e)