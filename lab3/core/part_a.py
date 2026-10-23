# -*- coding: utf-8 -*-
"""
ЛР №2. Частина А. Варіант 20.
=================================================================
Обчислювальний вираз (варіант 20, Додаток А):

    b_i = 20 / (i^3 + 20),           i = 1..n           (вектор b)
    y1  = A * b                                         (матрично-векторний добуток)
    d   = 20*b1 - c1                                    (b1, c1 - незалежні вхідні вектори)
    y2  = A1 * d
    C2[i][j] = 20 / (i^3 - j^3 + 2), i,j = 1..n          (генерація елементів матриці)
    Y3  = A2*C2 - B2

    x = ( y1' * ((y2'*y2)*Y3) + y2'*Y3^3 + (y2'*y2) )  *  ( (y2'*Y3*y2 + 1) * y1 )

Типи підвиразів (обов'язковий п.1 етапу 6.1):
    b, d, y1, y2       - вектори (n x 1)
    A, A1, A2, B2, C2  - матриці (n x n), вводяться / генеруються
    Y3                 - матриця (n x n)
    y2'*y2             - скаляр
    (y2'*y2)*Y3        - матриця (n x n)
    y1' * (матриця)    - вектор-рядок (1 x n)
    Y3^3               - матриця (n x n) = Y3*Y3*Y3
    y2' * Y3^3         - вектор-рядок (1 x n)
    "лівий блок"       - вектор-рядок (1 x n): сума двох рядків + скаляр (broadcast)
    y2'*Y3*y2          - скаляр
    "правий блок"      - вектор-стовпець (n x 1)
    x                  - скаляр (число), результат добутку (1xn)*(nx1)

DAG (функціональна декомпозиція, велика зернистість Dᴸ):

    b1, c1 ---> d ---> y2 = A1*d ------\
                                         \
    b -----------------> y1 = A*b -------+---> x (фінальна редукція)
                                         /
    C2 --> Y3 = A2*C2 - B2 ------------/

    Гілки y1, y2, Y3 обчислюються НЕЗАЛЕЖНО одна від одної (немає спільних даних
    між ними) - це природний кандидат на OpenMP sections / паралельні tasks.
    Обчислення x можливе лише після завершення всіх трьох гілок (точка синхронізації).

Реалізовано дві схеми паралелізму:
    * Dᴹ (середньоблокова, ОСНОВНА для цього бенчмарку) - рядки матриць A, A1, A2
      діляться на p блоків, кожен worker обчислює свій блок рядків
      матрично-векторного/матрично-матричного добутку.  Це масштабується на
      p = 1,2,4,8 і саме на ній вимірюються T/S/E/O.
    * Dᴸ (великоблокова) - демонстраційна: гілки y1/y2/Y3 запускаються як три
      незалежні задачі одного пулу (аналог sections). Дивись demo_large_grained().
"""

import math
import os
import random
import time
from concurrent.futures import ProcessPoolExecutor

# =================================================================
# 1. Генерація вхідних даних
# =================================================================

def gen_b(n):
    """b_i = 20/(i^3+20), i=1..n - усі b_i обчислюються незалежно (fine-grained)."""
    return [20.0 / (i ** 3 + 20) for i in range(1, n + 1)]


def gen_C2(n):
    """C2[i][j] = 20/(i^3 - j^3 + 2) - генерація незалежна по (i,j)."""
    C2 = [[0.0] * n for _ in range(n)]
    for i in range(1, n + 1):
        for j in range(1, n + 1):
            denom = i ** 3 - j ** 3 + 2
            if denom == 0:
                denom = 1e-9  # захист від ділення на нуль (структурно майже не трапляється)
            C2[i - 1][j - 1] = 20.0 / denom
    return C2


def gen_random_vector(n, rng):
    return [rng.uniform(-1.0, 1.0) for _ in range(n)]


def gen_random_matrix(n, rng):
    return [[rng.uniform(-1.0, 1.0) for _ in range(n)] for _ in range(n)]


def generate_inputs(n, seed=42):
    """A, A1, A2, B2, b1, c1 - вводяться з клавіатури або генеруються випадково.
    Тут - псевдовипадково з фіксованим seed для відтворюваності."""
    rng = random.Random(seed)
    return dict(
        n=n,
        A=gen_random_matrix(n, rng),
        A1=gen_random_matrix(n, rng),
        A2=gen_random_matrix(n, rng),
        B2=gen_random_matrix(n, rng),
        b1=gen_random_vector(n, rng),
        c1=gen_random_vector(n, rng),
        b=gen_b(n),
        C2=gen_C2(n),
    )


# =================================================================
# 2. Базові лінійно-алгебраїчні операції (наївні, для чесного порівняння з паралельною версією)
# =================================================================

def matvec(A, v):
    """y = A*v, послідовно."""
    n = len(v)
    out = []
    for row in A:
        s = 0.0
        for j in range(n):
            s += row[j] * v[j]
        out.append(s)
    return out


def vec_transposed_matmul(v, M):
    """v' * M -> вектор-рядок довжини m (v: n, M: n x m)."""
    n = len(v)
    m = len(M[0])
    out = [0.0] * m
    for i in range(n):
        vi = v[i]
        if vi == 0.0:
            continue
        Mi = M[i]
        for j in range(m):
            out[j] += vi * Mi[j]
    return out


def matmul(A, B):
    n = len(B)
    m = len(B[0])
    out = [[0.0] * m for _ in range(len(A))]
    for i, Ai in enumerate(A):
        row_out = out[i]
        for k in range(n):
            aik = Ai[k]
            if aik == 0.0:
                continue
            Bk = B[k]
            for j in range(m):
                row_out[j] += aik * Bk[j]
    return out


def mat_sub(A, B):
    return [[A[i][j] - B[i][j] for j in range(len(A[0]))] for i in range(len(A))]


def dot(u, v):
    return sum(x * y for x, y in zip(u, v))


def vec_scale_add(alpha, u, beta, v):
    return [alpha * ui + beta * vi for ui, vi in zip(u, v)]


def mat_pow3(Y, matmul_fn=matmul):
    """Y^3 = Y*Y*Y."""
    Y2 = matmul_fn(Y, Y)
    Y3 = matmul_fn(Y2, Y)
    return Y3


# =================================================================
# 3. Три незалежні функціональні гілки DAG
# =================================================================

def branch_y1(A, b, matvec_fn=matvec):
    return matvec_fn(A, b)


def branch_y2(A1, b1, c1, matvec_fn=matvec):
    d = vec_scale_add(20.0, b1, -1.0, c1)
    return matvec_fn(A1, d)


def branch_Y3(A2, C2, B2, matmul_fn=matmul):
    return mat_sub(matmul_fn(A2, C2), B2)


def compute_x(y1, y2, Y3, matmul_fn=matmul):
    """Фінальна редукція за готовими y1, y2, Y3 (див. розбір типів вище)."""
    n = len(y1)
    yy = dot(y2, y2)                                   # скаляр y2'*y2
    scaled_Y3 = [[yy * Y3[i][j] for j in range(n)] for i in range(n)]
    term1 = vec_transposed_matmul(y1, scaled_Y3)        # 1xn: y1' * (yy*Y3)
    Y33 = mat_pow3(Y3, matmul_fn)
    term2 = vec_transposed_matmul(y2, Y33)              # 1xn: y2' * Y3^3
    left = [term1[j] + term2[j] + yy for j in range(n)]  # + yy розповсюджується (broadcast)

    Y3y2 = matvec(Y3, y2)
    y2Y3y2 = dot(y2, Y3y2)                              # скаляр y2'*Y3*y2
    right = [(y2Y3y2 + 1.0) * y1[i] for i in range(n)]  # (y2'Y3y2 + 1)*y1

    return dot(left, right)


def sequential_part_a(inp):
    y1 = branch_y1(inp['A'], inp['b'])
    y2 = branch_y2(inp['A1'], inp['b1'], inp['c1'])
    Y3 = branch_Y3(inp['A2'], inp['C2'], inp['B2'])
    x = compute_x(y1, y2, Y3)
    return x, y1, y2, Y3


# =================================================================
# 4. Середньоблокова паралельна реалізація (Dᴹ) - розподіл рядків між p worker-ами
# =================================================================

def _worker_matvec(args):
    A_chunk, v = args
    n = len(v)
    out = []
    for row in A_chunk:
        s = 0.0
        for j in range(n):
            s += row[j] * v[j]
        out.append(s)
    return out


def parallel_matvec(A, v, p):
    n = len(A)
    chunk = max(1, (n + p - 1) // p)
    chunks = [A[i:i + chunk] for i in range(0, n, chunk)]
    with ProcessPoolExecutor(max_workers=p) as ex:
        results = list(ex.map(_worker_matvec, [(c, v) for c in chunks]))
    out = []
    for r in results:
        out.extend(r)
    return out


def _worker_matmul(args):
    A_chunk, B = args
    n = len(B)
    m = len(B[0])
    out = []
    for Ai in A_chunk:
        row_out = [0.0] * m
        for k in range(n):
            aik = Ai[k]
            if aik == 0.0:
                continue
            Bk = B[k]
            for j in range(m):
                row_out[j] += aik * Bk[j]
        out.append(row_out)
    return out


def parallel_matmul(A, B, p):
    n = len(A)
    chunk = max(1, (n + p - 1) // p)
    chunks = [A[i:i + chunk] for i in range(0, n, chunk)]
    with ProcessPoolExecutor(max_workers=p) as ex:
        results = list(ex.map(_worker_matmul, [(c, B) for c in chunks]))
    out = []
    for r in results:
        out.extend(r)
    return out


def parallel_part_a(inp, p):
    """Dᴹ: паралелізуємо всі важкі матрично-векторні/матричні добутки за рядками."""
    y1 = parallel_matvec(inp['A'], inp['b'], p)
    d = vec_scale_add(20.0, inp['b1'], -1.0, inp['c1'])
    y2 = parallel_matvec(inp['A1'], d, p)
    AC2 = parallel_matmul(inp['A2'], inp['C2'], p)
    Y3 = mat_sub(AC2, inp['B2'])
    matmul_fn = (lambda X, Y: parallel_matmul(X, Y, p)) if p > 1 else matmul
    x = compute_x(y1, y2, Y3, matmul_fn)
    return x, y1, y2, Y3


# =================================================================
# 5. Демонстрація великоблокової схеми (Dᴸ) - три незалежні "sections"
# =================================================================

def _section_y1(args):
    A, b = args
    return branch_y1(A, b)


def _section_y2(args):
    A1, b1, c1 = args
    return branch_y2(A1, b1, c1)


def _section_Y3(args):
    A2, C2, B2 = args
    return branch_Y3(A2, C2, B2)


def demo_large_grained(inp):
    """Аналог OpenMP sections: 3 незалежні функціональні гілки в одному пулі з 3 worker-ами."""
    with ProcessPoolExecutor(max_workers=3) as ex:
        f1 = ex.submit(_section_y1, (inp['A'], inp['b']))
        f2 = ex.submit(_section_y2, (inp['A1'], inp['b1'], inp['c1']))
        f3 = ex.submit(_section_Y3, (inp['A2'], inp['C2'], inp['B2']))
        y1, y2, Y3 = f1.result(), f2.result(), f3.result()
    x = compute_x(y1, y2, Y3)
    return x, y1, y2, Y3


# =================================================================
# 6. Бенчмарк: T_p, S_p, E_p, O_p для p = 1,2,4,8
# =================================================================

def benchmark(n=250, seed=42, workers=(1, 2, 4, 8)):
    logical_cores = os.cpu_count()
    print(f"Логічних ядер CPU у системі: {logical_cores}")
    if logical_cores is not None and max(workers) > logical_cores:
        print(f"УВАГА: запитано p={max(workers)} worker-ів, що більше за кількість "
              f"логічних ядер ({logical_cores}). Це слід зазначити в аналізі результатів.")

    inp = generate_inputs(n, seed)

    t0 = time.perf_counter()
    x_ref, *_ = sequential_part_a(inp)
    T1 = time.perf_counter() - t0
    print(f"\nЧастина А, варіант 20, n={n}")
    print(f"T1 (послідовно) = {T1:.4f} c,  x = {x_ref:.6g}\n")

    print(f"{'p':>3} | {'Tp, c':>10} | {'Sp':>8} | {'Ep':>8} | {'Op, c':>10}")
    print("-" * 52)
    table = []
    for p in workers:
        if p == 1:
            Tp = T1
        else:
            t0 = time.perf_counter()
            x_par, *_ = parallel_part_a(inp, p)
            Tp = time.perf_counter() - t0
            rel_err = abs(x_par - x_ref) / max(1.0, abs(x_ref))
            assert rel_err < 1e-6, f"Розбіжність результату при p={p}: {rel_err}"
        Sp = T1 / Tp
        Ep = Sp / p
        Op = p * Tp - T1
        table.append((p, Tp, Sp, Ep, Op))
        print(f"{p:>3} | {Tp:>10.4f} | {Sp:>8.3f} | {Ep:>8.3f} | {Op:>10.4f}")
    return table


if __name__ == "__main__":
    benchmark(n=250)
