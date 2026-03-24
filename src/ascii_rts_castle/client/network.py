"""
Сетевой клиент для подключения к игровому серверу.

Этап 6: полная реализация asyncio TCP клиента с обработкой сообщений.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Optional

from ascii_rts_castle.shared.messages import (
    ClientToServerMessage,
    ErrorMessage,
    GameOver,
    JoinAccepted,
    ServerToClientMessage,
    StateSnapshot,
    extract_framed_message,
    frame_message,
)
from ascii_rts_castle.shared.models import GameState, PlayerId, TeamId


@dataclass
class ClientGameContext:
    """
    Локальное состояние клиента:
    - кто мы (player_id, team_id);
    - последнее полученное состояние игры;
    - флаги завершения игры/отключения;
    - лог событий;
    - выбранная линия.
    """

    player_id: Optional[PlayerId] = None
    team_id: Optional[TeamId] = None

    last_state: Optional[GameState] = None
    last_tick: int = 0

    game_over: bool = False
    game_over_reason: str = ""
    winner_team_id: Optional[TeamId] = None

    disconnected: bool = False

    event_log: Deque[str] = field(default_factory=lambda: deque(maxlen=50))
    
    selected_lane_index: int = 0  # Индекс выбранной линии (0-based)
    show_help: bool = False  # Показывать ли экран подсказки


class NetworkClient:
    """
    Сетевой клиент для подключения к игровому серверу.

    - Использует asyncio.open_connection для TCP.
    - Читает length-prefixed сообщения, раскладывает их в очередь incoming.
    """

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.incoming: asyncio.Queue[ServerToClientMessage] = asyncio.Queue()
        self._buffer: bytes = b""
        self._reader_task: Optional[asyncio.Task[None]] = None
        self.connected: bool = False

    async def connect(self) -> None:
        """Подключиться к серверу и запустить фоновый reader."""
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
        self.connected = True
        self._reader_task = asyncio.create_task(self._reader_loop())

    async def _reader_loop(self) -> None:
        """Фоновый цикл чтения сообщений от сервера."""
        assert self.reader is not None
        try:
            while True:
                data = await self.reader.read(4096)
                if not data:
                    # EOF — сервер разорвал соединение
                    break

                self._buffer += data

                while True:
                    msg_any, self._buffer = extract_framed_message(self._buffer)
                    if msg_any is None:
                        break
                    # Фильтруем только серверные сообщения
                    if isinstance(msg_any, (JoinAccepted, StateSnapshot, GameOver, ErrorMessage)):
                        await self.incoming.put(msg_any)
                    else:
                        # неожиданный тип — можно залогировать и игнорировать
                        # (но на практике сервер шлёт только серверные типы)
                        continue
        finally:
            self.connected = False
            # Положим ErrorMessage, чтобы внешний код мог узнать о разрыве
            await self.incoming.put(ErrorMessage(message="Disconnected from server"))

    async def send(self, msg: ClientToServerMessage) -> None:
        """Отправить сообщение на сервер."""
        if not self.connected or self.writer is None:
            raise RuntimeError("NetworkClient is not connected")
        data = frame_message(msg)
        self.writer.write(data)
        await self.writer.drain()

    async def close(self) -> None:
        """Закрыть соединение и остановить фоновые задачи."""
        # Остановить reader_task
        if self._reader_task is not None:
            self._reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reader_task
            self._reader_task = None

        # Закрыть writer
        if self.writer is not None:
            self.writer.close()
            with contextlib.suppress(Exception):
                await self.writer.wait_closed()
            self.writer = None

        self.connected = False


async def process_incoming_messages(client: NetworkClient, ctx: ClientGameContext) -> None:
    """
    Забрать все доступные входящие сообщения и обновить контекст клиента.
    Не блокирует (использует get_nowait).
    """
    while True:
        try:
            msg = client.incoming.get_nowait()
        except asyncio.QueueEmpty:
            break

        if isinstance(msg, JoinAccepted):
            ctx.player_id = msg.player_id
            ctx.team_id = msg.team_id

        elif isinstance(msg, StateSnapshot):
            ctx.last_state = msg.state
            ctx.last_tick = msg.tick
            if msg.events:
                for e in msg.events:
                    ctx.event_log.append(e)

        elif isinstance(msg, GameOver):
            ctx.game_over = True
            ctx.winner_team_id = msg.winner_team_id
            ctx.game_over_reason = msg.reason

        elif isinstance(msg, ErrorMessage):
            # Ошибка или разрыв соединения
            ctx.game_over = True
            ctx.game_over_reason = msg.message
            ctx.disconnected = True


async def wait_for_join_accepted(
    client: NetworkClient,
    ctx: ClientGameContext,
    timeout: float = 10.0,
) -> JoinAccepted:
    """
    Ожидает JoinAccepted от сервера.
    При получении ErrorMessage выбрасывает исключение.
    """
    while True:
        msg_any = await asyncio.wait_for(client.incoming.get(), timeout=timeout)
        if isinstance(msg_any, JoinAccepted):
            ctx.player_id = msg_any.player_id
            ctx.team_id = msg_any.team_id
            return msg_any
        if isinstance(msg_any, ErrorMessage):
            ctx.game_over = True
            ctx.game_over_reason = msg_any.message
            raise RuntimeError(f"Failed to join: {msg_any.message}")
        # В теории, других сообщений до JoinAccepted быть не должно — игнорируем.
