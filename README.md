
# layer-kafka-subscriber-k8s

Kafka REST API which creates consumers in a kubernetes cluster. 

Layers required to build this charm: 
 - [kafka-helper](https://github.com/tengu-team/layer-kafka-helper)
 - [flask](https://github.com/tengu-team/layer-flask)
 
 ## Setup
 
 This charm requires a relation to [Kafka](https://jujucharms.com/kafka/) and the [Kubernetes](https://jujucharms.com/canonical-kubernetes/) master node. 
 ```
 juju deploy ./kafka-subscriber-k8s --series xenial subscriber
 juju add-relation subscriber kafka
 juju add-relation subscriber kubernetes-master
 ```
 Creating new pods and deployments on Kubernetes requires a service account.
 Service account can be created via:
 ```
 kubectl create serviceaccount (NAME)
 kubectl get serviceaccounts (NAME) -o yaml
 ```
 The outputted yaml will contain the secret name used to fetch the bearer token. This token will be used as `k8skey` config parameter. The token value can be recovered via the kubernetes Dashboard (Config -> Secrets) or manually via:
 ```
 kubectl get secret (SECRET_NAME) -o yaml
   apiVersion: v1
   data:
    ca.crt: (APISERVER'S CA BASE64 ENCODED)
    token: (BEARER TOKEN BASE64 ENCODED)     <-- 
    
 echo (BEARER TOKEN) | base64 --decode
 
 juju config subscriber "k8skey=(BEARER_TOKEN)"
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
If the message is json formatted, the payload has the following format:
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
 
## Subscribing
The api server can be used to subscribe and unsubscribe by using the following HTTP requests.
`/subscribe` expects a PUT request with a JSON payload containing an array with topics and an endpoint:
```
curl -H "Content-Type: application/json" -X PUT -d '{"topics":["topic1", "topic2"],"endpoint":"x.x.x.x"}' http://subscriberip/subscribe
```
The POST request has two optional fields `replay` and `pods`.
### Replay
`replay` can be set to `true` or `false`. Default value is `false`.

For example replaying a topic can be done by sending the following request:
```
curl -H "Content-Type: application/json" -X PUT -d '{"topics":["topic1"],"endpoint":"x.x.x.x", "replay": true}' http://subscriberip/subscribe
```
### Pods
The number of pods can be set via the `pods` field. The number of pods reflects to total number of consumers in a single consumer group. Setting this value higher than the number of partitions in the topic will have no performance gain. When no pods value is set, this will default to 1 pod. Setting the pods value can be done via:
```
curl -H "Content-Type: application/json" -X PUT -d '{"topics":["topic1"],"endpoint":"x.x.x.x", "pods": 2}' http://subscriberip/subscribe
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
- Replaying a topic will start from the earliest available offset and will keep running, eventually behaving like a normal subscribe request.
- Requesting a replay of a topic and resending a subscribe request, with the same endpoint and topics, will start sending messages where the last replay request was stopped.
- Replaying from a multiple partitioned topic does not guarantee order.

## Authors

This software was created in the [IBCN research group](https://www.ibcn.intec.ugent.be/) of [Ghent University](https://www.ugent.be/en) in Belgium. This software is used in [Tengu](http://tengu.intec.ugent.be), a project that aims to make experimenting with data frameworks and tools as easy as possible.

 - Sander Borny <sander.borny@intec.ugent.be>
 - Crawler icon made by [Freepik](http://www.freepik.com) from [www.flaticon.com](www.flaticon.com) licensed as [Creative Commons BY 3.0](http://creativecommons.org/licenses/by/3.0/)
 
