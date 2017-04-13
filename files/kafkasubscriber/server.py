import os
import jinja2
import json
from flask import Flask, jsonify, request, abort, Response
from subprocess import call
from kafka import KafkaConsumer, KafkaProducer

app = Flask(__name__)


class configuration(object):
    def __init__(self):
        if os.path.exists('/home/ubuntu/kafka-helpers/kafkaip'):
            with open('/home/ubuntu/kafka-helpers/kafkaip') as f:
                content = f.readline().rstrip()
            self.kafkaip = content.split(',')
            self.kafkaconsumer = KafkaConsumer(bootstrap_servers=self.kafkaip)
            self.kafkaproducer = KafkaProducer(bootstrap_servers=self.kafkaip)

    def configure_kafka(self, kafkaip):
        self.kafkaip = kafkaip

    def start_consumer(self, endpoint, topics):
        self.stop_consumer(endpoint)
        if len(topics) > 0 and topics[0] != "":
            env_vars = [
                "topics={}".format(' '.join(topics)),
                "endpoint={}".format(endpoint),
                "kafkaip={}".format(' '.join(self.kafkaip))
            ]
            self.render(source='/home/ubuntu/kafkasubscriber/templates/unitfile.consumer',
                        target='/home/ubuntu/.config/systemd/user/consumer-' + endpoint + '.service',
                        context={
                            'description': 'Kafka consumer for ' + endpoint,
                            'env_vars': env_vars
                        })
            call(["systemctl", "--user", "enable", "consumer-" + endpoint])
            call(["systemctl", "--user", "start", "consumer-" + endpoint])

    def stop_consumer(self, endpoint):
        if call(["systemctl", "--user", "-q", "is-active", "consumer-" + endpoint]) == 0:  # 0 = active
            call(["systemctl", "--user", "stop", "consumer-" + endpoint])
            call(["systemctl", "--user", "disable", "consumer-" + endpoint])
        if os.path.exists('/home/ubuntu/.config/systemd/user/consumer-' + endpoint + '.service'):
            os.remove('/home/ubuntu/.config/systemd/user/consumer-' + endpoint + '.service')

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


server_config = configuration()


@app.route('/subscribe', methods=['PUT'])
def subscribe():
    if request.json and 'topics' in request.json and 'endpoint' in request.json:
        if not server_config.check_topics(request.json['topics']):
            return jsonify({'status': 400})
        server_config.start_consumer(request.json['endpoint'], request.json['topics'])
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
