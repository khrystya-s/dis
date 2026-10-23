# -*- coding: utf-8 -*-
"""Розподілене виконання "клієнт + сервер" (великоблокова декомпозиція Dᴸ з ЛР №2).

DAG:   y1 --\
       y2 ---+--> x = compute_x(y1, y2, Y3)
       Y3 --/

Трудомісткість: y1, y2 ~ n² (дешеві), Y3 = A2*C2-B2 ~ n³ (важка), compute_x ~ 2n³.

Схема H1: клієнт -> y1, y2;  сервер -> Y3 (ціла). Клієнт чекає на Y3 і рахує x.
          Критичний шлях: Y3 -> x. Клієнт майже весь час простоює -> виграшу
          практично немає (y1,y2 надто легкі, щоб перекрити Y3).
Схема H3: важка гілка Y3 ділиться за рядками на два великі блоки:
          клієнт -> Y3[0:k) (+ y1, y2);  сервер -> Y3[k:n).  Обидва вузли
          рахують важку роботу одночасно -> реальне перекриття у часі.
"""
import time
from dataclasses import dataclass

from core import part_a as lab2


@dataclass
class HybridResult:
    total_ms: float      # від старту до готового x (включно з об'єднанням і compute_x)
    local_ms: float      # скільки клієнт рахував свою частину
    remote_ms: float     # e2e віддаленого виклику (як його бачить клієнт)
    server_ms: float     # серверний час математичного ядра
    wait_ms: float       # скільки клієнт ЧЕКАВ мережу після завершення локальної частини
    x: float
    split_k: int


def _rows(values, r, c):
    return [values[i * c:(i + 1) * c] for i in range(r)]


def split_rows(n, k_blocks):
    """Рівномірно розбиває [0,n) на k_blocks суміжних блоків (begin,end)."""
    base, extra = divmod(n, k_blocks)
    out, b = [], 0
    for i in range(k_blocks):
        e = b + base + (1 if i < extra else 0)
        out.append((b, e))
        b = e
    return out


def run_hybrid(scheme, transport, executor, inp, n, seed, rid, client_share=0.5):
    k = 0
    if scheme == "H3":
        k = min(max(int(round(n * client_share)), 1), n - 1)   # рядків Y3 на клієнті

    def local_job():
        t = time.perf_counter()
        y1 = lab2.branch_y1(inp["A"], inp["b"])
        y2 = lab2.branch_y2(inp["A1"], inp["b1"], inp["c1"])
        Y3_local = []
        if scheme == "H3":
            Y3_local = lab2.branch_Y3(inp["A2"][:k], inp["C2"], inp["B2"][:k])
        return y1, y2, Y3_local, (time.perf_counter() - t) * 1000.0

    def remote_job():
        t = time.perf_counter()
        if scheme == "H1":
            rep = transport.compute_branch("Y3", n, seed, rid)
        else:
            rep = transport.compute_branch("BLOCK", n, seed, rid, k, n)
        return rep, (time.perf_counter() - t) * 1000.0

    t0 = time.perf_counter()
    f_local = executor.submit(local_job)       # локальна підзадача — асинхронно
    f_remote = executor.submit(remote_job)     # віддалена підзадача — одночасно
    y1, y2, Y3_local, local_ms = f_local.result()
    rep, remote_ms = f_remote.result()

    if scheme == "H1":
        Y3 = _rows(rep.values, n, n)
    else:
        Y3 = Y3_local + _rows(rep.values, n - k, n)
    x = lab2.compute_x(y1, y2, Y3)             # об'єднання: фінальна редукція на клієнті
    total_ms = (time.perf_counter() - t0) * 1000.0
    return HybridResult(total_ms, local_ms, remote_ms, rep.server_ms,
                        max(0.0, remote_ms - local_ms), x, k)


def run_blocked_y3(transport, n, seed, rid, k_blocks):
    """Частина IV: весь Y3 віддалено, але k_blocks окремими RPC (послідовно).
    Повертає (загальний час, сума серверних часів) у мс."""
    t0 = time.perf_counter()
    rows, srv = [], 0.0
    for (b, e) in split_rows(n, k_blocks):
        rep = transport.compute_branch("BLOCK", n, seed, rid, b, e)
        rows.extend(_rows(rep.values, e - b, n))
        srv += rep.server_ms
    return (time.perf_counter() - t0) * 1000.0, srv
