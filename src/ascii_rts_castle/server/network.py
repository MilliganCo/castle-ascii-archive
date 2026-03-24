"""
Сетевой код сервера (TCP, управление клиентами).

Этап 5: полная реализация asyncio TCP сервера с игровым циклом.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, Literal, Optional, Set

from ascii_rts_castle.config import GameConfig
from ascii_rts_castle.server.engine import GameEngine
from ascii_rts_castle.shared.commands import GameCommand
from ascii_rts_castle.shared.messages import (
    AnyMessage,
    ErrorMessage,
    GameOver,
    JoinAccepted,
    JoinRequest,
    PlayerCommandMessage,
    ReadyToStart,
    ServerToClientMessage,
    StateSnapshot,
    extract_framed_message,
    frame_message,
)
from ascii_rts_castle.shared.models import PlayerId, TeamId

logger = logging.getLogger(__name__)

DEFAULT_TICK_RATE: float = 20.0
DEFAULT_SNAPSHOT_INTERVAL_TICKS: int = 2
DEFAULT_MAX_PLAYERS: int = 4
DEFAULT_REQUIRED_PLAYERS: int = 2

ServerState = Literal["lobby", "running", "finished"]


@dataclass
class ClientSession:
    """Сессия подключённого клиента."""

    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    player_id: Optional[PlayerId] = None
    team_id: Optional[TeamId] = None
    name: str = ""


class GameServer:
    """
    Сервер игры: управляет подключениями, обрабатывает сообщения,
    крутит игровой цикл и рассылает снапшоты состояния.
    """

    def __init__(
        self,
        config: GameConfig,
        host: str = "0.0.0.0",
        port: int = 8765,
        max_players: int = DEFAULT_MAX_PLAYERS,
        required_players: int = DEFAULT_REQUIRED_PLAYERS,
        tick_rate: float = DEFAULT_TICK_RATE,
        snapshot_interval_ticks: int = DEFAULT_SNAPSHOT_INTERVAL_TICKS,
    ) -> None:
        self.config = config
        self.host = host
        self.port = port
        self.max_players = max_players
        self.required_players = required_players
        self.tick_rate = tick_rate
        self.snapshot_interval_ticks = snapshot_interval_ticks

        self.state: ServerState = "lobby"
        self._server: Optional[asyncio.AbstractServer] = None

        self._next_player_id: int = 1
        self.sessions_by_player: Dict[PlayerId, ClientSession] = {}
        self._all_sessions: Set[ClientSession] = set()

        self.players_team_mapping: Dict[PlayerId, TeamId] = {}
        self.ready_players: Set[PlayerId] = set()

        self.engine: Optional[GameEngine] = None
        self._command_queue: asyncio.Queue[GameCommand] = asyncio.Queue()

        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        """Запустить TCP сервер."""
        self._server = await asyncio.start_server(
            self._handle_client,
            host=self.host,
            port=self.port,
        )
        addr = ", ".join(str(sock.getsockname()) for sock in self._server.sockets or [])
        logger.info("GameServer started on %s", addr)

    async def run_forever(self) -> None:
        """Запустить сервер и ждать остановки."""
        await self._stop_event.wait()

    async def stop(self) -> None:
        """Остановить сервер и закрыть все соединения."""
        logger.info("Stopping GameServer...")
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
        # Закрыть все клиентские соединения
        for session in list(self._all_sessions):
            try:
                session.writer.close()
                await session.writer.wait_closed()
            except Exception:
                pass
        self._all_sessions.clear()
        logger.info("GameServer stopped")

    def _request_stop(self) -> None:
        """Запросить остановку сервера."""
        if not self._stop_event.is_set():
            self._stop_event.set()

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Обработчик подключения клиента."""
        addr = writer.get_extra_info("peername")
        logger.info("New connection from %r", addr)

        session = ClientSession(reader=reader, writer=writer)
        self._all_sessions.add(session)

        buffer = b""

        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    logger.info("Client %r disconnected", addr)
                    break

                buffer += data

                while True:
                    msg, buffer = extract_framed_message(buffer)
                    if msg is None:
                        break
                    await self._handle_message_from_client(session, msg)

        except asyncio.CancelledError:
            logger.info("Client handler cancelled for %r", addr)
        except Exception as exc:
            logger.exception("Exception in _handle_client: %s", exc)
        finally:
            # Удалить сессию
            if session.player_id is not None:
                self.sessions_by_player.pop(session.player_id, None)
                self.ready_players.discard(session.player_id)
                self.players_team_mapping.pop(session.player_id, None)
            self._all_sessions.discard(session)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            logger.info("Connection closed for %r", addr)

    async def _handle_message_from_client(
        self,
        session: ClientSession,
        msg: AnyMessage,
    ) -> None:
        """Обработать сообщение от клиента."""
        if isinstance(msg, JoinRequest):
            await self._on_join_request(session, msg)
        elif isinstance(msg, ReadyToStart):
            await self._on_ready_to_start(session, msg)
        elif isinstance(msg, PlayerCommandMessage):
            await self._on_player_command(session, msg)
        else:
            # Игнорируем неподдерживаемые/неожиданные сообщения
            logger.warning("Unexpected message from client: %r", msg)

    async def _on_join_request(self, session: ClientSession, msg: JoinRequest) -> None:
        """Обработать запрос на подключение."""
        if self.state != "lobby":
            # Игра уже началась/закончилась — не принимаем новых игроков
            await self._send_error_and_close(
                session,
                "Game already started or finished",
            )
            return

        if session.player_id is not None:
            # Повторный JoinRequest — игнорируем
            logger.warning("Session already has player_id, ignoring JoinRequest")
            return

        if len(self.sessions_by_player) >= self.max_players:
            await self._send_error_and_close(session, "Server is full")
            return

        player_id = PlayerId(self._next_player_id)
        self._next_player_id += 1
        team_id = self._assign_team_for_new_player()

        session.player_id = player_id
        session.team_id = team_id
        session.name = msg.name

        self.sessions_by_player[player_id] = session
        self.players_team_mapping[player_id] = team_id

        logger.info(
            "Player %s joined as team %s (name=%r)",
            int(player_id),
            int(team_id),
            msg.name,
        )
        logger.debug("Total players: %d/%d", len(self.sessions_by_player), self.max_players)

        reply = JoinAccepted(player_id=player_id, team_id=team_id)
        await self._send_to_session(session, reply)

    def _assign_team_for_new_player(self) -> TeamId:
        """
        Простейший балансировщик: игроки распределяются по командам 1 и 2 примерно поровну.
        """
        count_team1 = sum(1 for t in self.players_team_mapping.values() if int(t) == 1)
        count_team2 = sum(1 for t in self.players_team_mapping.values() if int(t) == 2)
        if count_team1 <= count_team2:
            return TeamId(1)
        return TeamId(2)

    async def _send_error_and_close(self, session: ClientSession, message: str) -> None:
        """Отправить ошибку клиенту и закрыть соединение."""
        logger.warning("Sending error to client and closing: %s", message)
        try:
            await self._send_to_session(session, ErrorMessage(message=message))
        except Exception:
            pass
        try:
            session.writer.close()
            await session.writer.wait_closed()
        except Exception:
            pass

    async def _on_ready_to_start(self, session: ClientSession, msg: ReadyToStart) -> None:
        """Обработать сигнал готовности игрока."""
        if self.state != "lobby":
            # Готовность после старта игры — игнорируем
            return

        if session.player_id is None or msg.player_id != session.player_id:
            logger.warning("ReadyToStart with mismatched player_id")
            return

        self.ready_players.add(session.player_id)
        logger.info("Player %s is ready", int(session.player_id))

        await self._maybe_start_game()

    async def _maybe_start_game(self) -> None:
        """
        Проверяет, можно ли запустить игру:
        - игроков не меньше required_players;
        - все зарегистрированные игроки отправили ReadyToStart.
        """
        if self.state != "lobby":
            return

        players_count = len(self.sessions_by_player)
        if players_count < self.required_players:
            return

        # Все зарегистрированные игроки должны быть в ready_players
        all_ready = all(pid in self.ready_players for pid in self.sessions_by_player.keys())
        if not all_ready:
            return

        # Создаём GameEngine и запускаем игровой цикл
        logger.info(
            "Starting game with %d players: %s",
            players_count,
            [int(pid) for pid in self.sessions_by_player.keys()],
        )
        self.engine = GameEngine(self.config, self.players_team_mapping)
        self.state = "running"

        asyncio.create_task(self._game_loop())

    async def _on_player_command(self, session: ClientSession, msg: PlayerCommandMessage) -> None:
        """Обработать команду от игрока."""
        if self.state != "running" or self.engine is None:
            # Игра ещё не началась или уже закончилась — игнор
            return

        if session.player_id is None or msg.player_id != session.player_id:
            logger.warning("PlayerCommand with mismatched player_id")
            return

        logger.debug("Received command from P%s: %r", int(session.player_id), msg.command)
        await self._command_queue.put(msg.command)

    async def _send_to_session(self, session: ClientSession, msg: ServerToClientMessage) -> None:
        """Отправить сообщение конкретной сессии."""
        data = frame_message(msg)
        session.writer.write(data)
        await session.writer.drain()

    async def _send_to_player(self, player_id: PlayerId, msg: ServerToClientMessage) -> None:
        """Отправить сообщение конкретному игроку."""
        session = self.sessions_by_player.get(player_id)
        if session is None:
            return
        await self._send_to_session(session, msg)

    async def _broadcast(self, msg: ServerToClientMessage) -> None:
        """Разослать сообщение всем подключённым игрокам."""
        for session in list(self.sessions_by_player.values()):
            try:
                await self._send_to_session(session, msg)
            except ConnectionError:
                logger.warning("Failed to send to player %s", session.player_id)

    async def _game_loop(self) -> None:
        """Основной игровой цикл."""
        assert self.engine is not None
        logger.info("Game loop started")
        dt = 1.0 / self.tick_rate

        try:
            while self.engine.state.running:
                # 1. Достать все команды из очереди
                while True:
                    try:
                        cmd = self._command_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                    self.engine.enqueue_command(cmd)

                # 2. Обновить игровое состояние
                self.engine.tick(dt)

                # 3. Разослать снапшот
                if (
                    self.engine.state.tick % self.snapshot_interval_ticks == 0
                    and self.sessions_by_player
                ):
                    events = self.engine.consume_events()
                    snapshot = StateSnapshot(
                        tick=self.engine.state.tick,
                        state=self.engine.state,
                        events=events,
                    )
                    await self._broadcast(snapshot)

                # 4. Проверить окончание игры
                if not self.engine.state.running:
                    break

                await asyncio.sleep(dt)

            # Игра закончилась → отправить GameOver
            winner = self.engine.state.winner_team_id
            reason = "game_over"
            if winner is not None:
                reason = f"winner_team_{int(winner)}"

            game_over_msg = GameOver(
                winner_team_id=winner,
                reason=reason,
            )
            await self._broadcast(game_over_msg)
            logger.info("Game loop finished with winner_team=%s", winner)

        except asyncio.CancelledError:
            logger.info("Game loop cancelled")
        finally:
            self.state = "finished"
            # Остановим сервер целиком (для простоты)
            self._request_stop()
