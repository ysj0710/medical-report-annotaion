from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Set

from fastapi import WebSocket


@dataclass(eq=False)
class CollaborationSocketClient:
    websocket: WebSocket
    report_id: int
    user_id: int
    username: str
    role: str


@dataclass(eq=False)
class ReportUpdatesSocketClient:
    websocket: WebSocket
    user_id: int
    username: str
    role: str


class CollaborationSocketHub:
    def __init__(self) -> None:
        self._clients_by_report: Dict[int, Set[CollaborationSocketClient]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, client: CollaborationSocketClient) -> None:
        await client.websocket.accept()
        async with self._lock:
            self._clients_by_report[client.report_id].add(client)

    async def disconnect(self, client: CollaborationSocketClient) -> None:
        async with self._lock:
            clients = self._clients_by_report.get(client.report_id)
            if not clients:
                return
            clients.discard(client)
            if not clients:
                self._clients_by_report.pop(client.report_id, None)

    async def get_clients(self, report_id: int) -> List[CollaborationSocketClient]:
        async with self._lock:
            return list(self._clients_by_report.get(report_id, ()))


class ReportUpdatesSocketHub:
    def __init__(self) -> None:
        self._clients: Set[ReportUpdatesSocketClient] = set()
        self._lock = asyncio.Lock()

    async def connect(self, client: ReportUpdatesSocketClient) -> None:
        await client.websocket.accept()
        async with self._lock:
            self._clients.add(client)

    async def disconnect(self, client: ReportUpdatesSocketClient) -> None:
        async with self._lock:
            self._clients.discard(client)

    async def get_clients(self) -> List[ReportUpdatesSocketClient]:
        async with self._lock:
            return list(self._clients)


collaboration_socket_hub = CollaborationSocketHub()
report_updates_socket_hub = ReportUpdatesSocketHub()
