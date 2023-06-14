#!/bin/env python3

from mqip.pusher import Pusher

from influxdb_client import InfluxDBClient, Point

import datetime
from typing import Optional
import configparser


class InfluxPusher(Pusher):

    def __init__(self, config_filename: str):
        self.config_filename = config_filename
        self.config = configparser.ConfigParser()
        with open(config_filename) as file:
            self.config.read_file(file)
        self.bucket = self.config["influx2"]["bucket"]
        self.client = None
        self.write_api = None
        super().__init__()

    def connect(self):
        self.client = InfluxDBClient.from_config_file(self.config_filename)
        self.write_api = self.client.write_api()

    def push(self, measurement_name: str, data: dict, mapped_data: dict, timestamp: Optional[datetime.datetime] = None):
        point = Point(measurement_name)
        for value_name in data:
            point = point.field(value_name, data[value_name])
        for value_name in mapped_data:
            point = point.field(value_name + "_mapped", mapped_data[value_name])
        if timestamp is not None:
            timestamp = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
        point = point.time(timestamp)
        self.write_api.write(point=point, bucket=self.bucket)
        self.write_api.flush()

    def close(self):
        self.client.close()
