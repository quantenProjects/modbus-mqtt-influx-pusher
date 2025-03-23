#!/bin/env python3

import argparse
import time
import json5

from enum import Enum
from typing import Any, Optional

from pymodbus.client import mixin, ModbusTcpClient
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.exceptions import ModbusIOException


Values = dict[str, Any]


class UpdateResult(Enum):
    SUCCESSFUL = 0
    FAILURE = 1


class RegisterBatch:

    def __init__(self, register_description: dict, name_list: list[str], byteorder: Endian, wordorder: Endian):
        self.register_description = register_description
        self.name_list = name_list

        self._raw_values: Values = {}

        self.addr = register_description[name_list[0]]["address"]
        self.count = register_description[name_list[-1]]["address"] - self.addr + register_description[name_list[-1]]["length"]
        self.byteorder = byteorder
        self.wordorder = wordorder

    def clear(self):
        self._raw_values = {}

    def update(self, client: mixin.ModbusClientMixin, slave_id: Optional[int] = None) -> UpdateResult:
        self.clear()
        if slave_id is None:
            result = client.read_input_registers(self.addr, self.count)
        else:
            result = client.read_input_registers(self.addr, self.count, slave=slave_id)
        if isinstance(result, ModbusIOException):
            return UpdateResult.FAILURE
        registers = result.registers
        decoder = BinaryPayloadDecoder.fromRegisters(registers, byteorder=self.byteorder, wordorder=self.wordorder)
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
                elif length == 4:
                    value = decoder.decode_64bit_int()
            elif type == "uint":
                if length == 1:
                    value = decoder.decode_16bit_uint()
                elif length == 2:
                    value = decoder.decode_32bit_uint()
                elif length == 4:
                    value = decoder.decode_64bit_uint()
            elif type == "float":
                if length == 1:
                    value = decoder.decode_16bit_float()
                elif length == 2:
                    value = decoder.decode_32bit_float()
                elif length == 4:
                    value = decoder.decode_64bit_float()
            if value is None:
                raise ValueError("register descriptions contains unknown data types")
            self._raw_values[name] = value
        return UpdateResult.SUCCESSFUL

    @property
    def raw_values(self) -> Values:
        return self._raw_values


class RegisterReader:

    def __init__(self, register_description: dict, wordorder: str, byteorder: str, max_batch_size=5):
        self.register_description = register_description
        self.batches: list[RegisterBatch] = []
        self._values: Values = {}
        self._mapped_values: Values = {}
        self._max_batch_size = max_batch_size
        self.byteorder = Endian(byteorder)
        self.wordorder = Endian(wordorder)

        def name_to_address(name: str) -> int:
            return register_description[name]["address"]

        def check_if_names_are_okay_for_a_batch(name_list: list[str]) -> bool:
            assert sorted(name_list, key=name_to_address) == name_list
            length = name_to_address(name_list[-1]) - name_to_address(name_list[0]) + register_description[name_list[-1]]["length"]
            return length <= self._max_batch_size

        names_sorted_by_addr = list(sorted(register_description.keys(), key=name_to_address))
        start_index = 0
        for i in range(1, len(names_sorted_by_addr) + 1):
            if i >= len(names_sorted_by_addr) or not check_if_names_are_okay_for_a_batch(names_sorted_by_addr[start_index:i + 1]):
                self.batches.append(RegisterBatch(register_description, names_sorted_by_addr[start_index: i], byteorder=self.byteorder, wordorder=self.wordorder))
                start_index = i

    def clear(self):
        self._values = {}
        self._mapped_values = {}

    def update(self, client: mixin.ModbusClientMixin, slave_id = None, request_pause: float = 1) -> UpdateResult:
        self.clear()
        for i, batch in enumerate(self.batches):
            if i > 0:
                time.sleep(request_pause)
            result = batch.update(client, slave_id=slave_id)
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
    parser.add_argument("host", help="Host for modbus")
    parser.add_argument("--port", help="TCP port for modbus", default=502, type=int)
    parser.add_argument("--slave-id", help="Modbus Slave ID", default=None, type=int)
    parser.add_argument("--max-batch-size", help="Read a maximum of max-batch-sizes registers per request", default=5, type=int)
    parser.add_argument("--request-pause", help="Pause between requesting two batches, sec", default=1, type=float)
    args = parser.parse_args()

    with open(args.register_description) as file:
        register_description = json5.load(file)

    client = ModbusTcpClient(args.host, port=args.port)

    reader = RegisterReader(register_description, max_batch_size=args.max_batch_size)
    for i, batch in enumerate(reader.batches):
        print(f"batch {i} has {batch.count} bytes, starting at {batch.addr}")
    print(reader.update(client, slave_id=args.slave_id, request_pause=args.request_pause))

    for value_name in reader.values:
        print(f"{value_name + ':' :25} {reader.values[value_name]:>10} {register_description[value_name]['unit']}", f"{reader.mapped_values[value_name]}" if value_name in reader.mapped_values else "")

    client.close()
