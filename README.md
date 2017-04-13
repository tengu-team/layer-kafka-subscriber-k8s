# layer-kafka-subscriber
This layer sets up a Flask API to subscribe to Kafka topics. Subscribing to the api can be done via the [kafka-subclient](https://github.com/IBCNServices/layer-kafka-subclient).

# Usage
The layer requires a relation with Apache Kafka.
```
juju deploy kafka-subscriber
juju add-relation kafka-subscriber kafka
```

The layer uses a Flask layer [(repo)](https://github.com/IBCNServices/layer-flask) and defaults to using a gunicorn and nginx deployment for the the Flask API. To suppress this behaviour, deploy the charm with an extra config.yaml with the following content:

```
subscriber:
  nginx: False
```
Deploy via:
```
juju deploy kafka-subscriber subscriber --config config.yaml
```


## HTTP Response
When subscribed to the kafka-subscriber, HTTP POST messages will be sent to the specified endpoint with the following json payload:

```
{
	"topic": "topic_name",
	"subscriberTime": "2017-03-07T14:50:12.584942",
	"message": "Example message"
}
```
Incase the message is json formatted, the payload follows the following format:
```
{
	"topic": "topic_name",
	"subscriberTime": "2017-03-07T14:50:12.584942",
	"message": {
		"attr1": "attr1_value",
		"attr2": "attr2_value"
	}
}
```

A `subscriberTime` is added to every message before it is sent.

## Subscribing without kafka-subclient
The api server can be used to subscribe and unsubscribe by using the following HTTP requests.
`/subscribe` expects a PUT request with a JSON payload containing an array with topics and an endpoint:
```
curl -H "Content-Type: application/json" -X PUT -d '{"topics":["topic1", "topic2"],"endpoint":"x.x.x.x"}' http://subscriberip/subscribe
```
Unsubscribing can be done by sending an empty topics field to subscribe or via `/unsubscribe`:
```
curl -H "Content-Type: application/json" -X DELETE -d '{"endpoint":"x.x.x.x"}' http://subscriberip/unsubscribe
```

## Sending data to Kafka
Sending data to Kafka can be done via POST and a json payload. The payload should indicate if the message is json formatted have the following structure:
```
{
    "message": ... ,
    "json": [true | false]
}
```

Sending to a Kafka topic without key `/kafka/<topic>`:
```
curl -H "Content-Type: application/json" -X POST -d '{"message": {"field1": "value1"}, "json": true}' http://subscriberip/kafka/topic
```
Sending to a Kafka topic with key `/kafka/<topic>/<key>`:
```
curl -H "Content-Type: application/json" -X POST -d '{"message": {"field1": "value1"}, "json": true}' http://subscriberip/kafka/topic/key
```

## Default behaviour
- Subscribing or writing data to a topic that does not exists, results in a 400 response. Even if Kafka auto topic create is configured.


## Authors

This software was created in the [IBCN research group](https://www.ibcn.intec.ugent.be/) of [Ghent University](https://www.ugent.be/en) in Belgium. This software is used in [Tengu](http://tengu.intec.ugent.be), a project that aims to make experimenting with data frameworks and tools as easy as possible.

 - Sander Borny <sander.borny@intec.ugent.be>
 - Crawler icon made by [Freepik](http://www.freepik.com) from [www.flaticon.com](www.flaticon.com) licensed as [Creative Commons BY 3.0](http://creativecommons.org/licenses/by/3.0/)