#!/bin/bash

if [ -z "$(ls -A '/home/ubuntu/.config/systemd/user/')" ]; then
	for service in $(ls /home/ubuntu/.config/systemd/user/consumer*); do
		systemctl --user stop ${service##*/}
	done
fi