# -*- coding: utf-8 -*-
"""gRPC-сервер (grpcio). Спочатку: python gen_proto.py.   Запуск: python grpc_server.py --port 50051

Логічно той самий контракт і ТОЙ САМИЙ core, що й у REST-сервері.
"""
import argparse
import os
import sys
from concurrent import futures

import grpc

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "contracts"))
import compute_pb2          # noqa: E402  (згенеровано gen_proto.py)
import compute_pb2_grpc     # noqa: E402

import config
import service
from core import core_api

POOL = None
WORKERS = 2


class ComputeServicer(compute_pb2_grpc.ComputeServiceServicer):
    def Ping(self, request, context):
        return compute_pb2.PingReply(request_id=request.request_id, payload=request.payload)

    def GetServerInfo(self, request, context):
        i = service.server_info(WORKERS)
        return compute_pb2.InfoReply(node=i["node"], runtime=i["runtime"], logical_cpu=i["logicalCpu"])

    def ComputeFull(self, request, context):
        return self._compute(request, context, "FULL")

    def ComputeBranch(self, request, context):
        return self._compute(request, context, compute_pb2.Branch.Name(request.branch))

    def _compute(self, request, context, branch):
        client = context.peer()
        try:
            service.validate(request.variant, request.n, branch, request.block_begin,
                             request.block_end, request.generate_on_server)
        except ValueError as e:
            service.log_request("grpc", client, request.request_id, request.variant, request.n,
                                branch, 0.0, "INVALID_ARGUMENT", service.now_iso(), service.now_iso())
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(e))

        start_ts = service.now_iso()
        res = POOL.submit(core_api.execute, branch, request.n, request.seed,
                          request.block_begin, request.block_end, True).result()
        end_ts = service.now_iso()
        service.log_request("grpc", client, request.request_id, request.variant, request.n,
                            branch, res["compute_ms"], "OK", start_ts, end_ts)
        return compute_pb2.ComputeReply(
            request_id=request.request_id, status="OK", result_kind=res["kind"],
            rows=res["rows"], cols=res["cols"], values=res["values"],
            checksum=res["checksum"], server_compute_ms=res["compute_ms"],
            server_node=service.NODE)


def main():
    global POOL, WORKERS
    ap = argparse.ArgumentParser(description="LR3 gRPC server")
    ap.add_argument("--host", default=config.BIND)
    ap.add_argument("--port", type=int, default=config.GRPC_PORT)
    ap.add_argument("--workers", type=int, default=2, help="процесів-виконавців (ProcessPoolExecutor)")
    a = ap.parse_args()
    WORKERS = a.workers
    POOL = futures.ProcessPoolExecutor(max_workers=WORKERS)

    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=8),
        options=[("grpc.max_send_message_length", config.MAX_MSG_BYTES),
                 ("grpc.max_receive_message_length", config.MAX_MSG_BYTES)])
    compute_pb2_grpc.add_ComputeServiceServicer_to_server(ComputeServicer(), server)
    server.add_insecure_port("%s:%d" % (a.host, a.port))
    server.start()
    print("gRPC сервер: %s:%d  (вузол %s, workers=%d)" % (a.host, a.port, service.NODE, WORKERS))
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop(0)
        POOL.shutdown(wait=False, cancel_futures=True)


if __name__ == "__main__":
    main()
