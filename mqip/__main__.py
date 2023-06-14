#!/bin/env python3

import argparse
import configparser
import json5
import datetime
import time

from pymodbus.client import ModbusTcpClient

from mqip import modbus

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("config_file")
    args = parser.parse_args()
    config = configparser.ConfigParser()
    with open(args.config_file) as file:
        config.read_file(file)

    with open(config["mqip"]["register_description"]) as file:
        register_description = json5.load(file)

    reader = modbus.RegisterReader(register_description)
    client = ModbusTcpClient(config["mqip"]["host"], port=config["mqip"].getint("port", fallback=502))

    pushers = []

    if "mqtt" in config:
        from mqip.pusher.mqtt import MqttPusher
        pushers.append(MqttPusher(args.config_file))
    if "influx2" in config:
        from mqip.pusher.influxdb import InfluxPusher
        pushers.append(InfluxPusher(args.config_file))

    for pusher in pushers:
        pusher.connect()

    client.connect()

    # TODO
