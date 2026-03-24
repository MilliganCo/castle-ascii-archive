"""Тесты логики сервера (без реальных сокетов)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ascii_rts_castle.config import create_default_game_config
from ascii_rts_castle.server.engine import GameEngine
from ascii_rts_castle.server.network import ClientSession, GameServer
from ascii_rts_castle.shared.models import PlayerId, TeamId


def test_assign_team_balances_teams() -> None:
    """Тест распределения игроков по командам."""
    cfg = create_default_game_config()
    server = GameServer(cfg)

    # имитируем уже существующих игроков
    server.players_team_mapping[PlayerId(1)] = TeamId(1)
    server.players_team_mapping[PlayerId(2)] = TeamId(2)

    t3 = server._assign_team_for_new_player()
    t4 = server._assign_team_for_new_player()

    # команды должны распределяться примерно поровну между 1 и 2
    assert int(t3) in (1, 2)
    assert int(t4) in (1, 2)


@pytest.mark.asyncio
async def test_maybe_start_game_creates_engine_when_all_ready() -> None:
    """Тест создания GameEngine при готовности всех игроков."""
    cfg = create_default_game_config()
    server = GameServer(cfg, required_players=2)

    # подготавливаем "зарегистрированных" игроков
    server.players_team_mapping[PlayerId(1)] = TeamId(1)
    server.players_team_mapping[PlayerId(2)] = TeamId(2)
    # Создаём фиктивные сессии для sessions_by_player
    # (в реальности они создаются при подключении, но для теста нам нужны только player_id)
    mock_reader = MagicMock()
    mock_writer = MagicMock()
    session1 = ClientSession(reader=mock_reader, writer=mock_writer, player_id=PlayerId(1))
    session2 = ClientSession(reader=mock_reader, writer=mock_writer, player_id=PlayerId(2))
    server.sessions_by_player[PlayerId(1)] = session1
    server.sessions_by_player[PlayerId(2)] = session2

    server.ready_players.add(PlayerId(1))
    server.ready_players.add(PlayerId(2))

    # вызываем приватно (допустимо в тестах)
    await server._maybe_start_game()

    assert server.engine is not None
    assert isinstance(server.engine, GameEngine)
    assert server.state == "running"


@pytest.mark.asyncio
async def test_maybe_start_game_does_not_start_with_insufficient_players() -> None:
    """Тест, что игра не начинается при недостаточном количестве игроков."""
    cfg = create_default_game_config()
    server = GameServer(cfg, required_players=2)

    # только один игрок
    server.players_team_mapping[PlayerId(1)] = TeamId(1)
    mock_reader = MagicMock()
    mock_writer = MagicMock()
    session1 = ClientSession(reader=mock_reader, writer=mock_writer, player_id=PlayerId(1))
    server.sessions_by_player[PlayerId(1)] = session1
    server.ready_players.add(PlayerId(1))

    await server._maybe_start_game()

    assert server.engine is None
    assert server.state == "lobby"


@pytest.mark.asyncio
async def test_maybe_start_game_does_not_start_when_not_all_ready() -> None:
    """Тест, что игра не начинается, если не все игроки готовы."""
    cfg = create_default_game_config()
    server = GameServer(cfg, required_players=2)

    server.players_team_mapping[PlayerId(1)] = TeamId(1)
    server.players_team_mapping[PlayerId(2)] = TeamId(2)
    mock_reader = MagicMock()
    mock_writer = MagicMock()
    session1 = ClientSession(reader=mock_reader, writer=mock_writer, player_id=PlayerId(1))
    session2 = ClientSession(reader=mock_reader, writer=mock_writer, player_id=PlayerId(2))
    server.sessions_by_player[PlayerId(1)] = session1
    server.sessions_by_player[PlayerId(2)] = session2

    # только один игрок готов
    server.ready_players.add(PlayerId(1))

    await server._maybe_start_game()

    assert server.engine is None
    assert server.state == "lobby"
