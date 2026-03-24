"""
Система команд игрока (BuildCommand, UpgradeCommand, etc.).

Определяет действия, которые игрок может отправить серверу.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from .models import BuildingId, LaneId, PlayerId


@dataclass
class BuildCommand:
    player_id: PlayerId
    lane_id: LaneId
    building_type_id: str
    # На Этапе 1 можно игнорировать явную позицию и спавнить около своей базы


@dataclass
class UpgradeBuildingCommand:
    player_id: PlayerId
    building_id: BuildingId


@dataclass
class ResearchUpgradeCommand:
    player_id: PlayerId
    upgrade_id: str


@dataclass
class ActivateBaseAbilityCommand:
    """Команда активации способности базы."""
    player_id: PlayerId
    lane_id: LaneId
    ability_id: str  # "shield", "lightning", "summon", "heal"


GameCommand = Union[BuildCommand, UpgradeBuildingCommand, ResearchUpgradeCommand, ActivateBaseAbilityCommand]
