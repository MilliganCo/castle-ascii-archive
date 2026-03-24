"""Тесты для базовой логики GameEngine."""

import pytest

from ascii_rts_castle.config import (
    BuildingTemplate,
    GameConfig,
    LaneConfig,
    UnitTemplate,
)
from ascii_rts_castle.server.engine import GameEngine
from ascii_rts_castle.shared.commands import BuildCommand
from ascii_rts_castle.shared.models import LaneId, PlayerId, TeamId


def create_test_config() -> GameConfig:
    """Создать тестовую конфигурацию игры."""
    unit_template = UnitTemplate(
        id="infantry",
        name="Infantry",
        max_hp=100.0,
        damage=10.0,
        attack_range=1.5,
        attack_cooldown=1.0,
        speed=2.0,
        gold_cost=10,
        role="melee",
    )

    building_template = BuildingTemplate(
        id="barracks",
        name="Barracks",
        unit_template_id="infantry",
        spawn_interval=2.0,
        cost=100,
    )

    lane_config = LaneConfig(id=1, length=10.0)

    return GameConfig(
        lanes=[lane_config],
        base_hp=1000.0,
        starting_gold=200,
        starting_income_per_sec=10.0,
        unit_templates={"infantry": unit_template},
        building_templates={"barracks": building_template},
        upgrade_templates={},
    )


def test_unit_movement() -> None:
    """Тест движения юнита."""
    config = create_test_config()
    player_id = PlayerId(1)
    team_id = TeamId(1)

    engine = GameEngine(config, {player_id: team_id})

    # Добавляем юнита вручную
    lane_id = LaneId(1)
    unit_id = engine.state.next_unit_id
    engine.state.next_unit_id += 1

    from ascii_rts_castle.shared.models import Unit, UnitId

    unit = Unit(
        id=UnitId(unit_id),
        team_id=team_id,
        lane_id=lane_id,
        position=1.0,
        max_hp=100.0,
        hp=100.0,
        damage=10.0,
        attack_range=1.5,
        attack_cooldown=1.0,
        attack_cooldown_remaining=0.0,
        speed=1.0,
        state="moving",
        alive=True,
    )

    engine.state.units[unit.id] = unit
    engine.state.lanes[lane_id].unit_ids.append(unit.id)

    initial_position = unit.position

    # Вызываем tick
    engine.tick(1.0)

    # Проверяем, что позиция увеличилась
    assert unit.position > initial_position
    assert unit.position == pytest.approx(2.0, abs=0.1)


def test_unit_combat() -> None:
    """Тест боя между юнитами."""
    config = create_test_config()
    player1_id = PlayerId(1)
    player2_id = PlayerId(2)
    team1_id = TeamId(1)
    team2_id = TeamId(2)

    engine = GameEngine(config, {player1_id: team1_id, player2_id: team2_id})

    lane_id = LaneId(1)

    from ascii_rts_castle.shared.models import Unit, UnitId

    # Создаём юнита команды 1
    unit1_id = engine.state.next_unit_id
    engine.state.next_unit_id += 1
    unit1 = Unit(
        id=UnitId(unit1_id),
        team_id=team1_id,
        lane_id=lane_id,
        position=4.0,
        max_hp=100.0,
        hp=100.0,
        damage=10.0,
        attack_range=1.5,
        attack_cooldown=1.0,
        attack_cooldown_remaining=0.0,
        speed=0.0,  # Не двигаемся, только атакуем
        state="moving",
        alive=True,
    )

    # Создаём юнита команды 2
    unit2_id = engine.state.next_unit_id
    engine.state.next_unit_id += 1
    unit2 = Unit(
        id=UnitId(unit2_id),
        team_id=team2_id,
        lane_id=lane_id,
        position=5.0,
        max_hp=100.0,
        hp=100.0,
        damage=10.0,
        attack_range=1.5,
        attack_cooldown=1.0,
        attack_cooldown_remaining=0.0,
        speed=0.0,  # Не двигаемся, только атакуем
        state="moving",
        alive=True,
    )

    engine.state.units[unit1.id] = unit1
    engine.state.units[unit2.id] = unit2
    engine.state.lanes[lane_id].unit_ids.append(unit1.id)
    engine.state.lanes[lane_id].unit_ids.append(unit2.id)

    initial_hp1 = unit1.hp
    initial_hp2 = unit2.hp

    # Вызываем несколько тиков
    for _ in range(10):
        engine.tick(1.0)
        if not unit1.alive or not unit2.alive:
            break

    # Проверяем, что хотя бы один юнит получил урон или умер
    assert unit1.hp < initial_hp1 or unit2.hp < initial_hp2 or not unit1.alive or not unit2.alive


def test_unit_spawning() -> None:
    """Тест спавна юнитов из зданий."""
    config = create_test_config()
    player_id = PlayerId(1)
    team_id = TeamId(1)

    engine = GameEngine(config, {player_id: team_id})

    lane_id = LaneId(1)

    # Строим здание через команду
    build_cmd = BuildCommand(
        player_id=player_id,
        lane_id=lane_id,
        building_type_id="barracks",
    )

    engine.enqueue_command(build_cmd)
    engine.tick(0.0)  # Применяем команду без изменения ресурсов/таймеров

    # Проверяем, что здание создано
    assert len(engine.state.buildings) == 1
    building = list(engine.state.buildings.values())[0]
    # Здание должно иметь правильный шаблон здания
    assert building.template_id == "barracks"
    # Проверяем, что здание спавнит правильный тип юнита
    assert config.building_templates[building.template_id].unit_template_id == "infantry"

    initial_unit_count = len(engine.state.units)

    # Вызываем tick два раза по 1.0 секунде (в сумме 2.0, что равно spawn_interval)
    engine.tick(1.0)
    engine.tick(1.0)

    # Проверяем, что появился новый юнит
    assert len(engine.state.units) == initial_unit_count + 1


def test_build_command_and_gold() -> None:
    """Тест применения BuildCommand и расхода золота."""
    config = create_test_config()
    player_id = PlayerId(1)
    team_id = TeamId(1)

    engine = GameEngine(config, {player_id: team_id})

    player = engine.state.players[player_id]

    # Устанавливаем золото равное стоимости здания
    building_cost = config.building_templates["barracks"].cost
    player.gold = building_cost

    lane_id = LaneId(1)

    # Отправляем команду строительства
    build_cmd = BuildCommand(
        player_id=player_id,
        lane_id=lane_id,
        building_type_id="barracks",
    )

    engine.enqueue_command(build_cmd)
    engine.tick(0.0)  # Применяем команду без изменения ресурсов/таймеров

    # Проверяем, что золото потрачено
    assert player.gold == 0

    # Проверяем, что здание создано
    assert len(engine.state.buildings) == 1
    building = list(engine.state.buildings.values())[0]
    assert building.owner_player_id == player_id
    assert building.lane_id == lane_id


def test_build_command_insufficient_gold() -> None:
    """Тест, что строительство не происходит при недостатке золота."""
    config = create_test_config()
    player_id = PlayerId(1)
    team_id = TeamId(1)

    engine = GameEngine(config, {player_id: team_id})

    player = engine.state.players[player_id]

    # Устанавливаем недостаточно золота
    player.gold = 50  # Меньше стоимости здания (100)
    initial_gold = player.gold

    lane_id = LaneId(1)

    build_cmd = BuildCommand(
        player_id=player_id,
        lane_id=lane_id,
        building_type_id="barracks",
    )

    engine.enqueue_command(build_cmd)
    engine.tick(0.0)  # Применяем команду без изменения ресурсов/таймеров

    # Проверяем, что золото не изменилось и здание не создано
    assert player.gold == initial_gold
    assert len(engine.state.buildings) == 0


def test_resource_update() -> None:
    """Тест обновления ресурсов."""
    config = create_test_config()
    player_id = PlayerId(1)
    team_id = TeamId(1)

    engine = GameEngine(config, {player_id: team_id})

    player = engine.state.players[player_id]
    initial_gold = player.gold

    # Вызываем tick на 1 секунду
    engine.tick(1.0)

    # Проверяем, что золото увеличилось
    assert player.gold > initial_gold
    assert player.gold == pytest.approx(
        initial_gold + config.starting_income_per_sec * 1.0, abs=1.0
    )
