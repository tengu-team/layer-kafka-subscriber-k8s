#!/usr/bin/python
import os
import sys
import json
import datetime
import requests
import backoff
import hashlib
from kafka import KafkaConsumer, TopicPartition


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


def create_consumer(kafka, group, replay, topics):
    consumer = KafkaConsumer(bootstrap_servers=kafka, group_id=group)
    if replay == "True":
        ps_array = []
        for topic in topics:
            for partition in consumer.partitions_for_topic(topic):
                ps_array.append(TopicPartition(topic, partition))

        consumer.assign(ps_array)
        consumer.seek_to_beginning()
    else:
        consumer.subscribe(topics=topics)
    return consumer


def main():
    topics = os.environ['topics'].split(' ')
    endpoint = os.environ['endpoint']
    id = hashlib.sha224(endpoint.encode('utf-8')).hexdigest()
    kafkaip = os.environ['kafkaip'].split(' ')
    replay = os.environ['replay']

    consumer = create_consumer(kafkaip, id, replay, topics)

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
        if replay == "True":
            consumer.commit()


if __name__ == '__main__':
    main()
