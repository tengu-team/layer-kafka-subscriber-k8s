#!/bin/bash
if [ -f '/home/ubuntu/kafka-helpers/kafkaip' ] && [ "$(ls -A '/home/ubuntu/.config/systemd/user/')" ]; then
	kafka=$(while read line
			do
			  echo -n "{line} "
			done < /home/ubuntu/kafka-helpers/kafkaip)
	kafkaip=$(echo -e "${kafka}" | sed -e 's/[[:space:]]*$//')
	for service in $(ls /home/ubuntu/.config/systemd/user/consumer*); do
		"/kafkaip/ s/.*/Environment=\"kafkaip=$kafkaip\"/g" "$service"
	done
	systemctl --user daemon-reload
	for service in $(ls /home/ubuntu/.config/systemd/user/consumer*); do
		systemctl --user start ${service##*/}
	done
fi