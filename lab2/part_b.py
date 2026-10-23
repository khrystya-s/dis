# -*- coding: utf-8 -*-
"""
ЛР №2. Частина Б. Варіант 20.
=================================================================
Матриця A (Додаток Б, варіант 20):  "1 2 3 ... n" у кожному рядку.
    => A[i][j] = j+1  для будь-якого i   (0-індексація; усі рядки ІДЕНТИЧНІ).

Матриця B (Додаток Б, варіант 20): заштрихована (ненульова) область -
    трикутник, прилеглий до побічної діагоналі знизу-справа, тобто
    (у 1-індексації i,j = 1..n):

        B[i][j] != 0   <=>   i + j >= n + 1
        B[i][j]  = 0   інакше

    (перевірено рендерингом рисунка зі сторінки методички: заштрихований
     трикутник обмежений нижнім краєм, правим краєм і діагоналлю
     "лівий-нижній кут -> правий-верхній кут" квадрата, що відповідає
     умові i+j >= n+1).

-----------------------------------------------------------------
КЛЮЧОВІ СТРУКТУРНІ СПОСТЕРЕЖЕННЯ (використовуються для оптимізації D1/D3):

  (1) Усі рядки A однакові  =>  Y[i][j] = sum_k A[i][k]*B[k][j] НЕ залежить
      від i. Тобто ВСІ РЯДКИ добутку Y = A*B - однакові! Достатньо
      обчислити ОДИН рядок і розмножити його на інші n-1 рядків (0 множень).

  (2) B[k][j] != 0 лише при k >= n+1-j (1-індексація). Тому для стовпця j
      сума береться не по всіх k=1..n, а лише по k = max(1,n+1-j)..n,
      тобто рівно по j доданках (не по n).

  Прямий алгоритм:      n^3 множень (усі рядки, усі k).
  Оптимізований:        sum_{j=1..n} j = n(n+1)/2 множень (лише ОДИН рядок,
                         і лише в межах ненульової області B).

  Це ілюструє методичну вимогу п.7.2: недостатньо просто перевіряти
  "if a!=0 and b!=0" у потрійному циклі - тут використана структура ОБОХ
  матриць (однорідність рядків A + трикутна форма B), що дає перехід
  від O(n^3) до O(n^2) (з урахуванням розмноження рядка).
-----------------------------------------------------------------

Порівнюються 4 версії (D0-D3, п.7.3 методички):
    D0 - прямий послідовний          (n^3 множень)
    D1 - структурно оптимізований послідовний   (n(n+1)/2 множень)
    D2 - прямий паралельний          (розподіл РЯДКІВ A між p worker-ами)
    D3 - оптимізований паралельний   (розподіл СТОВПЦІВ j між p worker-ами,
                                       бо обчислюється лише один рядок)
"""

import random
import time
from concurrent.futures import ProcessPoolExecutor


# =================================================================
# 1. Побудова матриць A, B за варіантом 20
# =================================================================

def make_A(n):
    row = [float(j) for j in range(1, n + 1)]
    return [row[:] for _ in range(n)]  # усі рядки - копії одного й того ж рядка [1,2,...,n]


def make_B(n, seed=20):
    """Заштрихована область: i+j >= n+1 (1-індексація) - довільні ненульові цілі."""
    rng = random.Random(seed)
    B = [[0.0] * n for _ in range(n)]
    for i in range(1, n + 1):
        for j in range(1, n + 1):
            if i + j >= n + 1:
                B[i - 1][j - 1] = float(rng.randint(1, 9))
    return B


# =================================================================
# 2. D0: прямий послідовний алгоритм (контрольний, O(n^3))
# =================================================================

def D0_direct(A, B):
    n = len(A)
    m = len(B[0])
    Y = [[0.0] * m for _ in range(n)]
    for i in range(n):
        Ai = A[i]
        Yi = Y[i]
        for j in range(m):
            s = 0.0
            for k in range(n):
                s += Ai[k] * B[k][j]
            Yi[j] = s
    return Y


def count_mults_direct(n):
    return n * n * n


# =================================================================
# 3. D1: структурно оптимізований послідовний алгоритм
# =================================================================

def D1_optimized(A, B):
    n = len(A)
    m = len(B[0])
    a_row = A[0]                       # усі рядки A однакові -> достатньо одного
    y0 = [0.0] * m
    for j in range(1, m + 1):
        k_lo = max(1, n + 1 - j)       # межі ненульової області B у стовпці j
        s = 0.0
        for k in range(k_lo, n + 1):
            s += a_row[k - 1] * B[k - 1][j - 1]
        y0[j - 1] = s
    return [y0[:] for _ in range(n)]   # розмноження ОДНОГО рядка на всі n рядків (без множень)


def count_mults_optimized(n):
    """sum_{j=1}^{n} j = n(n+1)/2 - і це для ОДНОГО рядка, а не для n рядків."""
    return n * (n + 1) // 2


# =================================================================
# 4. D2: прямий паралельний (рядки A діляться між p worker-ами)
# =================================================================

def _worker_direct(args):
    A_chunk, B = args
    n = len(B)
    m = len(B[0])
    out = []
    for Ai in A_chunk:
        row_out = [0.0] * m
        for j in range(m):
            s = 0.0
            for k in range(n):
                s += Ai[k] * B[k][j]
            row_out[j] = s
        out.append(row_out)
    return out


def D2_direct_parallel(A, B, p, chunksize=None):
    """chunksize=None -> 'static' (по n/p рядків на задачу, p задач).
    Менший chunksize -> дрібніші задачі, що емулюють dynamic/guided
    (виконавці розбирають задачі з черги пулу по мірі звільнення)."""
    n = len(A)
    chunk = chunksize or max(1, (n + p - 1) // p)
    chunks = [A[i:i + chunk] for i in range(0, n, chunk)]
    with ProcessPoolExecutor(max_workers=p) as ex:
        results = list(ex.map(_worker_direct, [(c, B) for c in chunks]))
    out = []
    for r in results:
        out.extend(r)
    return out


# =================================================================
# 5. D3: оптимізований паралельний (стовпці j діляться між p worker-ами,
#    бо через ідентичність рядків A рахуємо лише ОДИН рядок)
# =================================================================

def _worker_optimized(args):
    a_row, B, j_lo, j_hi, n = args
    out = []
    for j0 in range(j_lo, j_hi):        # j0 - 0-індексований стовпець
        j = j0 + 1
        k_lo = max(1, n + 1 - j)
        s = 0.0
        for k in range(k_lo, n + 1):
            s += a_row[k - 1] * B[k - 1][j0]
        out.append(s)
    return out


def D3_optimized_parallel(A, B, p, chunksize=None):
    n = len(A)
    m = len(B[0])
    a_row = A[0]
    chunk = chunksize or max(1, (m + p - 1) // p)
    tasks = []
    for j_lo in range(0, m, chunk):
        j_hi = min(m, j_lo + chunk)
        tasks.append((a_row, B, j_lo, j_hi, n))
    with ProcessPoolExecutor(max_workers=p) as ex:
        results = list(ex.map(_worker_optimized, tasks))
    y0 = []
    for r in results:
        y0.extend(r)
    return [y0[:] for _ in range(n)]


# =================================================================
# 6. Допоміжні функції перевірки та вимірювання
# =================================================================

def matrices_close(X, Y, tol=1e-6):
    return all(abs(X[i][j] - Y[i][j]) < tol
               for i in range(len(X)) for j in range(len(X[0])))


def compare_schedules(A, B, p, n):
    """Емуляція schedule(static) vs dynamic vs guided через розмір chunksize."""
    variants = {
        "static  (chunk = n/p)": max(1, (n + p - 1) // p),
        "dynamic (chunk ~ n/(4p))": max(1, n // (4 * p)),
        "guided  (chunk ~ n/(8p))": max(1, n // (8 * p)),
    }
    print(f"\nПорівняння стратегій розподілу (D2, прямий паралельний), n={n}, p={p}:")
    for name, ch in variants.items():
        t0 = time.perf_counter()
        D2_direct_parallel(A, B, p, chunksize=ch)
        t = time.perf_counter() - t0
        print(f"  {name:26s} chunk={ch:5d}  T={t:.4f} c")


def benchmark_part_b(ns=(40, 60, 80), p=4):
    print(f"{'n':>5} | {'D0 seq':>9} | {'D1 seq':>9} | {'D2 par':>9} | {'D3 par':>9} "
          f"| {'mults D0':>10} | {'mults D1':>10}")
    print("-" * 78)
    for n in ns:
        A = make_A(n)
        B = make_B(n)

        t0 = time.perf_counter(); Y0 = D0_direct(A, B);              t_d0 = time.perf_counter() - t0
        t0 = time.perf_counter(); Y1 = D1_optimized(A, B);           t_d1 = time.perf_counter() - t0
        t0 = time.perf_counter(); Y2 = D2_direct_parallel(A, B, p);  t_d2 = time.perf_counter() - t0
        t0 = time.perf_counter(); Y3 = D3_optimized_parallel(A, B, p); t_d3 = time.perf_counter() - t0

        assert matrices_close(Y0, Y1), "D1 не збігається з D0!"
        assert matrices_close(Y0, Y2), "D2 не збігається з D0!"
        assert matrices_close(Y0, Y3), "D3 не збігається з D0!"

        print(f"{n:5d} | {t_d0:9.4f} | {t_d1:9.4f} | {t_d2:9.4f} | {t_d3:9.4f} "
              f"| {count_mults_direct(n):10d} | {count_mults_optimized(n):10d}")

    # демонстрація static/dynamic/guided-подібних стратегій на найбільшому n
    compare_schedules(make_A(ns[-1]), make_B(ns[-1]), p, ns[-1])


if __name__ == "__main__":
    benchmark_part_b(ns=(40, 60, 80), p=4)
