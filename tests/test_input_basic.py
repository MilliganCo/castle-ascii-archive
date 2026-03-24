"""Тесты для парсера команд ввода игрока."""

from __future__ import annotations

from ascii_rts_castle.client.input import ParsedInput, parse_command_line
from ascii_rts_castle.shared.commands import BuildCommand, UpgradeBuildingCommand
from ascii_rts_castle.shared.models import BuildingId, LaneId, PlayerId


def test_parse_build_command() -> None:
    parsed = parse_command_line("b 1 barracks", PlayerId(1))
    assert isinstance(parsed, ParsedInput)
    assert not parsed.should_quit
    assert parsed.message is None or "Invalid" not in parsed.message
    assert len(parsed.commands) == 1

    cmd = parsed.commands[0]
    assert isinstance(cmd, BuildCommand)
    assert cmd.player_id == PlayerId(1)
    assert cmd.lane_id == LaneId(1)
    assert cmd.building_type_id == "barracks"


def test_parse_upgrade_command() -> None:
    parsed = parse_command_line("u 3", PlayerId(2))
    assert not parsed.should_quit
    assert len(parsed.commands) == 1

    cmd = parsed.commands[0]
    assert isinstance(cmd, UpgradeBuildingCommand)
    assert cmd.player_id == PlayerId(2)
    assert cmd.building_id == BuildingId(3)


def test_parse_quit_variants() -> None:
    for text in ("q", "quit", "exit"):
        parsed = parse_command_line(text, PlayerId(1))
        assert parsed.should_quit
        assert parsed.commands == []


def test_parse_unknown_command() -> None:
    parsed = parse_command_line("foobar 1 2", PlayerId(1))
    assert not parsed.should_quit
    assert parsed.commands == []
    assert parsed.message is not None
