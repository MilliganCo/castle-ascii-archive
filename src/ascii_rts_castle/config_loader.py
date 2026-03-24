"""
Загрузка конфигураций игры из JSON-файлов.

Позволяет создавать кастомные карты и режимы игры через внешние конфиги.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from ascii_rts_castle.config import (
    BuildingTemplate,
    GameConfig,
    LaneConfig,
    UnitTemplate,
    UpgradeEffect,
    UpgradeTemplate,
)


def game_config_from_dict(data: Dict[str, Any]) -> GameConfig:
    """Создать GameConfig из словаря (распарсенного JSON)."""
    lanes = [
        LaneConfig(
            id=int(lane_data["id"]),
            length=float(lane_data["length"]),
        )
        for lane_data in data["lanes"]
    ]

    unit_templates = {
        ut_id: UnitTemplate(
            id=ut_data["id"],
            name=ut_data["name"],
            max_hp=float(ut_data["max_hp"]),
            damage=float(ut_data["damage"]),
            attack_range=float(ut_data["attack_range"]),
            attack_cooldown=float(ut_data["attack_cooldown"]),
            speed=float(ut_data["speed"]),
            gold_cost=int(ut_data["gold_cost"]),
            role=str(ut_data["role"]),
            vs_base_damage_multiplier=float(ut_data.get("vs_base_damage_multiplier", 1.0)),
        )
        for ut_id, ut_data in data["unit_templates"].items()
    }

    building_templates = {
        bt_id: BuildingTemplate(
            id=bt_data["id"],
            name=bt_data["name"],
            unit_template_id=bt_data.get("unit_template_id"),
            spawn_interval=bt_data.get("spawn_interval"),
            cost=int(bt_data["cost"]),
            income_bonus_per_sec=float(bt_data.get("income_bonus_per_sec", 0.0)),
        )
        for bt_id, bt_data in data["building_templates"].items()
    }

    upgrade_templates = {
        up_id: UpgradeTemplate(
            id=up_data["id"],
            name=up_data["name"],
            description=up_data["description"],
            cost=int(up_data["cost"]),
            max_level=int(up_data["max_level"]),
            target_type=up_data["target_type"],
            target_id=up_data.get("target_id"),
            effects=[
                UpgradeEffect(
                    stat=e["stat"],
                    op=e["op"],
                    value=float(e["value"]),
                )
                for e in up_data["effects"]
            ],
            research_time_base=float(up_data.get("research_time_base", 0.0)),
            research_time_per_level=float(up_data.get("research_time_per_level", 0.0)),
        )
        for up_id, up_data in data["upgrade_templates"].items()
    }

    return GameConfig(
        lanes=lanes,
        base_hp=float(data["base_hp"]),
        base_attack_range=float(data.get("base_attack_range", 4.5)),
        base_attack_damage=float(data.get("base_attack_damage", 15.0)),
        base_attack_cooldown=float(data.get("base_attack_cooldown", 1.0)),
        starting_gold=int(data["starting_gold"]),
        starting_income_per_sec=float(data["starting_income_per_sec"]),
        unit_templates=unit_templates,
        building_templates=building_templates,
        upgrade_templates=upgrade_templates,
        center_start_ratio=float(data.get("center_start_ratio", 0.4)),
        center_end_ratio=float(data.get("center_end_ratio", 0.6)),
    )


def load_game_config_from_file(path: str | Path) -> GameConfig:
    """Загрузить GameConfig из JSON-файла."""
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return game_config_from_dict(data)
