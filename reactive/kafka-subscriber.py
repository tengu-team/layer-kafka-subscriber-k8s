import os
import shutil
import re
from charms.reactive import when, when_not, hook
from charms.reactive import set_state, remove_state
from charmhelpers.core import hookenv, host, templating
from charmhelpers.core.hookenv import open_port, close_port, charm_dir, status_set
from charms.layer.flaskhelpers import start_api, install_requirements, stop_api
from charmhelpers.contrib.python.packages import pip_install
from subprocess import call

config = hookenv.config()
project_path = "/home/ubuntu/kafkasubscriber"


@when('flask.nginx.installed')
@when_not('kafkasubscriber.installed')
def install():
    hookenv.log("Installing Flask API")
    pkgs = ['requests', 'backoff']
    for pkg in pkgs:
        pip_install(pkg)
    if os.path.exists('/home/ubuntu/kafkasubscriber'):
        shutil.rmtree('/home/ubuntu/kafkasubscriber')
    shutil.copytree('files/kafkasubscriber', '/home/ubuntu/kafkasubscriber')
    install_requirements(project_path + "/requirements.txt")
    if not os.path.exists('/home/ubuntu/.config'):
        os.makedirs('/home/ubuntu/.config/systemd/user')
        for path in ['/.config', '/.config/systemd', '/.config/systemd/user']:
            shutil.chown('/home/ubuntu' + path, user='ubuntu', group='ubuntu')
    os.chmod('/home/ubuntu/kafkasubscriber/start-consumer.sh', 0o775)
    os.chmod('/home/ubuntu/kafkasubscriber/stop-consumer.sh', 0o775)
    shutil.chown('/home/ubuntu/kafkasubscriber/start-consumer.sh', user='ubuntu', group='ubuntu')
    shutil.chown('/home/ubuntu/kafkasubscriber/stop-consumer.sh', user='ubuntu', group='ubuntu')
    call(['loginctl', 'enable-linger', 'ubuntu'])
    if not os.path.exists('/home/ubuntu/kafka-helpers/kafkaip'):
        status_set('blocked', 'Waiting for Kafka relation')
    else:
        status_set('active', 'Ready')
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


@when('kafkasubscriber.installed', 'kafka.configured')
@when_not('kafkasubscriber.running')
def start():
    hookenv.log("Starting API")
    start_api(project_path + "/server.py", "app", config["flask-port"], 'kafkasub.unitfile')
    status_set('active', 'Ready')
    remove_state('kafkasubscriber.stopped')
    set_state('kafkasubscriber.running')

@when('kafka.changed', 'kafkasubscriber.running')
def kafka_config_changed():
    hookenv.log('Kafka config changed, restarting subscriber and consumers')
    start_api(project_path + "/server.py", "app", config["flask-port"], 'kafkasub.unitfile')
    remove_state('kafka.changed')