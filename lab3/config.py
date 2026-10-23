# -*- coding: utf-8 -*-
"""Налаштування ЛР №3. Порти/адреси НЕ зашиті в код: беруться звідси,
з змінних середовища або з аргументів командного рядка скриптів."""
import os

VARIANT = 20                                                # номер варіанта ЛР №2 (Частина А)
SEED = int(os.environ.get("LAB3_SEED", "2026"))             # seed генератора даних

HOST = os.environ.get("LAB3_HOST", "127.0.0.1")             # адреса СЕРВЕРА (для клієнта)
BIND = os.environ.get("LAB3_BIND", "0.0.0.0")               # де слухає сервер (0.0.0.0 = усі інтерфейси)
REST_PORT = int(os.environ.get("LAB3_REST_PORT", "8000"))
GRPC_PORT = int(os.environ.get("LAB3_GRPC_PORT", "50051"))

# gRPC за замовчуванням обмежує повідомлення 4 МБ; матриця Y3 при n>=700 більша
MAX_MSG_BYTES = 128 * 1024 * 1024
