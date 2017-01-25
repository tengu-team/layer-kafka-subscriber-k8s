import os
import tarfile

from charms.reactive import when, when_not, hook
from charms.reactive import set_state, remove_state
from charmhelpers.core import hookenv, host, templating
from charmhelpers.core.hookenv import open_port, close_port, charm_dir, status_set

from charms.layer.flaskhelpers import start_api, install_dependencies

from subprocess import call

config = hookenv.config()
hooks = hookenv.Hooks()

project_path = "/home/ubuntu/kafkasubscriber"

@when_not('kafkasubscriber.installed')
def install():
	hookenv.log("Installing Flask API")	
	tfile = tarfile.open("files/kafkasubscriber.tar.gz", 'r:gz')
	tfile.extractall('/home/ubuntu')	
	install_dependencies(project_path + "/wheelhouse", project_path + "/requirements.txt")
	status_set('blocked', 'Waiting for Kafka relation')
	set_state('kafkasubscriber.installed')

@when('kafkasubscriber.installed', 'flask.installed')
@when_not('kafka.configured')
def update_status():
	status_set('blocked', 'Waiting for Kafka relation')


@when('kafkasubscriber.installed', 'flask.installed', 'kafka.configured')
@when_not('kafkasubscriber.started')
def start():
	hookenv.log("Starting API")	
	start_api(project_path + "/server.py", "app", config["flask-port"])
	status_set('active', 'Ready')
	set_state('kafkasubscriber.started')

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