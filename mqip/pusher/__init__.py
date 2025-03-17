#!/bin/env python3

import datetime
from typing import Optional


class Pusher:

    def __init__(self):
        pass

    def connect(self):
        raise NotImplementedError()

    def close(self):
        raise NotImplementedError()

    def push(self, measurement_name: str, data: dict, mapped_data: dict, timestamp: Optional[datetime.datetime] = None):
        raise NotImplementedError()

class StdoutPusher(Pusher):

    def connect(self):
        pass

    def close(self):
        pass

    def push(self, measurement_name: str, data: dict, mapped_data: dict, timestamp: Optional[datetime.datetime] = None):
        print(measurement_name + ":")
        for key in data:
            if key in mapped_data:
                print(f"    {key}: {data[key]} mapped as {mapped_data[key]}")
            else:
                print(f"    {key}: {data[key]}")
