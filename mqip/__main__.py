#!/bin/env python3

import argparse
import configparser
import json5
import datetime
import time
import random

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusIOException, ModbusException, InvalidMessageReceivedException

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

    client.connect()
    result = reader.update(client)
    if result != modbus.UpdateResult.SUCCESSFUL:
        raise RuntimeError("updated failed!")
    else:
        print("connected to modbus")
    client.close()

    interval_minutes = config["mqip"].getint("interval")
    interval = datetime.timedelta(minutes=interval_minutes)
    measurement_name = config["mqip"]["measurement_name"]

    pushers = []

    if "mqtt" in config:
        from mqip.pusher.mqtt import MqttPusher
        pushers.append(MqttPusher(args.config_file))
    if "influx2" in config:
        from mqip.pusher.influxdb import InfluxPusher
        pushers.append(InfluxPusher(args.config_file))

    for pusher in pushers:
        pusher.connect()


    def now() -> datetime.datetime:
        return datetime.datetime.now(datetime.timezone.utc)
    last_timestamp = now().replace(second=0, microsecond=0)

    def close():
        for pusher in pushers:
            pusher.close()

    try:
        while True:
            if now() > last_timestamp + interval:
                timestamp = now().replace(second=0, microsecond=0)
                try:
                    client.connect()
                    result = reader.update(client)
                    if result != modbus.UpdateResult.SUCCESSFUL:
                        close()
                        raise RuntimeError("updated failed!")
                    client.close()
                except (ConnectionException, ModbusIOException, ModbusException, InvalidMessageReceivedException, RuntimeError) as e:
                    # cheap restart delay, since docker compose can't do it on its own...
                    print(f"Exception during update {e}")
                    print(f"waiting waiting 2 min (+ random up to 1 min) before exiting with error")
                    time.sleep(60 * 2)
                    time.sleep(random.randrange(10, 60))
                for pusher in pushers:
                    pusher.push(measurement_name, reader.values, reader.mapped_values, timestamp)
                last_timestamp = timestamp
            time.sleep(0.5)
    except KeyboardInterrupt:
        close()