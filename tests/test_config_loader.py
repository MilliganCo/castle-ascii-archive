"""Тесты для загрузки конфигураций из JSON-файлов."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from ascii_rts_castle.config import create_default_game_config
from ascii_rts_castle.config_loader import game_config_from_dict, load_game_config_from_file


def test_game_config_from_dict_roundtrip_with_default() -> None:
    """Тест: загрузка конфига из dict соответствует дефолтному конфигу."""
    default_cfg = create_default_game_config()

    # Создаём dict вручную из дефолтного конфига для теста
    data = {
        "lanes": [{"id": lane.id, "length": lane.length} for lane in default_cfg.lanes],
        "base_hp": default_cfg.base_hp,
        "starting_gold": default_cfg.starting_gold,
        "starting_income_per_sec": default_cfg.starting_income_per_sec,
        "unit_templates": {
            ut_id: {
                "id": ut.id,
                "name": ut.name,
                "max_hp": ut.max_hp,
                "damage": ut.damage,
                "attack_range": ut.attack_range,
                "attack_cooldown": ut.attack_cooldown,
                "speed": ut.speed,
                "gold_cost": ut.gold_cost,
                "role": ut.role,
            }
            for ut_id, ut in default_cfg.unit_templates.items()
        },
        "building_templates": {
            bt_id: {
                "id": bt.id,
                "name": bt.name,
                "unit_template_id": bt.unit_template_id,
                "spawn_interval": bt.spawn_interval,
                "cost": bt.cost,
                "income_bonus_per_sec": bt.income_bonus_per_sec,
            }
            for bt_id, bt in default_cfg.building_templates.items()
        },
        "upgrade_templates": {
            up_id: {
                "id": up.id,
                "name": up.name,
                "description": up.description,
                "cost": up.cost,
                "max_level": up.max_level,
                "target_type": up.target_type,
                "target_id": up.target_id,
                "effects": [{"stat": e.stat, "op": e.op, "value": e.value} for e in up.effects],
            }
            for up_id, up in default_cfg.upgrade_templates.items()
        },
    }

    loaded_cfg = game_config_from_dict(data)

    # Проверяем ключевые поля
    assert len(loaded_cfg.lanes) == len(default_cfg.lanes)
    assert loaded_cfg.base_hp == default_cfg.base_hp
    assert loaded_cfg.starting_gold == default_cfg.starting_gold
    assert loaded_cfg.starting_income_per_sec == default_cfg.starting_income_per_sec
    assert len(loaded_cfg.unit_templates) == len(default_cfg.unit_templates)
    assert len(loaded_cfg.building_templates) == len(default_cfg.building_templates)
    assert len(loaded_cfg.upgrade_templates) == len(default_cfg.upgrade_templates)

    # Проверяем конкретные значения
    assert "infantry" in loaded_cfg.unit_templates
    assert loaded_cfg.unit_templates["infantry"].max_hp == 100.0
    assert "barracks" in loaded_cfg.building_templates
    assert loaded_cfg.building_templates["barracks"].cost == 50


def test_load_game_config_from_file() -> None:
    """Тест: загрузка конфига из временного JSON-файла."""
    # Создаём минимальный корректный конфиг
    minimal_config = {
        "lanes": [{"id": 1, "length": 30.0}],
        "base_hp": 500.0,
        "starting_gold": 50,
        "starting_income_per_sec": 2.0,
        "unit_templates": {
            "test_unit": {
                "id": "test_unit",
                "name": "Test Unit",
                "max_hp": 50.0,
                "damage": 5.0,
                "attack_range": 1.5,
                "attack_cooldown": 1.0,
                "speed": 1.5,
                "gold_cost": 5,
                "role": "melee",
            }
        },
        "building_templates": {
            "test_building": {
                "id": "test_building",
                "name": "Test Building",
                "unit_template_id": "test_unit",
                "spawn_interval": 3.0,
                "cost": 30,
                "income_bonus_per_sec": 0.0,
            }
        },
        "upgrade_templates": {},
    }

    # Создаём временный файл
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(minimal_config, f, indent=2)
        temp_path = f.name

    try:
        # Загружаем конфиг
        loaded_cfg = load_game_config_from_file(temp_path)

        # Проверяем, что поля загружены корректно
        assert len(loaded_cfg.lanes) == 1
        assert loaded_cfg.lanes[0].id == 1
        assert loaded_cfg.lanes[0].length == 30.0
        assert loaded_cfg.base_hp == 500.0
        assert loaded_cfg.starting_gold == 50
        assert loaded_cfg.starting_income_per_sec == 2.0
        assert len(loaded_cfg.unit_templates) == 1
        assert "test_unit" in loaded_cfg.unit_templates
        assert loaded_cfg.unit_templates["test_unit"].max_hp == 50.0
        assert len(loaded_cfg.building_templates) == 1
        assert "test_building" in loaded_cfg.building_templates
        assert loaded_cfg.building_templates["test_building"].cost == 30
        assert len(loaded_cfg.upgrade_templates) == 0
    finally:
        # Удаляем временный файл
        Path(temp_path).unlink()
