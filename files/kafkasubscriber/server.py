import os
import jinja2
import json
import hashlib
from flask import Flask, jsonify, request, abort, Response
from kafka import KafkaConsumer, KafkaProducer
from k8skafka import K8sKafka
from kazoo.client import KazooClient

app = Flask(__name__)


class configuration(object):
    def __init__(self):
        self.kafkaip = os.environ['kafka'].split(',')
        self.kafkaconsumer = KafkaConsumer(bootstrap_servers=self.kafkaip)
        self.kafkaproducer = KafkaProducer(bootstrap_servers=self.kafkaip)
        self.k8s = K8sKafka(os.environ['k8shost'], os.environ['k8skey'])
        self.zk = KazooClient(hosts=os.environ['zookeeper'])

    def configure_kafka(self, kafkaip):
        self.kafkaip = kafkaip

    def start_consumer(self, endpoint, topics, status, pods):
        self.stop_consumer(endpoint)
        if len(topics) > 0 and topics[0] != "":
            id = hashlib.sha224(endpoint.encode('utf-8')).hexdigest()
            zk_node = self.create_zk_node(id, status)
            env_vars = {
                "topics": ' '.join(topics),
                "endpoint": endpoint,
                "zoopath": zk_node
            }
            context = {
                'env_vars': env_vars,
                'name': 'dep-' + id,
                'replicas': pods,
                'podisfor': id,
                'cname': 'kafka-sub-consumer',
                'image': 'sborny/kafka-subscriber',
                #'imagesecret': 'regsecret'
            }
            self.render('/home/ubuntu/kafkasubscriber/templates/deployment.tmpl',
                        context,
                        '/home/ubuntu/.config/kafkasubscriber/deployments/dep-' + id + '.yaml')
            self.k8s.create_deployment('/home/ubuntu/.config/kafkasubscriber/deployments/dep-' + id + '.yaml')

    def stop_consumer(self, endpoint):
        id = hashlib.sha224(endpoint.encode('utf-8')).hexdigest()
        # Stop pods
        path = '/home/ubuntu/.config/kafkasubscriber/deployments/dep-' + id + '.yaml'
        if os.path.exists(path) and self.k8s.delete_deployment(path):
            os.remove(path)

    def render(self, source, context, target):
        path, filename = os.path.split(source)
        with open(target, 'w+') as f:
            f.write(jinja2.Environment(
                loader=jinja2.FileSystemLoader(path or './')
            ).get_template(filename).render(context))

    def check_topics(self, topics):
        server_topics = self.kafkaconsumer.topics()
        for topic in topics:
            if topic not in server_topics:
                return False
        return True

    def send_to_kafka(self, topic, msg, json_message):
        if json_message:
            try:
                self.kafkaproducer.send(topic, json.dumps(msg).encode('utf-8'))
            except ValueError as e:
                abort(400)
        else:
            self.kafkaproducer.send(topic, msg.encode('utf-8'))

    def send_to_kafka_key(self, topic, msg, json_message, key):
        if json_message:
            try:
                self.kafkaproducer.send(topic, key=key.encode('utf-8'), value=json.dumps(msg).encode('utf-8'))
            except ValueError as e:
                abort(400)
        else:
            self.kafkaproducer.send(topic, key=key.encode('utf-8'), value=msg.encode('utf-8'))

    def partition_count(self, topic):
        return len(self.kafkaconsumer.partitions_for_topic(topic))

    def create_zk_node(self, id, status):
        self.zk.start()
        self.zk.ensure_path("/kafkasubscriber/consumers/" + id)
        self.zk.set("/kafkasubscriber/consumers/" + id, status.encode('utf-8'))
        self.zk.stop()
        return "/kafkasubscriber/consumers/" + id


server_config = configuration()


@app.route('/subscribe', methods=['PUT'])
def subscribe():
    if request.json and 'topics' in request.json and 'endpoint' in request.json:
        if not server_config.check_topics(request.json['topics']):
            return jsonify({'status': 400})
        status = request.json['offset'] if 'offset' in request.json else 'continue'
        pods = 1 
        if 'pods' in request.json:
            max_pods = server_config.partition_count(request.json['topic'])
            pods = int(request.json['pods']) if request.json['pods'] <= max_pods else 1    
        server_config.start_consumer(request.json['endpoint'], request.json['topics'], status, pods)
    else:
        abort(400)
    return jsonify({'status': 200})


@app.route('/unsubscribe', methods=['DELETE'])
def unsubscribe():
    if request.json and 'endpoint' in request.json:
        server_config.stop_consumer(request.json['endpoint'])
    else:
        abort(400)
    return jsonify({'status': 200})


@app.route('/ping', methods=['GET'])
def ping():
    resp = Response("pong")
    return resp


@app.route('/kafka/<topic>', methods=['POST'])
def write_to_kafka(topic):    
    if not server_config.check_topics([topic]) \
       or not request.json \
       or not 'message' in request.json \
       or not 'json' in request.json:
        abort(400)
    server_config.send_to_kafka(topic, request.json['message'], request.json['json'])
    return jsonify({'status': 200})


@app.route('/kafka/<topic>/<key>', methods=['POST'])
def write_to_kafka_key(topic, key):
    if not server_config.check_topics([topic]) \
       or not request.json \
       or not 'message' in request.json \
       or not 'json' in request.json:
        abort(400)
    server_config.send_to_kafka_key(topic, request.json['message'], request.json['json'], key)
    return jsonify({'status': 200})


if __name__ == "__main__":
    app.run()
