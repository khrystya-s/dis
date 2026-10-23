# -*- coding: utf-8 -*-
"""Тонкий шар над математичним ядром ЛР №2 (core/part_a.py).

core/part_a.py НЕ змінювався і НЕ залежить від REST/gRPC.
Тут лише:
  * кешований виклик генератора вхідних даних (режим P: variant, n, seed);
  * виконання однієї "гілки" DAG (FULL / Y1 / Y2 / Y3 / BLOCK);
  * checksum результату.
Час compute_ms вимірюється ТІЛЬКИ навколо математичного ядра
(без генерації даних, без пакування результату у список).
"""
import time
from functools import lru_cache

from core import part_a as lab2

VARIANT = 20
BRANCHES = ("FULL", "Y1", "Y2", "Y3", "BLOCK")


@lru_cache(maxsize=6)
def get_inputs(n, seed):
    """Той самий генератор, що й у Частині А ЛР №2 (generate_inputs)."""
    return lab2.generate_inputs(n, seed)


def _flat(M):
    return [v for row in M for v in row]


def execute(branch, n, seed, begin=0, end=0, return_values=True):
    """Виконує гілку на ЦЬОМУ вузлі. Повертає словник (picklable)."""
    t_gen = time.perf_counter()
    inp = get_inputs(n, seed)
    gen_ms = (time.perf_counter() - t_gen) * 1000.0

    t0 = time.perf_counter()
    if branch == "FULL":
        out = lab2.sequential_part_a(inp)[0]
    elif branch == "Y1":
        out = lab2.branch_y1(inp["A"], inp["b"])
    elif branch == "Y2":
        out = lab2.branch_y2(inp["A1"], inp["b1"], inp["c1"])
    elif branch == "Y3":
        out = lab2.branch_Y3(inp["A2"], inp["C2"], inp["B2"])
    elif branch == "BLOCK":      # рядки [begin, end) матриці Y3 = A2*C2 - B2
        out = lab2.branch_Y3(inp["A2"][begin:end], inp["C2"], inp["B2"][begin:end])
    else:
        raise ValueError("unknown branch " + str(branch))
    compute_ms = (time.perf_counter() - t0) * 1000.0

    if branch == "FULL":
        kind, rows, cols, values = "SCALAR", 1, 1, [out]
    elif branch in ("Y1", "Y2"):
        kind, rows, cols, values = "VECTOR", len(out), 1, list(out)
    else:
        kind, rows, cols, values = "MATRIX", len(out), len(out[0]), _flat(out)
    checksum = sum(abs(v) for v in values)
    return {
        "kind": kind, "rows": rows, "cols": cols,
        "values": values if return_values else [],
        "checksum": checksum, "compute_ms": compute_ms, "gen_ms": gen_ms,
    }
