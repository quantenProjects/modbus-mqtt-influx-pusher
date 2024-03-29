#!/bin/env python3

from mqip.pusher import Pusher

import paho.mqtt.client as mqtt

import datetime
from typing import Optional
import configparser


class MqttPusher(Pusher):

    def __init__(self, config_filename: str):
        self.config_filename = config_filename
        self.config = configparser.ConfigParser()
        with open(config_filename) as file:
            self.config.read_file(file)
        self.topic_prefix = self.config["mqtt"]["topic_prefix"]
        self.client: Optional[mqtt.Client] = None
        super().__init__()

    def connect(self):
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        if "ca_cert" in self.config["mqtt"]:
            self.client.tls_set(ca_certs=self.config["mqtt"]["ca_cert"], certfile=self.config["mqtt"]["cert"], keyfile=self.config["mqtt"]["key"])
        if "username" in self.config["mqtt"]:
            self.client.username_pw_set(self.config["mqtt"]["username"], self.config["mqtt"]["password"])
        self.client.connect(self.config["mqtt"]["host"], self.config["mqtt"].getint("port"))
        self.client.loop_start()

    def push(self, measurement_name: str, data: dict, mapped_data: dict, timestamp: Optional[datetime.datetime] = None):
        for value_name in data:
            self.client.publish(self.topic_prefix + "/" + measurement_name + "/" + value_name, data[value_name])
        for value_name in mapped_data:
            self.client.publish(self.topic_prefix + "/" + measurement_name + "/" + value_name + "/mapped", mapped_data[value_name])

    def close(self):
        self.client.disconnect()
