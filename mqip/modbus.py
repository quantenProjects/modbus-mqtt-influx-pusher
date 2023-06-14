#!/bin/env python3

import argparse
import time
import json5

from enum import Enum
from typing import Any

from pymodbus.client import mixin, ModbusTcpClient
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder


Values = dict[str, Any]


class UpdateResult(Enum):
    SUCCESSFUL = 0
    FAILURE = 1


class RegisterBatch:

    def __init__(self, register_description: dict, name_list: list[str]):
        self.register_description = register_description
        self.name_list = name_list

        self._raw_values: Values = {}

        self.addr = register_description[name_list[0]]["address"]
        self.count = register_description[name_list[-1]]["address"] - self.addr + register_description[name_list[-1]]["length"]

    def clear(self):
        self._raw_values = {}

    def update(self, client: mixin.ModbusClientMixin) -> UpdateResult:
        self.clear()
        registers = client.read_input_registers(self.addr, self.count).registers
        decoder = BinaryPayloadDecoder.fromRegisters(registers, byteorder=Endian.Big, wordorder=Endian.Little)
        for i, name in enumerate(self.name_list):
            value = None
            type = self.register_description[name]["type"]
            length = self.register_description[name]["length"]
            if i > 0:
                skip_words = self.register_description[name]["address"] - self.register_description[self.name_list[i - 1]]["address"] - self.register_description[self.name_list[i - 1]]["length"]
                if skip_words > 0:
                    decoder.skip_bytes(skip_words * 2)
            if type == "int":
                if length == 1:
                    value = decoder.decode_16bit_int()
                elif length == 2:
                    value = decoder.decode_32bit_int()
            elif type == "uint":
                if length == 1:
                    value = decoder.decode_16bit_uint()
                elif length == 2:
                    value = decoder.decode_32bit_uint()
            if value is None:
                raise ValueError("register descriptions contains unknown data types")
            self._raw_values[name] = value
        return UpdateResult.SUCCESSFUL

    @property
    def raw_values(self) -> Values:
        return self._raw_values


class RegisterReader:

    def __init__(self, register_description: dict):
        self.register_description = register_description
        self.batches: list[RegisterBatch] = []
        self._values: Values = {}
        self._mapped_values: Values = {}

        def name_to_address(name: str) -> int:
            return register_description[name]["address"]

        def check_if_names_are_okay_for_a_batch(name_list: list[str]) -> bool:
            assert sorted(name_list, key=name_to_address) == name_list
            length = name_to_address(name_list[-1]) - name_to_address(name_list[0]) + register_description[name_list[-1]]["length"]
            return length <= 100

        names_sorted_by_addr = list(sorted(register_description.keys(), key=name_to_address))
        start_index = 0
        for i in range(1, len(names_sorted_by_addr) + 1):
            if i >= len(names_sorted_by_addr) or not check_if_names_are_okay_for_a_batch(names_sorted_by_addr[start_index:i + 1]):
                self.batches.append(RegisterBatch(register_description, names_sorted_by_addr[start_index: i]))
                start_index = i

    def clear(self):
        self._values = {}
        self._mapped_values = {}

    def update(self, client: mixin.ModbusClientMixin, request_pause: float = 1) -> UpdateResult:
        self.clear()
        for i, batch in enumerate(self.batches):
            if i > 0:
                time.sleep(request_pause)
            result = batch.update(client)
            if result != UpdateResult.SUCCESSFUL:
                self.clear()  # clear not complete values
                return UpdateResult.FAILURE
            for value_name in batch.raw_values:
                value = batch.raw_values[value_name]
                this_register_description = self.register_description[value_name]
                if "factor" in this_register_description:
                    value = value * this_register_description["factor"]
                self._values[value_name] = value
                if "mapping" in this_register_description:
                    key = str(value)
                    if key in this_register_description["mapping"]:
                        self._mapped_values[value_name] = this_register_description["mapping"][key]
        return UpdateResult.SUCCESSFUL

    @property
    def mapped_values(self) -> Values:
        return self._mapped_values

    @property
    def values(self) -> Values:
        return self._values


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("register_description")
    parser.add_argument("host")
    parser.add_argument("--port", default=502, type=int)
    args = parser.parse_args()

    with open(args.register_description) as file:
        register_description = json5.load(file)

    client = ModbusTcpClient(args.host, args.port)

    reader = RegisterReader(register_description)
    reader.update(client)

    for value_name in reader.values:
        print(f"{value_name + ':' :25} {reader.values[value_name]:>10} {register_description[value_name]['unit']}", f"{reader.mapped_values[value_name]}" if value_name in reader.mapped_values else "")

    client.close()
