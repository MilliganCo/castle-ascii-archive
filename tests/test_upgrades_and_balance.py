"""Тесты для системы апгрейдов и экономики."""

from __future__ import annotations

import pytest

from ascii_rts_castle.config import create_default_game_config
from ascii_rts_castle.server.engine import GameEngine
from ascii_rts_castle.shared.commands import BuildCommand, ResearchUpgradeCommand
from ascii_rts_castle.shared.models import LaneId, PlayerId, TeamId


def test_income_upgrade_increases_income() -> None:
    """Тест: апгрейд income_1 повышает доход игрока."""
    cfg = create_default_game_config()
    engine = GameEngine(cfg, {PlayerId(1): TeamId(1)})

    player = engine.state.players[PlayerId(1)]
    base_income = player.income_per_sec

    # Применяем апгрейд
    engine.enqueue_command(ResearchUpgradeCommand(player_id=PlayerId(1), upgrade_id="income_1"))
    engine.tick(dt=0.0)

    # Проверяем, что доход увеличился
    assert player.income_per_sec > base_income
    assert player.income_per_sec == pytest.approx(base_income + 2.0)


def test_infantry_attack_upgrade_increases_damage() -> None:
    """Тест: апгрейд infantry_attack_1 повышает урон пехоты."""
    cfg = create_default_game_config()
    engine = GameEngine(cfg, {PlayerId(1): TeamId(1)})

    lane_id = LaneId(1)
    base_infantry_damage = cfg.unit_templates["infantry"].damage

    # Применяем апгрейд ДО строительства
    engine.enqueue_command(
        ResearchUpgradeCommand(player_id=PlayerId(1), upgrade_id="infantry_attack_1")
    )
    engine.tick(dt=0.0)

    # Строим казармы
    engine.enqueue_command(
        BuildCommand(player_id=PlayerId(1), lane_id=lane_id, building_type_id="barracks")
    )
    engine.tick(dt=0.0)

    # Прокручиваем несколько тиков, чтобы заспавнился юнит
    for _ in range(20):
        engine.tick(dt=0.25)

    # Ищем заспавненного юнита
    spawned_units = [u for u in engine.state.units.values() if u.team_id == TeamId(1) and u.alive]

    if spawned_units:
        upgraded_unit = spawned_units[0]
        # Урон должен быть увеличен на 20%
        expected_damage = base_infantry_damage * 1.2
        assert upgraded_unit.damage == pytest.approx(expected_damage)


def test_gold_mine_adds_income() -> None:
    """Тест: Gold Mine добавляет доход."""
    cfg = create_default_game_config()
    engine = GameEngine(cfg, {PlayerId(1): TeamId(1)})

    player = engine.state.players[PlayerId(1)]
    lane_id = LaneId(1)

    # Строим Gold Mine
    engine.enqueue_command(
        BuildCommand(player_id=PlayerId(1), lane_id=lane_id, building_type_id="gold_mine")
    )
    engine.tick(dt=0.0)

    gold_before = player.gold
    base_income = player.income_per_sec

    # Прокручиваем 10 секунд
    for _ in range(100):
        engine.tick(dt=0.1)

    # Проверяем, что золото увеличилось больше, чем только базовый доход
    gold_after = player.gold
    expected_min_gold = gold_before + (base_income * 10.0)

    assert gold_after >= expected_min_gold
    # Должно быть больше, чем только базовый доход
    assert gold_after > expected_min_gold


def test_barracks_training_reduces_spawn_interval() -> None:
    """Тест: barracks_training_1 уменьшает spawn_interval."""
    cfg = create_default_game_config()
    engine = GameEngine(cfg, {PlayerId(1): TeamId(1)})

    # Даём игроку больше золота для двух зданий и апгрейда
    player = engine.state.players[PlayerId(1)]
    player.gold = 300.0  # 50 (barracks) + 90 (upgrade) + 50 (barracks) + запас

    lane_id = LaneId(1)
    base_spawn_interval = cfg.building_templates["barracks"].spawn_interval
    assert base_spawn_interval is not None

    # Строим первую казарму до апгрейда
    engine.enqueue_command(
        BuildCommand(player_id=PlayerId(1), lane_id=lane_id, building_type_id="barracks")
    )
    engine.tick(dt=0.0)

    buildings = list(engine.state.buildings.values())
    assert len(buildings) == 1
    first_barracks = buildings[0]
    assert first_barracks.spawn_interval == pytest.approx(base_spawn_interval)

    # Применяем апгрейд
    engine.enqueue_command(
        ResearchUpgradeCommand(player_id=PlayerId(1), upgrade_id="barracks_training_1")
    )
    engine.tick(dt=0.0)

    # Строим вторую казарму после апгрейда
    engine.enqueue_command(
        BuildCommand(player_id=PlayerId(1), lane_id=lane_id, building_type_id="barracks")
    )
    engine.tick(dt=0.0)

    buildings = list(engine.state.buildings.values())
    assert len(buildings) == 2
    second_barracks = buildings[1]

    # Spawn interval второй казармы должен быть меньше
    expected_interval = base_spawn_interval * 0.8
    assert second_barracks.spawn_interval == pytest.approx(expected_interval)
    assert second_barracks.spawn_interval < first_barracks.spawn_interval


def test_upgrade_max_level_limit() -> None:
    """Тест: апгрейд не может превысить max_level."""
    cfg = create_default_game_config()
    engine = GameEngine(cfg, {PlayerId(1): TeamId(1)})

    player = engine.state.players[PlayerId(1)]
    upgrade_template = cfg.upgrade_templates["income_1"]

    # Применяем апгрейд до max_level
    for _ in range(upgrade_template.max_level):
        engine.enqueue_command(ResearchUpgradeCommand(player_id=PlayerId(1), upgrade_id="income_1"))
        engine.tick(dt=0.0)

    # Проверяем, что уровень достиг max_level
    assert player.upgrades.get("income_1", 0) == upgrade_template.max_level

    # Пытаемся применить ещё раз
    gold_before = player.gold
    engine.enqueue_command(ResearchUpgradeCommand(player_id=PlayerId(1), upgrade_id="income_1"))
    engine.tick(dt=0.0)

    # Золото не должно быть списано, уровень не должен увеличиться
    assert player.gold == pytest.approx(gold_before)
    assert player.upgrades.get("income_1", 0) == upgrade_template.max_level
