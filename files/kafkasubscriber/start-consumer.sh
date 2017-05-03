#!/bin/bash
if [ -f '/home/ubuntu/kafka-helpers/kafkaip' ] && [ "$(ls -A '/home/ubuntu/.config/systemd/user/')" ]; then
	#Update Kafka broker info
	#Rewrite consumers that started from earliest offset
	kafka=$(tr , " " < /home/ubuntu/kafka-helpers/kafkaip)
	kafkaip=$(echo -e "${kafka}" | sed -e 's/[[:space:]]*$//')
	for service in $(ls /home/ubuntu/.config/systemd/user/consumer*); do
		sed -i "/kafkaip/ s/.*/Environment=\"kafkaip=$kafkaip\"/g" "$service"
		sed -i "/replay=True/ s/.*/Environment=\"replay=False\"/g" "$service"
	done
	
	systemctl --user daemon-reload
	for service in $(ls /home/ubuntu/.config/systemd/user/consumer*); do
		systemctl --user start ${service##*/}
	done
fi