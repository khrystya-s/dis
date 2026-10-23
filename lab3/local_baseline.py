# -*- coding: utf-8 -*-
"""Частина I: локальний benchmark (без мережі) на ОДНОМУ вузлі.
  на клієнті: python local_baseline.py --label client   -> results/local_client.csv (T_client, L-C)
  на сервері: python local_baseline.py --label server   -> results/local_server.csv (T_server_local, L-S)
Файл local_server.csv скопіюйте на клієнтський ПК у папку results/."""
import argparse
import csv
import os
import platform
import statistics
import time

import config
from core import core_api
from core import part_a as lab2


def measure_local(n, seed, repeats, warmup=1):
    """Повертає (список часів у мс, x). Час — лише математичне ядро ЛР №2."""
    inp = core_api.get_inputs(n, seed)
    x = None
    for _ in range(warmup):
        x = lab2.sequential_part_a(inp)[0]
    times = []
    for _ in range(repeats):
        t = time.perf_counter()
        x = lab2.sequential_part_a(inp)[0]
        times.append((time.perf_counter() - t) * 1000.0)
    return times, x


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", choices=["client", "server"], required=True)
    ap.add_argument("--ns", default="100,150,200")
    ap.add_argument("--seed", type=int, default=config.SEED)
    ap.add_argument("--repeats", type=int, default=10)
    a = ap.parse_args()

    scen = "L-C" if a.label == "client" else "L-S"
    os.makedirs("results", exist_ok=True)
    out = os.path.join("results", "local_%s.csv" % a.label)
    print("Вузол: %s | CPU логічних: %s | %s | Python %s" % (
        platform.node(), os.cpu_count(), platform.platform(), platform.python_version()))
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["run_id", "protocol", "scenario", "n", "request_id",
                    "client_ms", "server_ms", "checksum", "status"])
        rid = 0
        for n in [int(s) for s in a.ns.split(",")]:
            times, x = measure_local(n, a.seed, a.repeats)
            for t in times:
                rid += 1
                w.writerow([rid, "direct", scen, n, "v%d-n%d-local%02d" % (config.VARIANT, n, rid),
                            "%.3f" % t, "%.3f" % t, "%.6f" % abs(x), "OK"])
            print("n=%d  %s: median=%.1f мс  min=%.1f  max=%.1f  checksum=%.6g" % (
                n, scen, statistics.median(times), min(times), max(times), abs(x)))
    print("Збережено:", out)


if __name__ == "__main__":
    main()
