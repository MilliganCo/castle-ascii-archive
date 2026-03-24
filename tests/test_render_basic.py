"""Базовые тесты для ASCII-рендера."""

from __future__ import annotations

from ascii_rts_castle.client.ui_ascii import RenderConfig, ScreenBuffer, render_game_state
from ascii_rts_castle.config import create_default_game_config
from ascii_rts_castle.server.engine import GameEngine
from ascii_rts_castle.shared.models import PlayerId, TeamId


def test_screen_buffer_basic() -> None:
    buffer = ScreenBuffer(width=10, height=3)
    buffer.clear(".")
    buffer.put(1, 1, "X")
    lines = buffer.as_lines()

    assert len(lines) == 3
    assert len(lines[0]) == 10
    assert lines[1][1] == "X"


def test_render_basic_does_not_crash() -> None:
    cfg = create_default_game_config()
    engine = GameEngine(cfg, {PlayerId(1): TeamId(1)})

    # Один тик, чтобы состояние не было совсем пустым
    engine.tick(0.1)

    render_cfg = RenderConfig(width=40, hud_height=3, lane_height=1)
    buffer = render_game_state(engine.state, render_cfg, view_player_id=PlayerId(1))

    assert buffer.width == 40
    assert buffer.height >= 3
    lines = buffer.as_lines()
    assert len(lines) == buffer.height
