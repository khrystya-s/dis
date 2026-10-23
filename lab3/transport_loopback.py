# -*- coding: utf-8 -*-
"""Псевдо-транспорт БЕЗ мережі — лише для самоперевірки логіки benchmark
(`python benchmark.py --protocols loopback ...`). Імітує JSON-серіалізацію.
У фінальному експерименті НЕ використовується."""
import json
import time

from core import core_api
from transport import Reply


class LoopbackTransport:
    name = "LOOPBACK"

    def __init__(self, latency_ms=0.0):
        self.latency = latency_ms / 1000.0

    def ping(self, rid="ping"):
        time.sleep(self.latency)

    def info(self):
        return {"node": "loopback", "runtime": "in-process", "logicalCpu": 0}

    def _do(self, branch, n, seed, rid, begin, end):
        time.sleep(self.latency)
        res = core_api.execute(branch, n, seed, begin, end, True)
        vals = json.loads(json.dumps(res["values"]))      # імітація серіалізації
        time.sleep(self.latency)
        return Reply(rid, "OK", res["kind"], res["rows"], res["cols"], vals,
                     res["checksum"], res["compute_ms"], "loopback")

    def compute_full(self, n, seed, rid, return_values=True):
        return self._do("FULL", n, seed, rid, 0, 0)

    def compute_branch(self, branch, n, seed, rid, begin=0, end=0, return_values=True):
        return self._do(branch, n, seed, rid, begin, end)

    def close(self):
        pass
