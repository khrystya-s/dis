# -*- coding: utf-8 -*-
"""Спільна для REST і gRPC серверів логіка (без жодних web/RPC-залежностей):
валідація запиту, виконання, інформація про вузол, структурований журнал."""
import datetime
import os
import platform
import socket
import threading

from core import core_api

NODE = socket.gethostname()
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
_LOCK = threading.Lock()


def validate(variant, n, branch, begin, end, generate_on_server=True):
    if variant != core_api.VARIANT:
        raise ValueError("реалізовано лише variant=%d" % core_api.VARIANT)
    if not (1 <= n <= 5000):
        raise ValueError("n має бути в межах 1..5000")
    if branch not in core_api.BRANCHES:
        raise ValueError("невідома гілка: %s" % branch)
    if branch == "BLOCK" and not (0 <= begin < end <= n):
        raise ValueError("для BLOCK потрібно 0 <= block_begin < block_end <= n")
    if not generate_on_server:
        raise ValueError("режим D (дані від клієнта) не реалізовано; використовуйте режим P")


def server_info(workers):
    return {
        "node": NODE,
        "runtime": "Python %s / %s" % (platform.python_version(), platform.platform()),
        "logicalCpu": os.cpu_count() or 0,
        "workers": workers,
    }


def now_iso():
    return datetime.datetime.now().isoformat(timespec="milliseconds")


def log_request(protocol, client, request_id, variant, n, branch, server_ms,
                status, start_ts, end_ts):
    """Один структурований запис на запит (п.11 методички) + стандартний вивід."""
    line = ("timestamp=%s requestId=%s protocol=%s client=%s variant=%s n=%s "
            "branch=%s serverComputeMs=%.2f startTs=%s endTs=%s status=%s") % (
        now_iso(), request_id, protocol, client, variant, n, branch,
        server_ms, start_ts, end_ts, status)
    print(line, flush=True)
    os.makedirs(LOG_DIR, exist_ok=True)
    with _LOCK:
        with open(os.path.join(LOG_DIR, "server.log"), "a", encoding="utf-8") as f:
            f.write(line + "\n")
