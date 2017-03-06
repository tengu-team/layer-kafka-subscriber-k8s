#!/bin/bash
if [ -f '/home/ubuntu/kafka-helpers/kafkaip' ] && [ -z "$(ls -A '/home/ubuntu/.config/systemd/user/')" ]; then
	kafkaip=$(cat /home/ubuntu/kafka-helpers/kafkaip)
	for service in $(ls /home/ubuntu/.config/systemd/user/consumer*); do
		"/kafkaip/ s/.*/Environment=\"kafkaip=$kafkaip\"/g" "$service"
	done
	systemctl --user daemon-reload
	for service in $(ls /home/ubuntu/.config/systemd/user/consumer*); do
		systemctl --user start ${service##*/}
	done
fi