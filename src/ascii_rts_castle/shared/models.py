"""
Общие модели данных (Player, Unit, Building, Lane, Base, GameState).

Содержит все основные игровые сущности.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal, NewType, Optional

PlayerId = NewType("PlayerId", int)
TeamId = NewType("TeamId", int)
UnitId = NewType("UnitId", int)
BuildingId = NewType("BuildingId", int)
LaneId = NewType("LaneId", int)
NeutralObjectId = NewType("NeutralObjectId", int)

UnitState = Literal["moving", "attacking", "dead"]


@dataclass
class ActiveUpgrade:
    """Активное исследование апгрейда."""
    upgrade_id: str
    remaining_time: float
    target_level: int


@dataclass
class Player:
    id: PlayerId
    team_id: TeamId
    gold: float
    income_per_sec: float
    upgrades: Dict[str, int] = field(default_factory=dict)  # upgrade_id -> уровень
    active_upgrades: Dict[str, ActiveUpgrade] = field(default_factory=dict)  # upgrade_id -> активное исследование


@dataclass
class Lane:
    id: LaneId
    length: float
    unit_ids: List[UnitId] = field(default_factory=list)
    building_ids: List[BuildingId] = field(default_factory=list)


@dataclass
class Base:
    team_id: TeamId
    lane_id: LaneId
    position: float  # 0.0 или length
    hp: float
    max_hp: float
    alive: bool = True
    attack_range: float = 4.5
    attack_damage: float = 15.0
    attack_cooldown: float = 1.0
    attack_cooldown_remaining: float = 0.0
    # Способности базы
    shield_active: bool = False  # Активен ли щит
    shield_duration_remaining: float = 0.0  # Оставшееся время действия щита
    shield_damage_reduction: float = 0.5  # Снижение урона (50%)
    lightning_cooldown_remaining: float = 0.0  # Кулдаун обстрела молниями
    summon_cooldown_remaining: float = 0.0  # Кулдаун вызова солдат
    heal_cooldown_remaining: float = 0.0  # Кулдаун лечения


@dataclass
class Unit:
    id: UnitId
    team_id: TeamId
    lane_id: LaneId
    position: float  # 0..length
    max_hp: float
    hp: float
    damage: float
    attack_range: float
    attack_cooldown: float
    attack_cooldown_remaining: float
    speed: float
    state: UnitState = "moving"
    alive: bool = True
    template_id: str = ""  # ID шаблона юнита для определения типа
    vs_base_damage_multiplier: float = 1.0  # Множитель урона по базам


@dataclass
class Building:
    id: BuildingId
    owner_player_id: PlayerId
    team_id: TeamId
    lane_id: LaneId
    position: float
    template_id: str
    level: int
    spawn_interval: float
    spawn_timer: float  # обратный отсчёт до спавна следующего юнита


@dataclass
class NeutralObject:
    """Нейтральный объект на линии (золото, сундук, монстр)."""
    id: NeutralObjectId
    lane_id: LaneId
    position: float
    object_type: str  # "gold", "chest", "monster"
    value: float  # Количество золота или ID апгрейда для сундука
    hp: float = 100.0  # HP для монстров
    max_hp: float = 100.0
    damage: float = 10.0  # Урон для монстров
    attack_range: float = 1.5
    attack_cooldown: float = 1.0
    attack_cooldown_remaining: float = 0.0
    monster_type: str = "normal"  # "normal", "tank", "fast", "ranged" - тип монстра
    alive: bool = True


@dataclass
class VisualEffect:
    """Визуальный эффект для отображения на карте."""
    effect_type: str  # "lightning", "shield", "summon", "heal"
    lane_id: LaneId
    position: float  # Позиция на линии
    team_id: TeamId
    duration: float  # Длительность эффекта в секундах
    remaining_time: float  # Оставшееся время


@dataclass
class GameState:
    tick: int = 0
    time: float = 0.0
    players: Dict[PlayerId, Player] = field(default_factory=dict)
    lanes: Dict[LaneId, Lane] = field(default_factory=dict)
    units: Dict[UnitId, Unit] = field(default_factory=dict)
    buildings: Dict[BuildingId, Building] = field(default_factory=dict)
    bases: Dict[TeamId, Base] = field(default_factory=dict)  # Для обратной совместимости
    bases_list: List[Base] = field(default_factory=list)  # Список всех баз (для многолинейной карты)
    neutral_objects: Dict[NeutralObjectId, NeutralObject] = field(default_factory=dict)  # Нейтральные объекты
    visual_effects: List[VisualEffect] = field(default_factory=list)  # Визуальные эффекты способностей
    next_unit_id: int = 1
    next_building_id: int = 1
    next_neutral_object_id: int = 1
    running: bool = True
    winner_team_id: Optional[TeamId] = None
