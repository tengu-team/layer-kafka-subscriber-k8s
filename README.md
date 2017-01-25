# layer-kafka-subscriber
This layer sets up a Flask API to subscribe to Kafka topics.

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
When subscribed to the kafka-subscriber HTTP POST messages will be send to the specified endpoint with a json payload with the following format:

```
{
	"topic": "topic_name",
	"message": "Example message"
}
```
Incase the message is json formatted, the payload follows the following format:
```
{
	"topic": "topic_name",
	"message": {
		"attr1": "attr1_value",
		"attr2": "attr2_value"
	}
}
```


## Authors

This software was created in the [IBCN research group](https://www.ibcn.intec.ugent.be/) of [Ghent University](http://www.ugent.be/en) in Belgium. This software is used in [Tengu](http://tengu.intec.ugent.be), a project that aims to make experimenting with data frameworks and tools as easy as possible.

 - Sander Borny <sander.borny@intec.ugent.be>