# -*- coding: utf-8 -*-
"""Клієнтський benchmark ЛР №3 (запускається на КЛІЄНТСЬКОМУ ПК, сервери вже працюють).

Виконує:  L-C  ->  Ping(RTT)  ->  R-REST / R-gRPC  ->  H1/H3 через REST і gRPC
          ->  вплив зернистості RPC  ->  паспорт benchmark + підсумкові таблиці.

Приклад:
  python benchmark.py --host 192.168.1.50 --ns 100,150,200 --repeats 10
Самоперевірка логіки без мережі:
  python benchmark.py --protocols loopback --ns 60 --repeats 3 --fine-n 12
"""
import argparse
import csv
import json
import os
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

import config
import hybrid
import summarize
from core import core_api
from core import part_a as lab2
from local_baseline import measure_local
from transport import TransportError

RES = "results"


def make_transport(name, a):
    if name == "rest":
        from rest_client import RestTransport
        return RestTransport(a.host, a.rest_port, a.timeout)
    if name == "grpc":
        from grpc_client import GrpcTransport
        return GrpcTransport(a.host, a.grpc_port, a.timeout)
    if name == "loopback":
        from transport_loopback import LoopbackTransport
        return LoopbackTransport()
    raise SystemExit("невідомий протокол: " + name)


class Recorder:
    def __init__(self, path):
        self.f = open(path, "w", newline="", encoding="utf-8")
        self.w = csv.writer(self.f)
        self.w.writerow(["run_id", "protocol", "scenario", "n", "request_id",
                         "client_ms", "server_ms", "checksum", "status", "note"])
        self.i = 0

    def add(self, protocol, scenario, n, rid, client_ms, server_ms, checksum, status, note=""):
        self.i += 1
        self.w.writerow([self.i, protocol, scenario, n, rid, "%.3f" % client_ms,
                         "%.3f" % server_ms, "%.6f" % checksum, status, note])
        self.f.flush()

    def close(self):
        self.f.close()


def close_enough(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def med(v):
    return statistics.median(v)


def main():
    ap = argparse.ArgumentParser(description="LR3 client benchmark")
    ap.add_argument("--host", default=config.HOST, help="IP/ім'я СЕРВЕРА")
    ap.add_argument("--rest-port", type=int, default=config.REST_PORT)
    ap.add_argument("--grpc-port", type=int, default=config.GRPC_PORT)
    ap.add_argument("--protocols", default="rest,grpc")
    ap.add_argument("--ns", default="100,150,200")
    ap.add_argument("--seed", type=int, default=config.SEED)
    ap.add_argument("--repeats", type=int, default=10)
    ap.add_argument("--warmup", type=int, default=3)
    ap.add_argument("--ping-count", type=int, default=20)
    ap.add_argument("--timeout", type=float, default=300.0)
    ap.add_argument("--client-share", default="auto",
                    help="частка рядків Y3 на клієнті у H3: число 0..1 або auto")
    ap.add_argument("--gran-n", type=int, default=0, help="n для досліду зернистості (0 = найбільше з --ns)")
    ap.add_argument("--fine-n", type=int, default=40, help="малий n для дрібнозернистого RPC (1 рядок = 1 RPC)")
    ap.add_argument("--gran-repeats", type=int, default=5)
    ap.add_argument("--skip-hybrid", action="store_true")
    ap.add_argument("--skip-gran", action="store_true")
    a = ap.parse_args()

    os.makedirs(RES, exist_ok=True)
    ns = [int(s) for s in a.ns.split(",")]
    transports = [make_transport(p.strip(), a) for p in a.protocols.split(",")]
    rec = Recorder(os.path.join(RES, "results.csv"))
    V = config.VARIANT
    ref_x, t_client = {}, {}

    # ---------------- Частина I: L-C ----------------
    print("== L-C: локальний benchmark на клієнті (без мережі) ==", flush=True)
    for n in ns:
        times, x = measure_local(n, a.seed, a.repeats)
        ref_x[n], t_client[n] = x, med(times)
        for i, t in enumerate(times, 1):
            rec.add("direct", "L-C", n, "v%d-n%d-lc%02d" % (V, n, i), t, t, abs(x), "OK")
        print("  n=%d  T_client(median)=%.1f мс" % (n, t_client[n]), flush=True)

    # ---------------- Ping / RTT ----------------
    print("== Ping (RTT) ==", flush=True)
    for t in transports:
        try:
            for _ in range(3):
                t.ping("warm")
            for i in range(a.ping_count):
                t0 = time.perf_counter()
                t.ping("ping%02d" % i)
                rec.add(t.name, "PING", 0, "v%d-ping-%s-%02d" % (V, t.name.lower(), i),
                        (time.perf_counter() - t0) * 1000.0, 0.0, 0.0, "OK")
            print("  %s: готово" % t.name, flush=True)
        except TransportError as e:
            print("  %s: ПОМИЛКА %s" % (t.name, e))
            rec.add(t.name, "PING", 0, "ping-err", 0, 0, 0, "ERROR")

    # ---------------- Частина II: R-REST / R-gRPC ----------------
    print("== Частина II: повне перенесення задачі на сервер ==", flush=True)
    for n in ns:
        for t in transports:
            sc = "R-" + t.name
            try:
                for _ in range(a.warmup):
                    t.compute_full(n, a.seed, "warm")
                for i in range(1, a.repeats + 1):
                    rid = "v%d-n%d-%s-r%02d" % (V, n, t.name.lower(), i)
                    t0 = time.perf_counter()
                    rep = t.compute_full(n, a.seed, rid)
                    e2e = (time.perf_counter() - t0) * 1000.0
                    ok = close_enough(rep.checksum, abs(ref_x[n]))
                    rec.add(t.name, sc, n, rid, e2e, rep.server_ms, rep.checksum, "OK" if ok else "MISMATCH")
                print("  n=%d %s: готово" % (n, sc), flush=True)
            except TransportError as e:
                print("  n=%d %s: ПОМИЛКА %s" % (n, sc, e))
                rec.add(t.name, sc, n, "err", 0, 0, 0, "ERROR", str(e))

    # ---------------- Частина III: hybrid ----------------
    if not a.skip_hybrid:
        print("== Частина III: hybrid (клієнт + сервер) ==", flush=True)
        server_local = summarize.read_csv(os.path.join(RES, "local_server.csv"))
        with ThreadPoolExecutor(max_workers=2) as ex:
            for n in ns:
                inp = core_api.get_inputs(n, a.seed)
                if a.client_share == "auto":
                    ts = [float(r["client_ms"]) for r in server_local if int(r["n"]) == n]
                    share = (med(ts) / (med(ts) + t_client[n])) if ts else 0.5
                else:
                    share = float(a.client_share)
                for t in transports:
                    for scheme in ("H1", "H3"):
                        sc = "%s-%s" % (scheme, t.name)
                        try:
                            for _ in range(a.warmup):
                                hybrid.run_hybrid(scheme, t, ex, inp, n, a.seed, "warm", share)
                            for i in range(1, a.repeats + 1):
                                rid = "v%d-n%d-%s-%s-r%02d" % (V, n, scheme.lower(), t.name.lower(), i)
                                r = hybrid.run_hybrid(scheme, t, ex, inp, n, a.seed, rid, share)
                                ok = close_enough(r.x, ref_x[n])
                                note = "local=%.1f;remote=%.1f;wait=%.1f;k=%d" % (
                                    r.local_ms, r.remote_ms, r.wait_ms, r.split_k)
                                rec.add(t.name, sc, n, rid, r.total_ms, r.server_ms, abs(r.x),
                                        "OK" if ok else "MISMATCH", note)
                            print("  n=%d %s: готово (client_share=%.2f)" % (n, sc, share), flush=True)
                        except TransportError as e:
                            print("  n=%d %s: ПОМИЛКА %s" % (n, sc, e))
                            rec.add(t.name, sc, n, "err", 0, 0, 0, "ERROR", str(e))
    rec.close()

    # ---------------- Частина IV: зернистість ----------------
    if not a.skip_gran:
        print("== Частина IV: вплив зернистості RPC ==", flush=True)
        gran_n = a.gran_n or max(ns)
        plan = [(gran_n, [1, 4]), (a.fine_n, sorted({1, 4, a.fine_n}))]
        gpath = os.path.join(RES, "results_granularity.csv")
        with open(gpath, "w", newline="", encoding="utf-8") as gf:
            gw = csv.writer(gf)
            gw.writerow(["protocol", "n", "rpcs", "block_rows", "repeat",
                         "total_ms", "server_sum_ms", "overhead_ms", "local_y3_ms"])
            for (n, ks) in plan:
                inp = core_api.get_inputs(n, a.seed)
                loc = []
                for _ in range(3):
                    t0 = time.perf_counter()
                    lab2.branch_Y3(inp["A2"], inp["C2"], inp["B2"])
                    loc.append((time.perf_counter() - t0) * 1000.0)
                local_y3 = med(loc)
                for t in transports:
                    try:
                        for k in ks:
                            hybrid.run_blocked_y3(t, n, a.seed, "warm", k)
                            for r in range(1, a.gran_repeats + 1):
                                tot, srv = hybrid.run_blocked_y3(
                                    t, n, a.seed, "v%d-n%d-g%d-%s-r%02d" % (V, n, k, t.name.lower(), r), k)
                                gw.writerow([t.name, n, k, -(-n // k), r, "%.3f" % tot,
                                             "%.3f" % srv, "%.3f" % (tot - srv), "%.3f" % local_y3])
                            print("  n=%d %s K=%d: готово" % (n, t.name, k), flush=True)
                    except TransportError as e:
                        print("  n=%d %s: ПОМИЛКА %s" % (n, t.name, e))

    # ---------------- паспорт benchmark (Додаток В) ----------------
    passport = {
        "variant": V, "n": ns, "seed": a.seed, "resultKind": "SCALAR",
        "referenceChecksum": {str(n): abs(ref_x[n]) for n in ns},
        "decompositionLarge": "гілки y1, y2, Y3 (великі незалежні підвирази DAG); x — точка синхронізації",
        "decompositionMedium": "Y3 = A2*C2-B2 ділиться на блоки рядків [begin,end) (BLOCK)",
        "clientBaselineMs": {str(n): t_client[n] for n in ns},
        "serverBaselineMs": "див. results/local_server.csv (L-S)",
        "payloadMode": "P (parameters: variant, n, seed)",
        "notes": "Python, core/part_a.py з ЛР №2 без змін; REST=FastAPI+httpx, gRPC=grpcio",
    }
    with open(os.path.join(RES, "passport.json"), "w", encoding="utf-8") as f:
        json.dump(passport, f, ensure_ascii=False, indent=2)

    for t in transports:
        t.close()
    print("\nГотово. Підсумкові таблиці:\n")
    summarize.main(RES)


if __name__ == "__main__":
    main()
