import threading
import queue
import random
import time


# ==========================================================
# КЛАС ПРОЦЕСУ
# ==========================================================

class Process:
    def __init__(self, process_id, stream):
        self.process_id = process_id
        self.stream = stream

    def __str__(self):
        return f"P{self.process_id}(потік {self.stream})"


# ==========================================================
# ЧЕРГИ ДВОХ ПОТОКІВ
# ==========================================================

queue1 = queue.Queue()
queue2 = queue.Queue()


# ==========================================================
# МАКСИМАЛЬНІ ДОПУСТИМІ РОЗМІРИ ЧЕРГ
# ==========================================================

MAX_QUEUE_1 = 5
MAX_QUEUE_2 = 7


# ==========================================================
# СПІЛЬНИЙ ЛІЧИЛЬНИК ПРОЦЕСІВ
# ==========================================================

counter = 0

# Блокування для захисту спільного лічильника
counter_lock = threading.Lock()


# ==========================================================
# ЗМІННІ ДЛЯ СТАТИСТИКИ
# ==========================================================

max_queue_1_reached = 0
max_queue_2_reached = 0

stats_lock = threading.Lock()


# ==========================================================
# СТВОРЕННЯ ПРОЦЕСІВ
# ==========================================================

def create_process(stream, process_queue, max_queue):

    global counter
    global max_queue_1_reached
    global max_queue_2_reached

    for _ in range(30):

        # Випадкова затримка появи процесу
        time.sleep(random.uniform(0.05, 0.2))

        # Захищаємо спільний лічильник
        with counter_lock:
            counter += 1
            process_id = counter

        # Створюємо процес
        process = Process(process_id, stream)

        # Перевіряємо, чи є місце в черзі
        if process_queue.qsize() < max_queue:

            process_queue.put(process)

            current_size = process_queue.qsize()

            # Запам'ятовуємо максимальний фактичний розмір черги
            with stats_lock:

                if stream == 1:
                    if current_size > max_queue_1_reached:
                        max_queue_1_reached = current_size

                else:
                    if current_size > max_queue_2_reached:
                        max_queue_2_reached = current_size

            print(
                f"Створено {process} -> "
                f"черга {stream}, "
                f"розмір: {current_size}"
            )

        else:

            print(
                f"Черга {stream} переповнена: "
                f"{process} відхилено"
            )


# ==========================================================
# РОБОТА CPU
# ==========================================================

def cpu_worker(
        cpu_number,
        own_queue,
        own_max,
        other_queue,
        other_max
):

    for _ in range(30):

        process = None

        own_size = own_queue.qsize()
        other_size = other_queue.qsize()

        # --------------------------------------------------
        # 1. Спочатку CPU бере процес зі своєї черги
        # --------------------------------------------------

        if own_size > 0:

            try:
                process = own_queue.get_nowait()

                print(
                    f"CPU {cpu_number} обробляє "
                    f"{process} зі своєї черги"
                )

            except queue.Empty:
                pass

        # --------------------------------------------------
        # 2. Якщо власна черга не перевищує допустимий
        #    розмір, а чужа черга перевищує свій розмір,
        #    CPU може допомогти іншому потоку
        # --------------------------------------------------

        elif (
            own_size <= own_max
            and other_size > other_max
        ):

            try:
                process = other_queue.get_nowait()

                print(
                    f"CPU {cpu_number} допомагає "
                    f"іншому потоку: обробляє {process}"
                )

            except queue.Empty:
                pass

        # --------------------------------------------------
        # 3. Якщо процесу немає
        # --------------------------------------------------

        if process is not None:

            # Імітація часу обробки процесу
            time.sleep(random.uniform(0.1, 0.3))

            print(
                f"CPU {cpu_number} завершив {process}"
            )

        else:

            # Якщо черги порожні — CPU очікує
            time.sleep(0.1)


# ==========================================================
# ГОЛОВНА ФУНКЦІЯ
# ==========================================================

def main():

    # Початок вимірювання часу
    start_time = time.perf_counter()

    print("=" * 60)
    print("МОДЕЛЮВАННЯ ОБСЛУГОВУВАННЯ ДВОХ ПОТОКІВ")
    print("=" * 60)

    print(f"Максимальний розмір черги 1: {MAX_QUEUE_1}")
    print(f"Максимальний розмір черги 2: {MAX_QUEUE_2}")
    print()

    # ======================================================
    # СТВОРЕННЯ ПОТОКІВ
    # ======================================================

    producer1 = threading.Thread(
        target=create_process,
        args=(
            1,
            queue1,
            MAX_QUEUE_1
        ),
        name="Producer-1"
    )

    producer2 = threading.Thread(
        target=create_process,
        args=(
            2,
            queue2,
            MAX_QUEUE_2
        ),
        name="Producer-2"
    )

    cpu1 = threading.Thread(
        target=cpu_worker,
        args=(
            1,
            queue1,
            MAX_QUEUE_1,
            queue2,
            MAX_QUEUE_2
        ),
        name="CPU-1"
    )

    cpu2 = threading.Thread(
        target=cpu_worker,
        args=(
            2,
            queue2,
            MAX_QUEUE_2,
            queue1,
            MAX_QUEUE_1
        ),
        name="CPU-2"
    )

    # ======================================================
    # ЗАПУСК ПОТОКІВ
    # ======================================================

    producer1.start()
    producer2.start()

    cpu1.start()
    cpu2.start()

    # ======================================================
    # ОЧІКУВАННЯ ЗАВЕРШЕННЯ ВСІХ ПОТОКІВ
    # ======================================================

    producer1.join()
    producer2.join()

    cpu1.join()
    cpu2.join()

    # ======================================================
    # ЗАКІНЧЕННЯ ВИМІРЮВАННЯ
    # ======================================================

    end_time = time.perf_counter()

    execution_time = end_time - start_time

    # ======================================================
    # ПІДСУМКОВА СТАТИСТИКА
    # ======================================================

    print()
    print("=" * 60)
    print("РЕЗУЛЬТАТИ МОДЕЛЮВАННЯ")
    print("=" * 60)

    print(
        f"Фактичний максимальний розмір "
        f"черги 1: {max_queue_1_reached}"
    )

    print(
        f"Фактичний максимальний розмір "
        f"черги 2: {max_queue_2_reached}"
    )

    print(
        f"Заданий максимальний розмір "
        f"черги 1: {MAX_QUEUE_1}"
    )

    print(
        f"Заданий максимальний розмір "
        f"черги 2: {MAX_QUEUE_2}"
    )

    print(
        f"Кількість створених процесів: {counter}"
    )

    print(
        f"Кількість потоків: 4"
    )

    print(
        f"Час виконання: {execution_time:.4f} секунд"
    )

    print(
        f"Залишок у черзі 1: {queue1.qsize()}"
    )

    print(
        f"Залишок у черзі 2: {queue2.qsize()}"
    )

    print()
    print("Моделювання завершено.")


# ==========================================================
# ЗАПУСК ПРОГРАМИ
# ==========================================================

if __name__ == "__main__":
    main()