# ЛР №3 — REST та gRPC (варіант 20, Python)

Математичне ядро — **без змін** з ЛР №2 (`core/part_a.py`, Частина А: вираз варіанта 20).
Мережевий шар лише викликає його (`core/core_api.py`), тому різниця в часі — це саме архітектура/мережа/серіалізація.

```
lab3/
  core/          part_a.py (з ЛР №2, не змінений) + core_api.py (гілки FULL/Y1/Y2/Y3/BLOCK, checksum)
  contracts/     compute.proto  (контракт gRPC із методички)
  config.py      порти/адреси (не зашиті в код)
  service.py     спільна логіка серверів: валідація, інфо про вузол, структурований журнал
  rest_server.py / rest_client.py     FastAPI + Uvicorn / httpx
  grpc_server.py / grpc_client.py     grpcio + згенеровані stub-и
  hybrid.py      розподілене виконання H1/H3 і блочні RPC
  local_baseline.py   Частина I (L-C на клієнті, L-S на сервері)
  benchmark.py   Частини II–IV + таблиці + паспорт benchmark
  part5_demo.py  Частина V (timeout, сервер вимкнено, два клієнти)
  summarize.py   підсумкові таблиці з results/*.csv
```

## 1. Встановлення (на ОБОХ ПК)
```
pip install -r requirements.txt
python gen_proto.py          # генерує contracts/compute_pb2*.py (один раз на кожному ПК)
```

## 2. Запуск (два фізичні ПК в одній мережі)
Дізнайтесь IP сервера (`ipconfig` / `ip a`). Дозвольте Python у брандмауері (приватна мережа) або порти 8000 і 50051.

**Сервер:**
```
python rest_server.py --port 8000 --workers 2
python grpc_server.py --port 50051 --workers 2      # у другому терміналі
```
**Клієнт:**
```
python local_baseline.py --label client --ns 100,150,200      # Частина I: T_client
# на сервері: python local_baseline.py --label server --ns 100,150,200
#   -> скопіюйте results/local_server.csv на клієнт у results/  (це T_server_local, L-S)
python benchmark.py --host <IP_СЕРВЕРА> --ns 100,150,200 --repeats 10
```
`benchmark.py` сам виконає: L-C → Ping (20×) → R-REST/R-gRPC → hybrid H1/H3 через REST і gRPC → зернистість RPC → паспорт → таблиці (`results/summary.md`, `results/results.csv`, `results/results_granularity.csv`, `results/passport.json`).

**Частина V:**
```
python part5_demo.py timeout     --host <IP> --n 150      # timeout < часу обчислення
python part5_demo.py two-clients --host <IP> --n 150      # два клієнти; дивіться logs/server.log на сервері
# зупиніть обидва сервери:
python part5_demo.py down        --host <IP>
```
Журнал сервера (`logs/server.log`) містить requestId, protocol, client, n, branch, serverComputeMs, startTs/endTs, status.

## 3. Відповідність завданню
| Вимога методички | Де |
|---|---|
| Ping/RTT, GetServerInfo, ComputeFull, ComputeBranch | `/api/v1/health|info|compute|branch` та `compute.proto` |
| T_server лише ядро; T_e2e на клієнті; T_overhead = T_e2e − T_server | `core_api.execute` / `benchmark.py` / `summarize.py` |
| warm-up (3) + 10 повторів, медіана, CSV | `benchmark.py` |
| Режим P (variant, n, seed); сервер відтворює дані тим самим генератором | усі сервіси. **Режим D (необов'язковий) не реалізовано** |
| Hybrid H1 і H3, перевірка результату проти еталона | `hybrid.py` |
| Зернистість: 1 великий RPC vs 4 блокові vs дрібнозернистий (малий n) | `benchmark.py --gran-n --fine-n` |
| timeout, сервер вимкнено, два клієнти | `part5_demo.py` |

Мапінг сценаріїв на таблицю 9.2: `H-REST`/`H-gRPC` у методичці = `H1-*` і `H3-*` тут (дві схеми розподілу).

## 4. Про вибір схеми розподілу (важливо для аналізу)
Трудомісткість у Частині А: y1, y2 ~ n² (дешеві), **Y3 = A2·C2−B2 ~ n³**, фінальний `compute_x` ~ 2n³ і залежить від усіх трьох.
* **H1** (клієнт: y1,y2 — сервер: Y3): критичний шлях Y3 → x. Клієнт майже весь час чекає, тож **виграшу очікувати не слід** — це варто показати й пояснити в звіті (метод. вказівки: вибір розподілу «не механічний»).
* **H3**: Y3 ділиться за рядками — клієнт рахує `Y3[0:k)`, сервер `Y3[k:n)` одночасно; `--client-share auto` бере k з відношення T_client/T_server_local (якщо є `local_server.csv`), інакше 0.5.
Навіть у H3 `compute_x` (2n³) лишається на клієнті, тож за законом Амдала виграш обмежений.

## 5. Що перевірено, а що ні
* **Перевірено в моєму середовищі:** математика (core_api), розбиття/злиття блоків Y3, гібридне перекриття, логіка benchmark/summarize — через псевдо-транспорт `loopback` (`python benchmark.py --protocols loopback --ns 60 --repeats 3 --fine-n 12`); усі результати збіглися з еталоном.
* **НЕ запускалося мною:** `rest_server.py`, `rest_client.py`, `grpc_server.py`, `grpc_client.py` — у моєму середовищі немає інтернету для встановлення FastAPI/grpcio. Код написано за документацією; якщо при першому запуску буде помилка — надішліть текст помилки, я виправлю.
* Результати з `localhost` — лише для налагодження; фінальний експеримент — на двох ПК (методичка забороняє localhost як фінальний).

## 6. Типові проблеми
* `ModuleNotFoundError: compute_pb2` → не виконано `python gen_proto.py`.
* Клієнт не з'єднується → брандмауер / не той IP / сервер слухає не на `0.0.0.0`.
* gRPC `RESOURCE_EXHAUSTED` на великих n → ліміт повідомлення вже піднято до 128 МБ (`config.py`); для REST велика матриця у JSON — це і є ефект, який досліджується.
* Перше обчислення на кожному процесі-виконавці сервера генерує дані (кеш) — тому warm-up обов'язковий.
