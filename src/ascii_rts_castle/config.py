"""
Глобальные конфигурации проекта.

Содержит конфигурационные структуры для баланса игры.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

GAME_NAME: str = "ascii-rts-castle"

VERSION: str = "0.1.0"


@dataclass(frozen=True)
class UnitTemplate:
    id: str
    name: str
    max_hp: float
    damage: float
    attack_range: float
    attack_cooldown: float
    speed: float
    gold_cost: int  # стоимость "виртуального" юнита (для баланса/апгрейдов)
    role: str  # "melee", "ranged", "mage", "siege"
    vs_base_damage_multiplier: float = 1.0  # множитель урона по базам


@dataclass(frozen=True)
class BuildingTemplate:
    id: str
    name: str
    unit_template_id: Optional[str]  # None для зданий без спавна юнитов
    spawn_interval: Optional[float]  # None для зданий без спавна юнитов
    cost: int
    income_bonus_per_sec: float = 0.0  # дополнительный доход игроку


@dataclass(frozen=True)
class LaneConfig:
    id: int
    length: float


@dataclass(frozen=True)
class UpgradeEffect:
    stat: str  # "max_hp", "damage", "attack_range", "speed", "income_per_sec", "spawn_interval"
    op: str  # "add" или "mul"
    value: float


@dataclass(frozen=True)
class UpgradeTemplate:
    id: str
    name: str
    description: str
    cost: int
    max_level: int
    target_type: str  # "unit", "building", "player"
    target_id: Optional[str]  # например, "infantry", "barracks", None для player-wide
    effects: List[UpgradeEffect]
    research_time_base: float = 0.0  # базовое время исследования в секундах
    research_time_per_level: float = 0.0  # добавка к времени за каждый уже изученный уровень


@dataclass(frozen=True)
class BaseAbilityEffect:
    """Эффект способности базы."""
    stat: str  # "shield_duration", "shield_damage_reduction", "lightning_damage", "lightning_range", "summon_count", "heal_amount"
    op: str  # "add" или "mul"
    value: float


@dataclass(frozen=True)
class BaseAbilityTemplate:
    """Шаблон способности базы."""
    id: str
    name: str
    description: str
    cost: float
    cooldown: float
    max_level: int
    effects: List[BaseAbilityEffect] = field(default_factory=list)
    # Specific ability parameters (optional)
    shield_duration: float = 0.0
    shield_damage_reduction: float = 0.0
    lightning_damage: float = 0.0
    lightning_range: float = 0.0
    summon_count: int = 0
    summon_unit_type: Optional[str] = None
    heal_amount: float = 0.0
    heal_range: float = 0.0


@dataclass(frozen=True)
class GameConfig:
    lanes: List[LaneConfig]
    base_hp: float
    base_attack_range: float
    base_attack_damage: float
    base_attack_cooldown: float
    starting_gold: int
    starting_income_per_sec: float
    unit_templates: Dict[str, UnitTemplate]
    building_templates: Dict[str, BuildingTemplate]
    upgrade_templates: Dict[str, UpgradeTemplate]
    base_ability_templates: Dict[str, BaseAbilityTemplate] = field(default_factory=dict)
    center_start_ratio: float = 0.4  # Начало центральной боевой зоны (относительно длины линии)
    center_end_ratio: float = 0.6  # Конец центральной боевой зоны


def create_default_game_config() -> GameConfig:
    """Создать конфигурацию игры по умолчанию с несколькими типами юнитов, зданий и апгрейдов."""

    unit_templates = {
        "infantry": UnitTemplate(
            id="infantry",
            name="Infantry",
            max_hp=160.0,
            damage=12.0,
            attack_range=1.0,
            attack_cooldown=0.8,
            speed=1.0,
            gold_cost=10,
            role="melee",
            vs_base_damage_multiplier=1.0,
        ),
        "archer": UnitTemplate(
            id="archer",
            name="Archer",
            max_hp=80.0,
            damage=10.0,
            attack_range=3.5,
            attack_cooldown=1.2,
            speed=1.0,
            gold_cost=12,
            role="ranged",
            vs_base_damage_multiplier=1.0,
        ),
        "mage": UnitTemplate(
            id="mage",
            name="Mage",
            max_hp=70.0,
            damage=18.0,
            attack_range=5.5,
            attack_cooldown=1.6,
            speed=0.9,
            gold_cost=18,
            role="mage",
            vs_base_damage_multiplier=1.0,
        ),
        "siege": UnitTemplate(
            id="siege",
            name="Siege Engine",
            max_hp=240.0,
            damage=20.0,
            attack_range=2.5,
            attack_cooldown=2.0,
            speed=0.7,
            gold_cost=35,
            role="siege",
            vs_base_damage_multiplier=2.0,  # По базам бьёт в 2 раза сильнее
        ),
    }

    building_templates = {
        "barracks": BuildingTemplate(
            id="barracks",
            name="Barracks",
            unit_template_id="infantry",
            spawn_interval=4.0,
            cost=50,
        ),
        "archery_range": BuildingTemplate(
            id="archery_range",
            name="Archery Range",
            unit_template_id="archer",
            spawn_interval=5.0,
            cost=70,
        ),
        "mage_tower": BuildingTemplate(
            id="mage_tower",
            name="Mage Tower",
            unit_template_id="mage",
            spawn_interval=6.0,
            cost=90,
        ),
        "siege_workshop": BuildingTemplate(
            id="siege_workshop",
            name="Siege Workshop",
            unit_template_id="siege",
            spawn_interval=8.0,
            cost=120,
        ),
        "gold_mine": BuildingTemplate(
            id="gold_mine",
            name="Gold Mine",
            unit_template_id=None,
            spawn_interval=None,
            cost=80,
            income_bonus_per_sec=3.0,
        ),
    }

    upgrade_templates = {
        "income_1": UpgradeTemplate(
            id="income_1",
            name="Improved Mining I",
            description="+2 gold/sec",
            cost=100,
            max_level=3,
            target_type="player",
            target_id=None,
            effects=[
                UpgradeEffect(stat="income_per_sec", op="add", value=2.0),
            ],
            research_time_base=5.0,
            research_time_per_level=2.0,
        ),
        "income_2": UpgradeTemplate(
            id="income_2",
            name="Improved Mining II",
            description="+3 gold/sec",
            cost=150,
            max_level=3,
            target_type="player",
            target_id=None,
            effects=[
                UpgradeEffect(stat="income_per_sec", op="add", value=3.0),
            ],
            research_time_base=7.0,
            research_time_per_level=3.0,
        ),
        "infantry_attack_1": UpgradeTemplate(
            id="infantry_attack_1",
            name="Infantry Weapons I",
            description="+20% infantry damage",
            cost=80,
            max_level=3,
            target_type="unit",
            target_id="infantry",
            effects=[
                UpgradeEffect(stat="damage", op="mul", value=1.2),
            ],
            research_time_base=8.0,
            research_time_per_level=3.0,
        ),
        "infantry_attack_2": UpgradeTemplate(
            id="infantry_attack_2",
            name="Infantry Weapons II",
            description="+30% infantry damage",
            cost=120,
            max_level=3,
            target_type="unit",
            target_id="infantry",
            effects=[
                UpgradeEffect(stat="damage", op="mul", value=1.3),
            ],
            research_time_base=10.0,
            research_time_per_level=4.0,
        ),
        "infantry_hp_1": UpgradeTemplate(
            id="infantry_hp_1",
            name="Infantry Armor I",
            description="+20% infantry HP",
            cost=80,
            max_level=3,
            target_type="unit",
            target_id="infantry",
            effects=[
                UpgradeEffect(stat="max_hp", op="mul", value=1.2),
            ],
            research_time_base=8.0,
            research_time_per_level=3.0,
        ),
        "infantry_hp_2": UpgradeTemplate(
            id="infantry_hp_2",
            name="Infantry Armor II",
            description="+30% infantry HP",
            cost=120,
            max_level=3,
            target_type="unit",
            target_id="infantry",
            effects=[
                UpgradeEffect(stat="max_hp", op="mul", value=1.3),
            ],
            research_time_base=10.0,
            research_time_per_level=4.0,
        ),
        "archer_attack_1": UpgradeTemplate(
            id="archer_attack_1",
            name="Archer Weapons I",
            description="+25% archer damage",
            cost=90,
            max_level=3,
            target_type="unit",
            target_id="archer",
            effects=[
                UpgradeEffect(stat="damage", op="mul", value=1.25),
            ],
            research_time_base=8.0,
            research_time_per_level=3.0,
        ),
        "archer_range_1": UpgradeTemplate(
            id="archer_range_1",
            name="Archer Range I",
            description="+15% archer range",
            cost=100,
            max_level=2,
            target_type="unit",
            target_id="archer",
            effects=[
                UpgradeEffect(stat="attack_range", op="mul", value=1.15),
            ],
            research_time_base=9.0,
            research_time_per_level=3.5,
        ),
        "mage_power_1": UpgradeTemplate(
            id="mage_power_1",
            name="Mage Power I",
            description="+30% mage damage",
            cost=110,
            max_level=2,
            target_type="unit",
            target_id="mage",
            effects=[
                UpgradeEffect(stat="damage", op="mul", value=1.3),
            ],
            research_time_base=10.0,
            research_time_per_level=4.0,
        ),
        "barracks_training_1": UpgradeTemplate(
            id="barracks_training_1",
            name="Barracks Training I",
            description="-20% infantry spawn interval",
            cost=90,
            max_level=2,
            target_type="building",
            target_id="barracks",
            effects=[
                UpgradeEffect(stat="spawn_interval", op="mul", value=0.8),
            ],
            research_time_base=7.0,
            research_time_per_level=2.5,
        ),
        "barracks_training_2": UpgradeTemplate(
            id="barracks_training_2",
            name="Barracks Training II",
            description="-30% infantry spawn interval",
            cost=130,
            max_level=2,
            target_type="building",
            target_id="barracks",
            effects=[
                UpgradeEffect(stat="spawn_interval", op="mul", value=0.7),
            ],
            research_time_base=9.0,
            research_time_per_level=3.0,
        ),
        "unit_speed_1": UpgradeTemplate(
            id="unit_speed_1",
            name="Swift Movement I",
            description="+15% all units speed",
            cost=120,
            max_level=2,
            target_type="unit",
            target_id=None,  # Все юниты
            effects=[
                UpgradeEffect(stat="speed", op="mul", value=1.15),
            ],
            research_time_base=10.0,
            research_time_per_level=4.0,
        ),
    }

    # Три линии для многолинейной карты (увеличена длина)
    lanes = [
        LaneConfig(id=1, length=90.0),
        LaneConfig(id=2, length=90.0),
        LaneConfig(id=3, length=90.0),
    ]

    # Способности базы
    base_ability_templates = {
        "shield": BaseAbilityTemplate(
            id="shield",
            name="Shield",
            description="Защита базы от урона на 10 секунд",
            cost=50.0,
            cooldown=30.0,
            max_level=3,
            shield_duration=10.0,
            shield_damage_reduction=0.5,  # 50% снижение урона
        ),
        "lightning": BaseAbilityTemplate(
            id="lightning",
            name="Lightning Strike",
            description="Молнии наносят урон вражеским юнитам",
            cost=60.0,
            cooldown=25.0,
            max_level=3,
            lightning_damage=50.0,
            lightning_range=8.0,
        ),
        "summon": BaseAbilityTemplate(
            id="summon",
            name="Summon Soldiers",
            description="Вызывает 3 пехотинцев у базы",
            cost=70.0,
            cooldown=40.0,
            max_level=2,
            summon_count=3,
            summon_unit_type="infantry",
        ),
        "heal": BaseAbilityTemplate(
            id="heal",
            name="Heal Base",
            description="Восстанавливает 200 HP базы",
            cost=40.0,
            cooldown=20.0,
            max_level=3,
            heal_amount=200.0,
            heal_range=0.0,  # Только база
        ),
    }

    return GameConfig(
        lanes=lanes,
        base_hp=1000.0,
        base_attack_range=6.0,  # Дальность базы должна превышать дальность любого юнита (макс. 5.5 у магов)
        base_attack_damage=15.0,
        base_attack_cooldown=1.0,
        starting_gold=80,
        starting_income_per_sec=4.0,  # Увеличен стартовый доход
        unit_templates=unit_templates,
        building_templates=building_templates,
        upgrade_templates=upgrade_templates,
        base_ability_templates=base_ability_templates,
        center_start_ratio=0.4,
        center_end_ratio=0.6,
    )
