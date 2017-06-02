#!/usr/bin/python
import os
import json
import datetime
import requests
import backoff
import hashlib
from kafka import KafkaConsumer, TopicPartition
from kafka.errors import BrokerNotAvailableError
from kazoo.client import KazooClient


def read_zookeeper(zooport, zoopath):   # exception handling
    zk = KazooClient(hosts='zookeeper:' + zooport, timeout=60)
    zk.start()
    if zk.exists(zoopath):
        value, stat = zk.get(zoopath)
        value = value.decode('utf-8')
    else:
        value = 'continue'
    zk.stop()
    return value


def update_zookeeper(zooport, zoopath):   # exception handling
    zk = KazooClient(hosts='zookeeper:' + zooport, timeout=60)
    zk.start()
    zk.create(zoopath, b'continue', makepath=True)  ## set?
    zk.stop()


def is_json(myjson):
    try:
        json_object = json.loads(myjson)
    except ValueError:
        return False
    return True


@backoff.on_exception(backoff.expo, requests.exceptions.RequestException, max_value=32)
def send(endpoint, data):
    r = requests.post(endpoint, json=data)
    r.raise_for_status()


def create_consumer(kafka, group, status, topics):
    try:
        consumer = KafkaConsumer(bootstrap_servers=kafka, group_id=group)
    except BrokerNotAvailableError:
        create_consumer(kafka, group, status, topics)
    if status != 'continue':
        ps_array = []
        for topic in topics:
            for partition in consumer.partitions_for_topic(topic):
                ps_array.append(TopicPartition(topic, partition))
        consumer.assign(ps_array)
        if status == 'earliest':
            consumer.seek_to_beginning()
        else:
            consumer.seek_to_end()
    else:
        consumer.subscribe(topics=topics)
    return consumer


def main():
    topics = os.environ['topics'].split(' ')
    endpoint = os.environ['endpoint']
    id = hashlib.sha224(endpoint.encode('utf-8')).hexdigest()
    kafkaip = os.environ['kafkaip'].split(' ')
    zooport = os.environ['zooport']
    zoopath = os.environ['zoopath']

    status = read_zookeeper(zooport, zoopath)

    consumer = create_consumer(kafkaip, id, status, topics)
    update_zookeeper(zooport, zoopath)
    if not endpoint.startswith('http'):
        endpoint = 'http://' + endpoint

    for msg in consumer:
        msg_value = msg.value.decode('utf-8')
        msg_dict = {}
        msg_dict['topic'] = msg.topic
        msg_dict['subscriberTime'] = datetime.datetime.now().isoformat()
        if is_json(msg_value):
            msg_dict['message'] = json.loads(msg_value)
        else:
            msg_dict['message'] = msg_value
        send(endpoint, msg_dict)
        if status != 'continue':
            consumer.commit()


if __name__ == '__main__':
    main()
