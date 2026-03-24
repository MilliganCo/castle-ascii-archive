"""Базовые тесты для кодеков сообщений и снапшотов состояния."""

from __future__ import annotations

from ascii_rts_castle.config import create_default_game_config
from ascii_rts_castle.server.engine import GameEngine
from ascii_rts_castle.shared.commands import BuildCommand
from ascii_rts_castle.shared.messages import (
    PlayerCommandMessage,
    StateSnapshot,
    decode_message_bytes,
    encode_message,
    extract_framed_message,
    frame_message,
)
from ascii_rts_castle.shared.models import LaneId, PlayerId, TeamId


def test_encode_decode_player_command_build() -> None:
    cmd = BuildCommand(
        player_id=PlayerId(1),
        lane_id=LaneId(1),
        building_type_id="barracks",
    )
    msg_out = PlayerCommandMessage(player_id=PlayerId(1), command=cmd)

    payload = encode_message(msg_out)
    msg_in = decode_message_bytes(payload)

    assert isinstance(msg_in, PlayerCommandMessage)
    assert msg_in.player_id == PlayerId(1)
    assert isinstance(msg_in.command, BuildCommand)
    assert msg_in.command.lane_id == LaneId(1)
    assert msg_in.command.building_type_id == "barracks"


def test_encode_decode_state_snapshot() -> None:
    cfg = create_default_game_config()
    engine = GameEngine(cfg, {PlayerId(1): TeamId(1), PlayerId(2): TeamId(2)})
    engine.tick(0.1)
    state = engine.state

    msg_out = StateSnapshot(tick=state.tick, state=state)
    payload = encode_message(msg_out)
    msg_in = decode_message_bytes(payload)

    assert isinstance(msg_in, StateSnapshot)
    assert msg_in.tick == state.tick
    assert len(msg_in.state.players) == len(state.players)
    assert len(msg_in.state.lanes) == len(state.lanes)
    assert len(msg_in.state.units) == len(state.units)


def test_frame_and_extract_message_roundtrip() -> None:
    cmd = BuildCommand(
        player_id=PlayerId(1),
        lane_id=LaneId(1),
        building_type_id="barracks",
    )
    msg = PlayerCommandMessage(player_id=PlayerId(1), command=cmd)

    framed = frame_message(msg)
    buffer = framed + b"extra"

    decoded_msg, remaining = extract_framed_message(buffer)

    assert isinstance(decoded_msg, PlayerCommandMessage)
    assert remaining == b"extra"
