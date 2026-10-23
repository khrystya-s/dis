# -*- coding: utf-8 -*-
"""Спільний інтерфейс клієнтів REST і gRPC: benchmark працює з обома однаково."""
from dataclasses import dataclass, field


class TransportError(Exception):
    """Будь-яка помилка віддаленого виклику."""


class TransportTimeout(TransportError):
    """Перевищено timeout."""


class TransportUnavailable(TransportError):
    """Сервер недоступний (нема з'єднання)."""


@dataclass
class Reply:
    request_id: str
    status: str
    kind: str
    rows: int
    cols: int
    values: list = field(default_factory=list)
    checksum: float = 0.0
    server_ms: float = 0.0
    node: str = ""
