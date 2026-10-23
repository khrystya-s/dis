# -*- coding: utf-8 -*-
"""gRPC-клієнт (generated stub). Реалізує той самий інтерфейс, що й RestTransport."""
import os
import sys

import grpc

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "contracts"))
import compute_pb2          # noqa: E402
import compute_pb2_grpc     # noqa: E402

import config
from transport import Reply, TransportError, TransportTimeout, TransportUnavailable


class GrpcTransport:
    name = "gRPC"

    def __init__(self, host, port, timeout=120.0):
        self.target = "%s:%d" % (host, port)
        self.timeout = timeout
        self._channel = grpc.insecure_channel(self.target, options=[
            ("grpc.max_send_message_length", config.MAX_MSG_BYTES),
            ("grpc.max_receive_message_length", config.MAX_MSG_BYTES)])
        self._stub = compute_pb2_grpc.ComputeServiceStub(self._channel)

    def _call(self, fn, request):
        try:
            return fn(request, timeout=self.timeout)
        except grpc.RpcError as e:
            code = e.code()
            if code == grpc.StatusCode.DEADLINE_EXCEEDED:
                raise TransportTimeout("gRPC: перевищено timeout (%s)" % self.target) from e
            if code == grpc.StatusCode.UNAVAILABLE:
                raise TransportUnavailable("gRPC: сервер недоступний (%s)" % self.target) from e
            raise TransportError("gRPC: %s: %s" % (code.name, e.details())) from e

    def ping(self, rid="ping"):
        self._call(self._stub.Ping, compute_pb2.PingRequest(request_id=rid, payload=b""))

    def info(self):
        r = self._call(self._stub.GetServerInfo, compute_pb2.InfoRequest())
        return {"node": r.node, "runtime": r.runtime, "logicalCpu": r.logical_cpu}

    def _reply(self, r):
        return Reply(r.request_id, r.status, r.result_kind, r.rows, r.cols,
                     list(r.values), r.checksum, r.server_compute_ms, r.server_node)

    def compute_full(self, n, seed, rid, return_values=True):
        req = compute_pb2.ComputeRequest(
            request_id=rid, variant=20, n=n, seed=seed,
            branch=compute_pb2.FULL, generate_on_server=True)
        return self._reply(self._call(self._stub.ComputeFull, req))

    def compute_branch(self, branch, n, seed, rid, begin=0, end=0, return_values=True):
        req = compute_pb2.ComputeRequest(
            request_id=rid, variant=20, n=n, seed=seed,
            branch=compute_pb2.Branch.Value(branch), generate_on_server=True,
            block_begin=begin, block_end=end)
        return self._reply(self._call(self._stub.ComputeBranch, req))

    def close(self):
        self._channel.close()
