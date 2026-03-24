"""Тесты логики сетевого клиента (без реальных сокетов)."""

from __future__ import annotations

import pytest

from ascii_rts_castle.client.network import (
    ClientGameContext,
    NetworkClient,
    process_incoming_messages,
)
from ascii_rts_castle.config import create_default_game_config
from ascii_rts_castle.server.engine import GameEngine
from ascii_rts_castle.shared.messages import ErrorMessage, GameOver, JoinAccepted, StateSnapshot
from ascii_rts_castle.shared.models import PlayerId, TeamId


@pytest.mark.asyncio
async def test_process_incoming_updates_context() -> None:
    """Тест обновления контекста при обработке входящих сообщений."""
    cfg = create_default_game_config()
    engine = GameEngine(cfg, {PlayerId(1): TeamId(1)})
    engine.tick(0.1)
    state = engine.state

    client = NetworkClient(host="localhost", port=12345)
    ctx = ClientGameContext()

    # Имитируем приход JoinAccepted и StateSnapshot
    await client.incoming.put(JoinAccepted(player_id=PlayerId(1), team_id=TeamId(2)))
    await client.incoming.put(StateSnapshot(tick=state.tick, state=state))

    await process_incoming_messages(client, ctx)

    assert ctx.player_id == PlayerId(1)
    assert ctx.team_id == TeamId(2)
    assert ctx.last_state is not None
    assert ctx.last_tick == state.tick


@pytest.mark.asyncio
async def test_process_incoming_game_over() -> None:
    """Тест обработки GameOver сообщения."""
    client = NetworkClient(host="localhost", port=12345)
    ctx = ClientGameContext()

    winner_team = TeamId(1)
    await client.incoming.put(GameOver(winner_team_id=winner_team, reason="winner_team_1"))

    await process_incoming_messages(client, ctx)

    assert ctx.game_over is True
    assert ctx.winner_team_id == winner_team
    assert ctx.game_over_reason == "winner_team_1"


@pytest.mark.asyncio
async def test_process_incoming_error_message() -> None:
    """Тест обработки ErrorMessage (разрыв соединения)."""
    client = NetworkClient(host="localhost", port=12345)
    ctx = ClientGameContext()

    error_msg = "Disconnected from server"
    await client.incoming.put(ErrorMessage(message=error_msg))

    await process_incoming_messages(client, ctx)

    assert ctx.game_over is True
    assert ctx.game_over_reason == error_msg
    assert ctx.disconnected is True


@pytest.mark.asyncio
async def test_process_incoming_multiple_messages() -> None:
    """Тест обработки нескольких сообщений подряд."""
    cfg = create_default_game_config()
    engine = GameEngine(cfg, {PlayerId(1): TeamId(1)})
    engine.tick(0.1)
    state = engine.state

    client = NetworkClient(host="localhost", port=12345)
    ctx = ClientGameContext()

    # Отправляем несколько сообщений
    await client.incoming.put(JoinAccepted(player_id=PlayerId(1), team_id=TeamId(2)))
    await client.incoming.put(StateSnapshot(tick=10, state=state))
    await client.incoming.put(StateSnapshot(tick=20, state=state))

    await process_incoming_messages(client, ctx)

    # Последнее состояние должно быть последним полученным
    assert ctx.player_id == PlayerId(1)
    assert ctx.team_id == TeamId(2)
    assert ctx.last_tick == 20
    assert ctx.last_state is not None
