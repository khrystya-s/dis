# -*- coding: utf-8 -*-
"""Підсумкові таблиці з results/*.csv (також запускається окремо: python summarize.py)."""
import csv
import os
import statistics

ORDER = ["L-C", "L-S", "R-REST", "R-gRPC", "R-LOOPBACK",
         "H1-REST", "H1-gRPC", "H1-LOOPBACK", "H3-REST", "H3-gRPC", "H3-LOOPBACK"]


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def med(v):
    return statistics.median(v) if v else float("nan")


def parse_note(note):
    d = {}
    for part in (note or "").split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            try:
                d[k] = float(v)
            except ValueError:
                pass
    return d


def md(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def f1(x):
    return "—" if x != x else "%.1f" % x


def build(res_dir):
    rows = read_csv(os.path.join(res_dir, "results.csv")) + read_csv(os.path.join(res_dir, "local_server.csv"))
    ok = [r for r in rows if r["status"] == "OK"]
    bad = [r for r in rows if r["status"] != "OK"]
    out = []

    # --- Ping ---
    pings = {}
    for r in ok:
        if r["scenario"] == "PING":
            pings.setdefault(r["protocol"], []).append(float(r["client_ms"]))
    if pings:
        out.append("### Ping / RTT після warm-up (мс)\n")
        out.append(md(["Протокол", "N", "Медіана", "Min", "Max"],
                      [[p, len(v), "%.2f" % med(v), "%.2f" % min(v), "%.2f" % max(v)]
                       for p, v in pings.items()]))

    # --- групування ---
    g = {}
    for r in ok:
        if r["scenario"] == "PING":
            continue
        g.setdefault((int(r["n"]), r["scenario"]), []).append(r)
    ns = sorted({k[0] for k in g})

    # --- основна таблиця 9.2 ---
    main_rows = []
    for n in ns:
        for sc in sorted({k[1] for k in g if k[0] == n}, key=lambda s: ORDER.index(s) if s in ORDER else 99):
            rs = g[(n, sc)]
            e2e = med([float(r["client_ms"]) for r in rs])
            srv = med([float(r["server_ms"]) for r in rs])
            if sc.startswith("L-"):
                ovh, proto = "—", "direct"
            elif sc.startswith("R-"):
                ovh, proto = f1(e2e - srv), rs[0]["protocol"]
            else:
                notes = [parse_note(r.get("note")) for r in rs]
                rem = med([x.get("remote", float("nan")) for x in notes])
                ovh, proto = f1(rem - srv) + "*", rs[0]["protocol"]
            main_rows.append([n, sc, proto, f1(e2e), f1(srv) if not sc.startswith("L-") or sc == "L-S" else f1(srv),
                              ovh, "%.6g" % float(rs[0]["checksum"]), "n=%d" % len(rs)])
    if main_rows:
        out.append("\n### Основна таблиця часу (медіани, мс)\n")
        out.append(md(["n", "Сценарій", "Протокол", "T_e2e", "T_server", "T_overhead", "Checksum", "Примітка"], main_rows))
        out.append("\n\\* для H-сценаріїв T_overhead = (e2e віддаленого виклику) − T_server; "
                   "T_e2e — повний час гібриду від старту до готового x.")

    # --- метрики ---
    met = []
    for n in ns:
        tc = med([float(r["client_ms"]) for r in g.get((n, "L-C"), [])])
        if tc != tc:
            continue
        for sc in sorted({k[1] for k in g if k[0] == n}, key=lambda s: ORDER.index(s) if s in ORDER else 99):
            if sc[:2] in ("R-", "H1", "H3"):
                rs = g[(n, sc)]
                t = med([float(r["client_ms"]) for r in rs])
                if sc.startswith("R-"):
                    met.append([n, sc, f1(t), "R_offload = %.2f" % (tc / t), "—", "—"])
                else:
                    wait = med([parse_note(r.get("note")).get("wait", float("nan")) for r in rs])
                    sd = tc / t
                    met.append([n, sc, f1(t), "S_dist = %.2f" % sd, "%.2f" % (sd / 2), f1(wait)])
    if met:
        out.append("\n### Distributed speedup та remote-offload (відносно T_client)\n")
        out.append(md(["n", "Сценарій", "T, мс", "Метрика", "E₂ = S_dist/2", "Очікування мережі клієнтом, мс"], met))

    # --- зернистість ---
    gr = read_csv(os.path.join(res_dir, "results_granularity.csv"))
    if gr:
        gg = {}
        for r in gr:
            gg.setdefault((r["protocol"], int(r["n"]), int(r["rpcs"])), []).append(r)
        grows = []
        for (p, n, k), rs in sorted(gg.items(), key=lambda kv: (kv[0][1], kv[0][0], kv[0][2])):
            tot = med([float(r["total_ms"]) for r in rs])
            ov = med([float(r["overhead_ms"]) for r in rs])
            loc = float(rs[0]["local_y3_ms"])
            grows.append([p, n, k, rs[0]["block_rows"], f1(tot), f1(ov), "%.2f" % (loc / tot),
                          "локально Y3: %.1f мс" % loc])
        out.append("\n### Вплив зернистості RPC (Y3 цілком віддалено, K послідовних RPC)\n")
        out.append(md(["Протокол", "n", "Кількість RPC", "Рядків у блоці", "Загальний T, мс",
                       "RPC overhead, мс", "Speedup (локальний Y3 / T)", "Примітка"], grows))

    if bad:
        out.append("\n### Рядки зі статусом ≠ OK: %d (перевірте results.csv)" % len(bad))
    return "\n".join(out)


def main(res_dir="results"):
    text = build(res_dir)
    print(text)
    with open(os.path.join(res_dir, "summary.md"), "w", encoding="utf-8") as f:
        f.write(text + "\n")


if __name__ == "__main__":
    main()
