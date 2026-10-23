# -*- coding: utf-8 -*-
"""Частина V: відмова сервера, timeout та два одночасні клієнти.

  python part5_demo.py timeout      --host IP   # timeout менший за час обчислення
  python part5_demo.py down         --host IP   # ЗУПИНІТЬ сервери перед запуском
  python part5_demo.py two-clients  --host IP   # два клієнти одночасно (дивіться logs/server.log)
"""
import argparse
import threading
import time

import config
from transport import TransportError, TransportTimeout, TransportUnavailable


def make(name, a, timeout):
    if name == "rest":
        from rest_client import RestTransport
        return RestTransport(a.host, a.rest_port, timeout)
    from grpc_client import GrpcTransport
    return GrpcTransport(a.host, a.grpc_port, timeout)


def demo_timeout(a):
    for p in a.protocols:
        t = make(p, a, a.short_timeout)
        print("[%s] запит n=%d з timeout=%.2f c ..." % (p, a.n, a.short_timeout))
        t0 = time.perf_counter()
        try:
            t.compute_full(a.n, a.seed, "v20-timeout-" + p)
            print("   відповідь прийшла вчасно (збільшіть n або зменшіть --short-timeout)")
        except TransportTimeout as e:
            print("   ОЧІКУВАНО: %s  (через %.2f c) — програма не впала" % (e, time.perf_counter() - t0))
        except TransportError as e:
            print("   помилка:", e)
        t.close()
    print("Примітка: сервер продовжує рахувати відкинутий запит до кінця — див. його журнал.")


def demo_down(a):
    for p in a.protocols:
        t = make(p, a, a.short_timeout)
        try:
            t.ping("v20-down-" + p)
            print("[%s] сервер ВІДПОВІВ — спочатку зупиніть сервер і повторіть." % p)
        except TransportUnavailable as e:
            print("[%s] ОЧІКУВАНО: %s — коректна обробка, без аварійного завершення" % (p, e))
        except TransportTimeout as e:
            print("[%s] ОЧІКУВАНО: %s" % (p, e))
        except TransportError as e:
            print("[%s] помилка: %s" % (p, e))
        t.close()


def demo_two_clients(a):
    for p in a.protocols:
        print("== %s: два клієнти одночасно, n=%d ==" % (p.upper(), a.n))
        results = {}
        barrier = threading.Barrier(2)

        def client(cid):
            t = make(p, a, a.timeout)
            t.ping("warm")                                   # з'єднання вже відкрите
            barrier.wait()                                   # стартують одночасно
            t0 = time.perf_counter()
            rep = t.compute_full(a.n, a.seed, "v20-n%d-%s-client%d" % (a.n, p, cid))
            results[cid] = ((time.perf_counter() - t0) * 1000.0, rep.server_ms)
            t.close()

        ths = [threading.Thread(target=client, args=(i,)) for i in (1, 2)]
        [x.start() for x in ths]
        [x.join() for x in ths]
        for cid in (1, 2):
            e2e, srv = results[cid]
            print("   клієнт %d: T_e2e=%.1f мс, serverComputeMs=%.1f мс" % (cid, e2e, srv))
    print("Журнал із requestId, startTs/endTs, serverComputeMs: logs/server.log НА СЕРВЕРІ.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["timeout", "down", "two-clients"])
    ap.add_argument("--host", default=config.HOST)
    ap.add_argument("--rest-port", type=int, default=config.REST_PORT)
    ap.add_argument("--grpc-port", type=int, default=config.GRPC_PORT)
    ap.add_argument("--protocols", default="rest,grpc")
    ap.add_argument("--n", type=int, default=150)
    ap.add_argument("--seed", type=int, default=config.SEED)
    ap.add_argument("--short-timeout", type=float, default=0.3)
    ap.add_argument("--timeout", type=float, default=300.0)
    a = ap.parse_args()
    a.protocols = [x.strip() for x in a.protocols.split(",")]
    {"timeout": demo_timeout, "down": demo_down, "two-clients": demo_two_clients}[a.mode](a)
