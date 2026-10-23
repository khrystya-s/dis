# -*- coding: utf-8 -*-
"""REST-клієнт (httpx). Реалізує спільний інтерфейс транспорту."""
import httpx

from transport import Reply, TransportError, TransportTimeout, TransportUnavailable


class RestTransport:
    name = "REST"

    def __init__(self, host, port, timeout=120.0):
        self.base = "http://%s:%d" % (host, port)
        self._http = httpx.Client(base_url=self.base, timeout=timeout)

    def _call(self, method, path, **kw):
        try:
            r = self._http.request(method, path, **kw)
        except httpx.TimeoutException as e:
            raise TransportTimeout("REST: перевищено timeout (%s)" % self.base) from e
        except httpx.TransportError as e:
            raise TransportUnavailable("REST: сервер недоступний (%s): %s" % (self.base, e)) from e
        if r.status_code != 200:
            raise TransportError("REST: HTTP %d: %s" % (r.status_code, r.text[:200]))
        return r.json()

    def ping(self, rid="ping"):
        self._call("GET", "/api/v1/health")

    def info(self):
        return self._call("GET", "/api/v1/info")

    def _compute(self, path, branch, n, seed, rid, begin, end, return_values):
        d = self._call("POST", path, json={
            "requestId": rid, "variant": 20, "n": n, "seed": seed, "branch": branch,
            "generateOnServer": True, "blockBegin": begin, "blockEnd": end,
            "returnValues": return_values})
        return Reply(d["requestId"], d["status"], d["resultKind"], d["rows"], d["cols"],
                     d.get("values", []), d["checksum"], d["serverComputeMs"], d["serverNode"])

    def compute_full(self, n, seed, rid, return_values=True):
        return self._compute("/api/v1/compute", "FULL", n, seed, rid, 0, 0, return_values)

    def compute_branch(self, branch, n, seed, rid, begin=0, end=0, return_values=True):
        return self._compute("/api/v1/branch", branch, n, seed, rid, begin, end, return_values)

    def close(self):
        self._http.close()
