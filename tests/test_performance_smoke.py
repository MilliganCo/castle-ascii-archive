"""Дымовой тест производительности для проверки стабильности при большой нагрузке."""

from __future__ import annotations

import time

from ascii_rts_castle.config import create_default_game_config
from ascii_rts_castle.server.engine import GameEngine
from ascii_rts_castle.shared.commands import BuildCommand
from ascii_rts_castle.shared.models import PlayerId, TeamId


def test_smoke_performance_large_battle() -> None:
    """Дымовой тест: симуляция большого сражения без падений."""
    cfg = create_default_game_config()
    engine = GameEngine(
        cfg,
        {
            PlayerId(1): TeamId(1),
            PlayerId(2): TeamId(2),
        },
    )

    # Сымитировать много зданий, чтобы было много юнитов
    from ascii_rts_castle.shared.models import LaneId

    lane_ids = list(engine.state.lanes.keys())
    if not lane_ids:
        return
    lane_id = LaneId(int(lane_ids[0]))

    # Строим несколько зданий для каждой команды
    for _ in range(3):
        engine.enqueue_command(
            BuildCommand(player_id=PlayerId(1), lane_id=lane_id, building_type_id="barracks")
        )
        engine.enqueue_command(
            BuildCommand(player_id=PlayerId(2), lane_id=lane_id, building_type_id="barracks")
        )

    # Применяем команды
    engine.tick(0.0)

    # Прогнать, например, 200 тиков (~10 секунд при dt=0.05)
    dt = 0.05
    ticks = 200
    start = time.perf_counter()
    for _ in range(ticks):
        engine.tick(dt)
    elapsed = time.perf_counter() - start

    # Проверка "не упали и не дико тормозим":
    assert elapsed < 5.0  # чисто ориентировочное значение
    # Проверяем, что игра не упала
    assert engine.state is not None
    # Проверяем, что есть юниты или здания
    assert len(engine.state.units) > 0 or len(engine.state.buildings) > 0
