#!/usr/bin/python
import os
import sys
import json
import urllib.request
import datetime
from kafka import KafkaConsumer

def is_json(myjson):
  try:
    json_object = json.loads(myjson)
  except ValueError:
    return False
  return True

def main():
    topics = tuple(filter(None, os.environ['topics'].split(' ')))
    endpoint = os.environ['endpoint']
    kafkaip = os.environ['kafkaip']

    consumer = KafkaConsumer(bootstrap_servers=kafkaip, group_id=endpoint)
    consumer.subscribe(topics=topics)

    if not endpoint.startswith('http://'):
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
        params = json.dumps(msg_dict).encode('utf-8')
        req = urllib.request.Request(endpoint, data=params, headers={'content-type': 'application/json'})
        response = urllib.request.urlopen(req)

if __name__ == '__main__':
    main()