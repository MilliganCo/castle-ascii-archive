"""
Сетевые сообщения для клиент-серверного взаимодействия.

Этап 4: описание типов сообщений, сериализация в JSON и length-prefixed фрейминг.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ascii_rts_castle.shared.commands import (
    BuildCommand,
    GameCommand,
    ResearchUpgradeCommand,
    UpgradeBuildingCommand,
)
from ascii_rts_castle.shared.models import (
    Base,
    Building,
    BuildingId,
    GameState,
    Lane,
    LaneId,
    Player,
    PlayerId,
    TeamId,
    Unit,
    UnitId,
)

MESSAGE_TYPE_JOIN_REQUEST = "join_request"
MESSAGE_TYPE_JOIN_ACCEPTED = "join_accepted"
MESSAGE_TYPE_PLAYER_COMMAND = "player_command"
MESSAGE_TYPE_READY_TO_START = "ready_to_start"
MESSAGE_TYPE_STATE_SNAPSHOT = "state_snapshot"
MESSAGE_TYPE_GAME_OVER = "game_over"
MESSAGE_TYPE_ERROR = "error"


# === Типы сообщений ===


@dataclass
class JoinRequest:
    name: str


@dataclass
class ReadyToStart:
    player_id: PlayerId


@dataclass
class PlayerCommandMessage:
    player_id: PlayerId
    command: GameCommand


@dataclass
class JoinAccepted:
    player_id: PlayerId
    team_id: TeamId


@dataclass
class StateSnapshot:
    tick: int
    state: GameState
    events: list[str] | None = None


@dataclass
class GameOver:
    winner_team_id: Optional[TeamId]
    reason: str


@dataclass
class ErrorMessage:
    message: str


ClientToServerMessage = Union[JoinRequest, ReadyToStart, PlayerCommandMessage]
ServerToClientMessage = Union[JoinAccepted, StateSnapshot, GameOver, ErrorMessage]
AnyMessage = Union[ClientToServerMessage, ServerToClientMessage]


# === Сериализация GameCommand ===


def command_to_wire_dict(cmd: GameCommand) -> Dict[str, Any]:
    """Преобразовать GameCommand во внешний словарь (JSON-friendly)."""
    if isinstance(cmd, BuildCommand):
        return {
            "type": "build",
            "player_id": int(cmd.player_id),
            "lane_id": int(cmd.lane_id),
            "building_type_id": cmd.building_type_id,
        }
    if isinstance(cmd, UpgradeBuildingCommand):
        return {
            "type": "upgrade",
            "player_id": int(cmd.player_id),
            "building_id": int(cmd.building_id),
        }
    if isinstance(cmd, ResearchUpgradeCommand):
        return {
            "type": "research_upgrade",
            "player_id": int(cmd.player_id),
            "upgrade_id": cmd.upgrade_id,
        }
    raise ValueError(f"Unsupported GameCommand type: {type(cmd)!r}")


def command_from_wire_dict(data: Dict[str, Any]) -> GameCommand:
    """Восстановить GameCommand из словаря."""
    cmd_type = data.get("type")
    if cmd_type == "build":
        return BuildCommand(
            player_id=PlayerId(int(data["player_id"])),
            lane_id=LaneId(int(data["lane_id"])),
            building_type_id=str(data["building_type_id"]),
        )
    if cmd_type == "upgrade":
        return UpgradeBuildingCommand(
            player_id=PlayerId(int(data["player_id"])),
            building_id=BuildingId(int(data["building_id"])),
        )
    if cmd_type == "research_upgrade":
        return ResearchUpgradeCommand(
            player_id=PlayerId(int(data["player_id"])),
            upgrade_id=str(data["upgrade_id"]),
        )
    raise ValueError(f"Unknown command type: {cmd_type!r}")


# === Сериализация GameState ===


def game_state_to_wire_dict(state: GameState) -> Dict[str, Any]:
    """Преобразовать GameState во внешний словарь для JSON."""
    return {
        "tick": state.tick,
        "time": state.time,
        "running": state.running,
        "winner_team_id": int(state.winner_team_id) if state.winner_team_id is not None else None,
        "next_unit_id": state.next_unit_id,
        "next_building_id": state.next_building_id,
        "players": [
            {
                "id": int(p.id),
                "team_id": int(p.team_id),
                "gold": p.gold,
                "income_per_sec": p.income_per_sec,
                "upgrades": dict(p.upgrades),
                "active_upgrades": {
                    upgrade_id: {
                        "upgrade_id": au.upgrade_id,
                        "remaining_time": au.remaining_time,
                        "target_level": au.target_level,
                    }
                    for upgrade_id, au in p.active_upgrades.items()
                },
            }
            for p in state.players.values()
        ],
        "lanes": [
            {
                "id": int(lane.id),
                "length": lane.length,
                "unit_ids": [int(uid) for uid in lane.unit_ids],
                "building_ids": [int(bid) for bid in lane.building_ids],
            }
            for lane in state.lanes.values()
        ],
        "bases": [
            {
                "team_id": int(base.team_id),
                "lane_id": int(base.lane_id),
                "position": base.position,
                "hp": base.hp,
                "max_hp": base.max_hp,
                "alive": base.alive,
                "attack_range": base.attack_range,
                "attack_damage": base.attack_damage,
                "attack_cooldown": base.attack_cooldown,
                "attack_cooldown_remaining": base.attack_cooldown_remaining,
            }
            for base in (state.bases_list if state.bases_list else state.bases.values())
        ],
        "buildings": [
            {
                "id": int(b.id),
                "owner_player_id": int(b.owner_player_id),
                "team_id": int(b.team_id),
                "lane_id": int(b.lane_id),
                "position": b.position,
                "template_id": b.template_id,
                "level": b.level,
                "spawn_interval": b.spawn_interval,
                "spawn_timer": b.spawn_timer,
            }
            for b in state.buildings.values()
        ],
        "units": [
            {
                "id": int(u.id),
                "team_id": int(u.team_id),
                "lane_id": int(u.lane_id),
                "position": u.position,
                "max_hp": u.max_hp,
                "hp": u.hp,
                "damage": u.damage,
                "attack_range": u.attack_range,
                "attack_cooldown": u.attack_cooldown,
                "attack_cooldown_remaining": u.attack_cooldown_remaining,
                "speed": u.speed,
                "state": u.state,
                "alive": u.alive,
                "template_id": u.template_id,
                "vs_base_damage_multiplier": u.vs_base_damage_multiplier,
            }
            for u in state.units.values()
        ],
    }


def game_state_from_wire_dict(data: Dict[str, Any]) -> GameState:
    """Восстановить GameState из словаря."""
    state = GameState()

    state.tick = int(data["tick"])
    state.time = float(data["time"])
    state.running = bool(data["running"])

    winner_team_id = data.get("winner_team_id")
    state.winner_team_id = TeamId(int(winner_team_id)) if winner_team_id is not None else None

    state.next_unit_id = int(data["next_unit_id"])
    state.next_building_id = int(data["next_building_id"])

    for p_raw in data.get("players", []):
        pid = PlayerId(int(p_raw["id"]))
        upgrades_dict = p_raw.get("upgrades", {})
        if not isinstance(upgrades_dict, dict):
            upgrades_dict = {}
        
        active_upgrades_dict = p_raw.get("active_upgrades", {})
        if not isinstance(active_upgrades_dict, dict):
            active_upgrades_dict = {}
        
        from ascii_rts_castle.shared.models import ActiveUpgrade
        active_upgrades = {}
        for upgrade_id, au_data in active_upgrades_dict.items():
            active_upgrades[str(upgrade_id)] = ActiveUpgrade(
                upgrade_id=str(au_data.get("upgrade_id", upgrade_id)),
                remaining_time=float(au_data.get("remaining_time", 0.0)),
                target_level=int(au_data.get("target_level", 1)),
            )

        player = Player(
            id=pid,
            team_id=TeamId(int(p_raw["team_id"])),
            gold=float(p_raw["gold"]),
            income_per_sec=float(p_raw["income_per_sec"]),
            upgrades={str(k): int(v) for k, v in upgrades_dict.items()},
            active_upgrades=active_upgrades,
        )
        state.players[pid] = player

    for lane_raw in data.get("lanes", []):
        lid = LaneId(int(lane_raw["id"]))
        lane = Lane(
            id=lid,
            length=float(lane_raw["length"]),
        )
        lane.unit_ids = [UnitId(int(uid)) for uid in lane_raw.get("unit_ids", [])]
        lane.building_ids = [BuildingId(int(bid)) for bid in lane_raw.get("building_ids", [])]
        state.lanes[lid] = lane

    for base_raw in data.get("bases", []):
        base = Base(
            team_id=TeamId(int(base_raw["team_id"])),
            lane_id=LaneId(int(base_raw["lane_id"])),
            position=float(base_raw["position"]),
            hp=float(base_raw["hp"]),
            max_hp=float(base_raw["max_hp"]),
            alive=bool(base_raw.get("alive", True)),
            attack_range=float(base_raw.get("attack_range", 4.5)),
            attack_damage=float(base_raw.get("attack_damage", 15.0)),
            attack_cooldown=float(base_raw.get("attack_cooldown", 1.0)),
            attack_cooldown_remaining=float(base_raw.get("attack_cooldown_remaining", 0.0)),
        )
        # Добавляем в список всех баз
        state.bases_list.append(base)
        # Для обратной совместимости храним первую базу команды в словаре
        if base.team_id not in state.bases:
            state.bases[base.team_id] = base

    for b_raw in data.get("buildings", []):
        bid = BuildingId(int(b_raw["id"]))
        building = Building(
            id=bid,
            owner_player_id=PlayerId(int(b_raw["owner_player_id"])),
            team_id=TeamId(int(b_raw["team_id"])),
            lane_id=LaneId(int(b_raw["lane_id"])),
            position=float(b_raw["position"]),
            template_id=str(b_raw["template_id"]),
            level=int(b_raw["level"]),
            spawn_interval=float(b_raw["spawn_interval"]),
            spawn_timer=float(b_raw["spawn_timer"]),
        )
        state.buildings[bid] = building

    for u_raw in data.get("units", []):
        uid = UnitId(int(u_raw["id"]))
        unit_state = str(u_raw["state"])
        unit = Unit(
            id=uid,
            team_id=TeamId(int(u_raw["team_id"])),
            lane_id=LaneId(int(u_raw["lane_id"])),
            position=float(u_raw["position"]),
            max_hp=float(u_raw["max_hp"]),
            hp=float(u_raw["hp"]),
            damage=float(u_raw["damage"]),
            attack_range=float(u_raw["attack_range"]),
            attack_cooldown=float(u_raw["attack_cooldown"]),
            attack_cooldown_remaining=float(u_raw["attack_cooldown_remaining"]),
            speed=float(u_raw["speed"]),
            state=unit_state,  # type: ignore[arg-type]
            alive=bool(u_raw.get("alive", True)),
            template_id=str(u_raw.get("template_id", "")),
            vs_base_damage_multiplier=float(u_raw.get("vs_base_damage_multiplier", 1.0)),
        )
        state.units[uid] = unit

    return state


# === Сериализация сообщений ===


def message_to_dict(msg: AnyMessage) -> Dict[str, Any]:
    """Преобразовать сообщение во внешний словарь с полем type."""
    if isinstance(msg, JoinRequest):
        return {
            "type": MESSAGE_TYPE_JOIN_REQUEST,
            "name": msg.name,
        }
    if isinstance(msg, ReadyToStart):
        return {
            "type": MESSAGE_TYPE_READY_TO_START,
            "player_id": int(msg.player_id),
        }
    if isinstance(msg, PlayerCommandMessage):
        return {
            "type": MESSAGE_TYPE_PLAYER_COMMAND,
            "player_id": int(msg.player_id),
            "command": command_to_wire_dict(msg.command),
        }
    if isinstance(msg, JoinAccepted):
        return {
            "type": MESSAGE_TYPE_JOIN_ACCEPTED,
            "player_id": int(msg.player_id),
            "team_id": int(msg.team_id),
        }
    if isinstance(msg, StateSnapshot):
        return {
            "type": MESSAGE_TYPE_STATE_SNAPSHOT,
            "tick": msg.tick,
            "state": game_state_to_wire_dict(msg.state),
            "events": msg.events or [],
        }
    if isinstance(msg, GameOver):
        return {
            "type": MESSAGE_TYPE_GAME_OVER,
            "winner_team_id": int(msg.winner_team_id) if msg.winner_team_id is not None else None,
            "reason": msg.reason,
        }
    if isinstance(msg, ErrorMessage):
        return {
            "type": MESSAGE_TYPE_ERROR,
            "message": msg.message,
        }
    raise ValueError(f"Unsupported message type: {type(msg)!r}")


def message_from_dict(data: Dict[str, Any]) -> AnyMessage:
    """Восстановить сообщение из словаря с полем type."""
    msg_type = data.get("type")
    if msg_type == MESSAGE_TYPE_JOIN_REQUEST:
        return JoinRequest(name=str(data["name"]))
    if msg_type == MESSAGE_TYPE_READY_TO_START:
        return ReadyToStart(player_id=PlayerId(int(data["player_id"])))
    if msg_type == MESSAGE_TYPE_PLAYER_COMMAND:
        cmd_dict = data["command"]
        cmd = command_from_wire_dict(cmd_dict)
        return PlayerCommandMessage(
            player_id=PlayerId(int(data["player_id"])),
            command=cmd,
        )
    if msg_type == MESSAGE_TYPE_JOIN_ACCEPTED:
        return JoinAccepted(
            player_id=PlayerId(int(data["player_id"])),
            team_id=TeamId(int(data["team_id"])),
        )
    if msg_type == MESSAGE_TYPE_STATE_SNAPSHOT:
        state = game_state_from_wire_dict(data["state"])
        events = data.get("events") or []
        return StateSnapshot(
            tick=int(data["tick"]),
            state=state,
            events=list(events),
        )
    if msg_type == MESSAGE_TYPE_GAME_OVER:
        winner_team_id = data.get("winner_team_id")
        return GameOver(
            winner_team_id=TeamId(int(winner_team_id)) if winner_team_id is not None else None,
            reason=str(data["reason"]),
        )
    if msg_type == MESSAGE_TYPE_ERROR:
        return ErrorMessage(message=str(data["message"]))

    raise ValueError(f"Unknown message type: {msg_type!r}")


# === JSON ↔ bytes + фрейминг ===


def encode_message(msg: AnyMessage) -> bytes:
    """Сериализовать сообщение в JSON и закодировать в UTF-8 (без префикса длины)."""
    data = message_to_dict(msg)
    json_text = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    return json_text.encode("utf-8")


def decode_message_bytes(payload: bytes) -> AnyMessage:
    """Десериализовать сообщение из JSON-байтов (без префикса длины)."""
    json_text = payload.decode("utf-8")
    data = json.loads(json_text)
    if not isinstance(data, dict):
        raise ValueError("Invalid message payload: expected JSON object")
    return message_from_dict(data)


MESSAGE_LENGTH_HEADER_SIZE = 4


def frame_message(msg: AnyMessage) -> bytes:
    """
    Упаковать сообщение в length-prefixed формат:
    [4 байта длины big-endian][JSON UTF-8 payload].
    """
    payload = encode_message(msg)
    length = len(payload)
    header = length.to_bytes(MESSAGE_LENGTH_HEADER_SIZE, byteorder="big", signed=False)
    return header + payload


def extract_framed_message(buffer: bytes) -> tuple[Optional[AnyMessage], bytes]:
    """
    Пытается извлечь одно сообщение из буфера.

    Возвращает (message_or_None, remaining_bytes). Если данных недостаточно — (None, buffer).
    """
    if len(buffer) < MESSAGE_LENGTH_HEADER_SIZE:
        return None, buffer

    length = int.from_bytes(buffer[:MESSAGE_LENGTH_HEADER_SIZE], byteorder="big", signed=False)
    if len(buffer) < MESSAGE_LENGTH_HEADER_SIZE + length:
        return None, buffer

    payload = buffer[MESSAGE_LENGTH_HEADER_SIZE : MESSAGE_LENGTH_HEADER_SIZE + length]
    remaining = buffer[MESSAGE_LENGTH_HEADER_SIZE + length :]
    msg = decode_message_bytes(payload)
    return msg, remaining
