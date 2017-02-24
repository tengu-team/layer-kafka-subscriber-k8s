import os
import shutil
from charms.reactive import when, when_not, hook
from charms.reactive import set_state, remove_state
from charmhelpers.core import hookenv, host, templating
from charmhelpers.core.hookenv import open_port, close_port, charm_dir, status_set
from charms.layer.flaskhelpers import start_api, install_requirements, stop_api
from subprocess import call

config = hookenv.config()
project_path = "/home/ubuntu/kafkasubscriber"

@when('flask.nginx.installed')
@when_not('kafkasubscriber.installed')
def install():
    hookenv.log("Installing Flask API")    
    if os.path.exists('/home/ubuntu/kafkasubscriber'):
        shutil.rmtree('/home/ubuntu/kafkasubscriber')
    shutil.copytree('files/kafkasubscriber', '/home/ubuntu/kafkasubscriber')
    install_requirements(project_path + "/requirements.txt")
    if not os.path.exists('/home/ubuntu/.config'):
        os.makedirs('/home/ubuntu/.config/systemd/user')
        for path in ['/.config', '/.config/systemd', '/.config/systemd/user']:
            shutil.chown('/home/ubuntu' + path, user='ubuntu', group='ubuntu')
    status_set('blocked', 'Waiting for Kafka relation')
    set_state('kafkasubscriber.installed')

@hook('upgrade-charm')
def upgrade_charm():
    hookenv.log('Upgrading charm')
    remove_state('kafkasubscriber.installed')

@when('kafkasubscriber.running')
@when_not('kafka.configured', 'kafkasubscriber.stopped')
def update_status():
    stop_api()
    consumers("stop")
    remove_state('kafkasubscriber.running')
    set_state('kafkasubscriber.stopped')
    status_set('blocked', 'Waiting for Kafka relation')

def consumers(action):
    for service in os.listdir('/home/ubuntu/.config/systemd/user'):
        call(["systemctl", "--user", action, service])

@when('kafkasubscriber.installed', 'flask.nginx.installed', 'kafka.configured')
@when_not('kafkasubscriber.running')
def start():
    hookenv.log("Starting API")    
    consumers("start")
    start_api(project_path + "/server.py", "app", config["flask-port"])
    status_set('active', 'Ready')
    set_state('kafkasubscriber.running')

@when('kafka.joined')
@when_not('kafka.configured')
def configure_kafka(kafka):
    if kafka.kafkas():
        hookenv.log("Kafka relation found")
        open(project_path + '/kafkaip', 'w+').close()
        configure_kafka_info(kafka)
        set_state('kafka.configured')

def configure_kafka_info(kafka):
    templating.render(
        source='kafka.connect',
        target= project_path + '/kafkaip',
        context={
            'kafkas': kafka.kafkas(),
        }
    )

@when('kafka.configured')
@when_not('kafka.joined')
def remove_kafka():
    hookenv.log("Kafka relation removed")
    if os.path.exists(project_path + '/kafkaip'):
        os.remove(project_path + '/kafkaip')
    remove_state('kafka.configured')