"""
Обработка ввода игрока (клавиатура, маппинг на команды).

Этап 3: парсинг текстовых команд и фоновый обработчик ввода.
"""

from __future__ import annotations

import queue
import sys
import threading
from dataclasses import dataclass
from typing import List, TextIO

from ascii_rts_castle.shared.commands import (
    BuildCommand,
    GameCommand,
    ResearchUpgradeCommand,
    UpgradeBuildingCommand,
)
from ascii_rts_castle.shared.models import BuildingId, LaneId, PlayerId


@dataclass
class ParsedInput:
    """Результат разбора одной строки пользовательского ввода."""

    commands: List[GameCommand]
    should_quit: bool
    message: str | None = None


def parse_command_line(line: str, player_id: PlayerId) -> ParsedInput:
    """
    Разобрать одну строку пользовательского ввода.

    :param line: строка из stdin (включая или без завершающего символа новой строки)
    :param player_id: игрок, от имени которого отправляются команды
    """

    stripped = line.strip()
    if not stripped:
        return ParsedInput(commands=[], should_quit=False)

    parts = stripped.split()
    if not parts:
        return ParsedInput(commands=[], should_quit=False)

    cmd = parts[0].lower()

    # Выход из игры
    if cmd in {"q", "quit", "exit"}:
        return ParsedInput(commands=[], should_quit=True, message="Exiting...")

    # Помощь
    if cmd in {"h", "help"}:
        help_text = (
            "Commands: "
            "b/build <lane_id> <building_type_id>, "
            "r/research <upgrade_id>, "
            "u/upgrade <building_id>, "
            "q/quit/exit, h/help"
        )
        return ParsedInput(commands=[], should_quit=False, message=help_text)

    # Построить здание
    if cmd in {"b", "build"}:
        if len(parts) < 3:
            return ParsedInput(
                commands=[], should_quit=False, message="Usage: b <lane_id> <building_type_id>"
            )

        lane_str = parts[1]
        building_type_id = parts[2]

        try:
            lane_int = int(lane_str)
        except ValueError:
            return ParsedInput(commands=[], should_quit=False, message="Invalid lane id")

        build_command: GameCommand = BuildCommand(
            player_id=player_id,
            lane_id=LaneId(lane_int),
            building_type_id=building_type_id,
        )
        return ParsedInput(commands=[build_command], should_quit=False)

    # Апгрейд здания
    if cmd in {"u", "upgrade"}:
        if len(parts) < 2:
            return ParsedInput(commands=[], should_quit=False, message="Usage: u <building_id>")

        building_str = parts[1]

        try:
            building_int = int(building_str)
        except ValueError:
            return ParsedInput(commands=[], should_quit=False, message="Invalid building id")

        upgrade_command: GameCommand = UpgradeBuildingCommand(
            player_id=player_id,
            building_id=BuildingId(building_int),
        )
        return ParsedInput(commands=[upgrade_command], should_quit=False)

    # Исследовать апгрейд
    if cmd in {"r", "research"}:
        if len(parts) < 2:
            return ParsedInput(commands=[], should_quit=False, message="Usage: r <upgrade_id>")

        upgrade_id = parts[1]

        research_command: GameCommand = ResearchUpgradeCommand(
            player_id=player_id,
            upgrade_id=upgrade_id,
        )
        return ParsedInput(commands=[research_command], should_quit=False)

    # Неизвестная команда
    return ParsedInput(commands=[], should_quit=False, message="Unknown command")


class InputHandler:
    """
    Обработчик пользовательского ввода.

    В отдельном потоке читает строки из stdin, парсит в GameCommand,
    складывает команды в очередь. Главный цикл периодически забирает команды.
    """

    def __init__(self, player_id: PlayerId, stdin: TextIO | None = None) -> None:
        self.player_id = player_id
        self._stdin: TextIO = stdin if stdin is not None else sys.stdin
        self._queue: "queue.Queue[GameCommand]" = queue.Queue()
        self._should_quit = False
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._reader_loop, daemon=True)

    @property
    def should_quit(self) -> bool:
        return self._should_quit

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def poll_commands(self) -> List[GameCommand]:
        """
        Забирает все команды, накопленные с момента последнего вызова.
        Не блокирует.
        """
        commands: List[GameCommand] = []
        while True:
            try:
                cmd = self._queue.get_nowait()
            except queue.Empty:
                break
            commands.append(cmd)
        return commands

    def _reader_loop(self) -> None:
        """Фоновый цикл чтения из stdin."""
        while not self._stop_event.is_set():
            line = self._stdin.readline()
            if line == "":
                # EOF
                break

            parsed = parse_command_line(line, self.player_id)

            if parsed.message:
                print(parsed.message, file=sys.stderr)

            if parsed.should_quit:
                self._should_quit = True
                break

            for command in parsed.commands:
                self._queue.put(command)
