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
