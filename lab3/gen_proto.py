# -*- coding: utf-8 -*-
"""Генерує contracts/compute_pb2.py та contracts/compute_pb2_grpc.py з compute.proto.
Запускати ОДИН раз після `pip install -r requirements.txt` (і повторно, якщо
змінили версію protobuf/grpcio-tools): python gen_proto.py"""
import os
import sys

from grpc_tools import protoc

here = os.path.dirname(os.path.abspath(__file__))
contracts = os.path.join(here, "contracts")
code = protoc.main([
    "grpc_tools.protoc",
    "-I" + contracts,
    "--python_out=" + contracts,
    "--grpc_python_out=" + contracts,
    os.path.join(contracts, "compute.proto"),
])
print("OK: згенеровано compute_pb2.py / compute_pb2_grpc.py" if code == 0 else "ПОМИЛКА protoc")
sys.exit(code)
