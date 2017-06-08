import os
import shutil
import yaml
from charms.reactive import when, when_not, hook
from charms.reactive import set_state, remove_state
from charmhelpers.core import hookenv, templating, unitdata
from charmhelpers.core.hookenv import status_set
from charms.layer.flaskhelpers import (start_api,
                                       install_requirements,
                                       stop_api,
                                       gracefull_reload)
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
project_k8s_path = "/home/ubuntu/.config/kafkasubscriber"


@when_not('kafka.configured')
def status_kafka():
    stop_api()
    remove_state('kafkasubscriber.running')
    status_set('blocked', 'Waiting for Kafka relation')


@when_not('kube-api.available')
def status_kube():
    stop_api()
    remove_state('kafkasubscriber.running')
    status_set('blocked', 'Waiting for kubernetes-api relation')


@when('kafka.configured', 'kube-api.available')
@when_not('kafkasubscriber.configured')
def status_configured(kube):
    stop_api()
    remove_state('kafkasubscriber.running')
    status_set('blocked', 'Waiting for k8skey')


@when('kafka.configured', 'kube-api.available', 'config.changed.k8skey')
def config_changed_k8skey(kube):
    if config['k8skey']:
        set_state('kafkasubscriber.configured')
    else:
        remove_state('kafkasubscriber.configured')


@when('flask.nginx.installed',
      'kafkasubscriber.configured',
      'kube-api.available',
      'kafka.configured')
@when_not('kafkasubscriber.installed')
def install(kube):
    hookenv.log("Installing Flask API")
    if os.path.exists('/home/ubuntu/kafkasubscriber'):
        shutil.rmtree('/home/ubuntu/kafkasubscriber')
    shutil.copytree('files/kafkasubscriber', '/home/ubuntu/kafkasubscriber')
    install_requirements(project_path + "/requirements.txt")

    if not os.path.exists(project_k8s_path):
        dirs = ['deployments', 'services', 'endpoints']
        for d in dirs:
            os.makedirs(project_k8s_path + '/' + d)
            shutil.chown(project_k8s_path + '/' + d,
                         user='ubuntu',
                         group='ubuntu')

    services = kube.services()
    db.set('k8s-api', services[0]['hosts'][0]['hostname']
                      + ':'
                      + services[0]['hosts'][0]['port'])
    create_k8_kafka_service()
    set_state('kafkasubscriber.installed')


@hook('upgrade-charm')
def upgrade_charm():
    hookenv.log('Upgrading charm')
    remove_state('kafkasubscriber.installed')
    remove_state('kafkasubscriber.stopped')
    remove_state('kafkasubscriber.running')


@when('kafkasubscriber.installed', 'kafka.configured')
@when_not('kafkasubscriber.running')
def start():
    hookenv.log("Starting API")
    context = {
        'kafka': brokers_as_string(','),
        'k8shost': 'https://' + db.get('k8s-api'),
        'k8skey': config['k8skey'],
        'zookeeper': zookeepers_as_string(',')
    }
    hookenv.log('FLASK CONTEXT')
    hookenv.log(context)
    start_api(project_path + "/server.py",
              "app",
              config["flask-port"],
              'subscriber.flask.tmpl',
              context)
    status_set('active', 'Ready')
    remove_state('kafkasubscriber.stopped')
    set_state('kafkasubscriber.running')


@when('kafka.changed', 'kafkasubscriber.running')
def kafka_config_changed():
    hookenv.log('Kafka config changed, restarting subscriber and consumers')
    create_k8_kafka_service()
    gracefull_reload()
    remove_state('kafka.changed')


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


def create_k8s_service(name, service_context, endpoints_context):
    client.configuration.host = 'https://' + db.get('k8s-api')
    client.configuration.api_key['authorization'] = config['k8skey']
    client.configuration.api_key_prefix['authorization'] = 'Bearer'
    client.configuration.verify_ssl = False
    api_client = client.CoreV1Api()

    templating.render(source='k8s.service.tmpl',
                      target= project_k8s_path + '/services/' + name + '-service',
                      context=service_context)
    templating.render(source='k8s.endpoints.tmpl',
                      target=project_k8s_path + '/endpoints/' + name + '-endpoint',
                      context=endpoints_context)

    try:
        with open(project_k8s_path + '/services/zookeeper-service') as f:
            dep = yaml.load(f)
            resp = api_client.create_namespaced_service(body=dep, namespace='default')
            hookenv.log(resp)
        with open(project_k8s_path + '/endpoints/zookeeper-endpoint') as f:
            dep = yaml.load(f)
            resp = api_client.create_namespaced_endpoints(body=dep, namespace='default')
            hookenv.log(resp)
    except (IOError, ApiException) as e:
        hookenv.log('Error creating k8s zookeeper service.')
        hookenv.log(e)
