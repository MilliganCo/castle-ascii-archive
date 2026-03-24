"""
Точка входа клиентского процесса.

Этап 6: поддержка локального и сетевого режимов.
"""

from __future__ import annotations

import argparse
import asyncio
import time
from collections import deque
from typing import Deque, TYPE_CHECKING

from ascii_rts_castle.client.input import InputHandler, parse_command_line
from ascii_rts_castle.client.network import (
    ClientGameContext,
    NetworkClient,
    process_incoming_messages,
    wait_for_join_accepted,
)
from ascii_rts_castle.client.ui_ascii import (
    RenderConfig,
    ScreenBuffer,
    print_buffer,
    render_game_state,
)
from ascii_rts_castle.client.ui_window import ActionType, UserAction
from ascii_rts_castle.config import create_default_game_config
from ascii_rts_castle.server.engine import GameEngine
from ascii_rts_castle.shared.commands import BuildCommand, ResearchUpgradeCommand
from ascii_rts_castle.shared.messages import JoinRequest, PlayerCommandMessage, ReadyToStart
from ascii_rts_castle.shared.models import LaneId, PlayerId, TeamId

if TYPE_CHECKING:
    from ascii_rts_castle.client.ui_window import AsciiWindow, WindowConfig


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ASCII RTS Castle - Client")
    parser.add_argument(
        "--mode",
        choices=["local", "network"],
        default="local",
        help="Run in 'local' demo mode or 'network' client mode (default: local)",
    )
    parser.add_argument(
        "--ui",
        choices=["terminal", "window"],
        default="terminal",
        help="UI mode: 'terminal' (default) or 'window' (graphical ASCII window)",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=60,
        help="Target FPS for rendering (default: 60)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Server host for network mode")
    parser.add_argument("--port", type=int, default=8765, help="Server port for network mode")
    parser.add_argument("--name", default="Player", help="Player name for network mode")
    parser.add_argument(
        "--ai",
        action="store_true",
        help="Enable AI players in local mode (Player 2 will be controlled by AI)",
    )
    return parser.parse_args()


def _simple_ai_tick(engine: GameEngine, ai_player_id: PlayerId, game_config) -> None:
    """Улучшенная AI логика: строит здания и исследует апгрейды с проверкой наличия."""
    if ai_player_id not in engine.state.players:
        return
    
    player = engine.state.players[ai_player_id]
    import random
    
    # Считаем здания по типам на всех линиях
    building_counts: Dict[str, int] = {}
    total_buildings = 0
    for building in engine.state.buildings.values():
        if building.owner_player_id == ai_player_id:
            building_counts[building.template_id] = building_counts.get(building.template_id, 0) + 1
            total_buildings += 1
    
    # Считаем апгрейды
    total_upgrades = sum(player.upgrades.values())
    
    # AI действует реже и более осмысленно
    # Не строим, если уже много зданий одного типа
    if total_buildings >= 6:
        # Если уже много зданий, приоритет апгрейдам
        upgrade_templates_list = list(game_config.upgrade_templates.values())
        if upgrade_templates_list and player.gold >= 80:
            affordable_upgrades = [
                t for t in upgrade_templates_list
                if player.gold >= t.cost
                and player.upgrades.get(t.id, 0) < t.max_level
                and t.id not in player.active_upgrades
            ]
            if affordable_upgrades:
                # Приоритет апгрейдам для юнитов, если есть соответствующие здания
                preferred = []
                for t in affordable_upgrades:
                    if t.target_type == "unit" and t.target_id in building_counts:
                        if building_counts[t.target_id] > 0:
                            preferred.append(t)
                    elif t.target_type == "building" and t.target_id in building_counts:
                        if building_counts[t.target_id] > 0:
                            preferred.append(t)
                    elif t.target_type == "player":
                        preferred.append(t)
                
                template = random.choice(preferred) if preferred else random.choice(affordable_upgrades)
                cmd = ResearchUpgradeCommand(
                    player_id=ai_player_id,
                    upgrade_id=template.id,
                )
                engine.enqueue_command(cmd)
                return
    
    # Строим здания только если их мало или нет определённых типов
    sorted_lane_ids = sorted(engine.state.lanes.keys(), key=int)
    if not sorted_lane_ids:
        return
    
    # Выбираем линию с наименьшим количеством зданий
    lane_building_counts: Dict[LaneId, int] = {}
    for lane_id in sorted_lane_ids:
        lane = engine.state.lanes.get(lane_id)
        count = 0
        if lane:
            for bid in lane.building_ids:
                if bid in engine.state.buildings:
                    b = engine.state.buildings[bid]
                    if b.owner_player_id == ai_player_id:
                        count += 1
        lane_building_counts[lane_id] = count
    
    # Выбираем линию с наименьшим количеством зданий
    min_count = min(lane_building_counts.values()) if lane_building_counts else 0
    candidate_lanes = [lid for lid, cnt in lane_building_counts.items() if cnt == min_count]
    lane_id = random.choice(candidate_lanes) if candidate_lanes else sorted_lane_ids[0]
    
    building_templates_list = list(game_config.building_templates.values())
    
    # Логика строительства: приоритет разнообразию
    if player.gold >= 50:
        affordable_buildings = [t for t in building_templates_list if player.gold >= t.cost]
        if affordable_buildings:
            # Если нет gold_mine, приоритет ему
            if "gold_mine" not in building_counts and any(t.id == "gold_mine" for t in affordable_buildings):
                template = next(t for t in affordable_buildings if t.id == "gold_mine")
            # Если нет barracks, приоритет ему
            elif "barracks" not in building_counts and any(t.id == "barracks" for t in affordable_buildings):
                template = next(t for t in affordable_buildings if t.id == "barracks")
            # Иначе выбираем здание, которого меньше всего
            else:
                # Находим здания с минимальным количеством
                min_building_count = min(
                    (building_counts.get(t.id, 0) for t in affordable_buildings),
                    default=0
                )
                candidates = [
                    t for t in affordable_buildings
                    if building_counts.get(t.id, 0) == min_building_count
                ]
                template = random.choice(candidates)
            
            cmd = BuildCommand(
                player_id=ai_player_id,
                lane_id=lane_id,
                building_type_id=template.id,
            )
            engine.enqueue_command(cmd)
            return
    
    # Если есть достаточно золота и зданий, исследуем апгрейд
    upgrade_templates_list = list(game_config.upgrade_templates.values())
    if upgrade_templates_list and player.gold >= 80 and total_buildings >= 2:
        affordable_upgrades = [
            t for t in upgrade_templates_list
            if player.gold >= t.cost
            and player.upgrades.get(t.id, 0) < t.max_level
            and t.id not in player.active_upgrades
        ]
        if affordable_upgrades:
            # Приоритет апгрейдам для имеющихся зданий
            preferred = []
            for t in affordable_upgrades:
                if t.target_type == "unit" and t.target_id in building_counts:
                    if building_counts[t.target_id] > 0:
                        preferred.append(t)
                elif t.target_type == "building" and t.target_id in building_counts:
                    if building_counts[t.target_id] > 0:
                        preferred.append(t)
                elif t.target_type == "player":
                    preferred.append(t)
            
            template = random.choice(preferred) if preferred else random.choice(affordable_upgrades)
            cmd = ResearchUpgradeCommand(
                player_id=ai_player_id,
                upgrade_id=template.id,
            )
            engine.enqueue_command(cmd)


def run_local_demo(ai_enabled: bool = False) -> None:
    """Запустить локальную демку без сети, но с локальным вводом команд."""

    config = create_default_game_config()

    # Два игрока, две команды
    players_team_mapping = {
        PlayerId(1): TeamId(1),
        PlayerId(2): TeamId(2),
    }

    engine = GameEngine(config=config, players_team_mapping=players_team_mapping)

    # Убрали начальные здания для прогрессии
    # Игроки должны сами строить первые здания

    dt = 1.0 / 60.0  # 60 FPS
    render_config = RenderConfig(
        width=240, hud_height=3, lane_height=8, show_event_log=True, log_height=12, action_bar_height=3
    )

    input_handler = InputHandler(player_id=PlayerId(1))
    input_handler.start()

    event_log: Deque[str] = deque(maxlen=50)
    selected_lane_index = 0
    show_help = False
    lanes_count = len(engine.state.lanes)

    ai_tick_counter = 0
    try:
        while engine.state.running and not input_handler.should_quit:
            # 1. AI логика (каждые 30 тиков, примерно раз в 0.5 секунды при 60 FPS)
            if ai_enabled:
                ai_tick_counter += 1
                if ai_tick_counter >= 30:
                    ai_tick_counter = 0
                    _simple_ai_tick(engine, PlayerId(2), config)
            
            # 2. Забираем команды пользователя и передаём в движок
            for command in input_handler.poll_commands():
                engine.enqueue_command(command)

            # 3. Обновляем мир
            engine.tick(dt)

            # 4. Собираем события
            events = engine.consume_events()
            for e in events:
                event_log.append(e)

            # 5. Рендерим состояние
            buffer = render_game_state(
                engine.state,
                render_config,
                view_player_id=PlayerId(1),
                event_lines=list(event_log),
                selected_lane_index=selected_lane_index,
                show_help=show_help,
                game_config=config,
            )
            print_buffer(buffer)

            time.sleep(dt)
    except KeyboardInterrupt:
        # Позволяем пользователю прервать демо Ctrl+C
        pass
    finally:
        input_handler.stop()


def run_local_demo_window(fps: int = 60, ai_enabled: bool = False) -> None:
    """Запустить локальную демку в GUI-окне."""
    try:
        from ascii_rts_castle.client.ui_window import AsciiWindow, WindowConfig
    except ImportError as e:
        raise ImportError(
            "GUI mode requires pygame. Install it with: pip install -e '.[gui]'"
        ) from e

    game_config = create_default_game_config()

    players_team_mapping = {
        PlayerId(1): TeamId(1),
        PlayerId(2): TeamId(2),
    }

    engine = GameEngine(config=game_config, players_team_mapping=players_team_mapping)

    # Убрали начальные здания для прогрессии

    render_config = RenderConfig(
        width=240, hud_height=3, lane_height=8, show_event_log=True, log_height=12, action_bar_height=3
    )

    # Высота ScreenBuffer = hud_height + lanes + log_height + action_bar + запас для верхней линии
    lanes_count = len(engine.state.lanes)
    total_rows = (
        5  # Запас сверху для верхней линии
        + render_config.hud_height
        + lanes_count * render_config.lane_height
        + render_config.log_height
        + render_config.action_bar_height
    )

    window = AsciiWindow(
        WindowConfig(cols=render_config.width, rows=total_rows, title="ASCII RTS (Local GUI)")
    )
    window.set_render_config(render_config)

    event_log: Deque[str] = deque(maxlen=50)
    selected_lane_index = 0
    show_help = False
    dt = 1.0 / fps

    # Получаем список зданий и апгрейдов для обработки действий
    building_templates_list = list(game_config.building_templates.values())[:4]
    upgrade_templates_list = list(game_config.upgrade_templates.values())[:4]

    try:
        last_ai_tick = 0
        while engine.state.running and window.running:
            # 1. AI логика (каждые 30 тиков движка, примерно раз в 0.5 секунды при 60 FPS)
            if ai_enabled:
                current_tick = engine.state.tick
                if current_tick - last_ai_tick >= 30:
                    last_ai_tick = current_tick
                    _simple_ai_tick(engine, PlayerId(2), game_config)
            
            # 2. Обработка действий из окна
            actions = window.poll_actions()
            for action in actions:
                if action.action_type == ActionType.QUIT:
                    engine.state.running = False
                    break
                elif action.action_type == ActionType.LANE_UP:
                    selected_lane_index = (selected_lane_index - 1) % lanes_count
                elif action.action_type == ActionType.LANE_DOWN:
                    selected_lane_index = (selected_lane_index + 1) % lanes_count
                elif action.action_type == ActionType.HELP:
                    show_help = not show_help
                elif action.action_type == ActionType.BUILD and action.value is not None:
                    slot = int(action.value)
                    if 0 <= slot < len(building_templates_list):
                        template = building_templates_list[slot]
                        sorted_lane_ids = sorted(engine.state.lanes.keys(), key=int)
                        if selected_lane_index < len(sorted_lane_ids):
                            lane_id = sorted_lane_ids[selected_lane_index]
                            cmd = BuildCommand(
                                player_id=PlayerId(1),
                                lane_id=lane_id,
                                building_type_id=template.id,
                            )
                            engine.enqueue_command(cmd)
                elif action.action_type == ActionType.UPGRADE and action.value is not None:
                    slot = int(action.value)
                    if 0 <= slot < len(upgrade_templates_list):
                        template = upgrade_templates_list[slot]
                        cmd = ResearchUpgradeCommand(
                            player_id=PlayerId(1),
                            upgrade_id=template.id,
                        )
                        engine.enqueue_command(cmd)
                elif action.action_type == ActionType.BASE_ABILITY and action.value is not None:
                    slot = int(action.value)
                    if game_config and game_config.base_ability_templates:
                        ability_templates_list = list(game_config.base_ability_templates.values())[:4]
                        if 0 <= slot < len(ability_templates_list):
                            template = ability_templates_list[slot]
                            sorted_lane_ids = sorted(engine.state.lanes.keys(), key=int)
                            if selected_lane_index < len(sorted_lane_ids):
                                lane_id = sorted_lane_ids[selected_lane_index]
                                from ascii_rts_castle.shared.commands import ActivateBaseAbilityCommand
                                cmd = ActivateBaseAbilityCommand(
                                    player_id=PlayerId(1),
                                    lane_id=lane_id,
                                    ability_id=template.id,
                                )
                                engine.enqueue_command(cmd)
                elif action.action_type == ActionType.TEXT_INPUT and action.text:
                    # Fallback для текстового ввода
                    parsed = parse_command_line(action.text, PlayerId(1))
                    if parsed.should_quit:
                        engine.state.running = False
                        break
                    for cmd in parsed.commands:
                        engine.enqueue_command(cmd)

            # 3. Тик движка
            engine.tick(dt)

            events = engine.consume_events()
            for e in events:
                event_log.append(e)

            # 3. Рендер
            buffer = render_game_state(
                engine.state,
                render_config,
                view_player_id=PlayerId(1),
                event_lines=list(event_log),
                selected_lane_index=selected_lane_index,
                show_help=show_help,
                game_config=game_config,
            )
            window.draw(buffer)

            time.sleep(dt)
    finally:
        window.close()


async def run_network_client(host: str, port: int, name: str, fps: int = 60) -> None:
    """Запустить сетевого клиента, подключиться к серверу и играть."""
    game_config = create_default_game_config()
    render_config = RenderConfig(
        width=240, hud_height=3, lane_height=8, show_event_log=True, log_height=12, action_bar_height=3
    )

    client = NetworkClient(host=host, port=port)
    await client.connect()

    ctx = ClientGameContext()

    # 1. Join
    await client.send(JoinRequest(name=name))
    await wait_for_join_accepted(client, ctx)

    if ctx.player_id is None:
        raise RuntimeError("JoinAccepted did not set player_id")

    # 2. InputHandler запускаем уже с реальным player_id
    input_handler = InputHandler(player_id=ctx.player_id)
    input_handler.start()

    # 3. Сообщаем серверу, что готовы начать
    await client.send(ReadyToStart(player_id=ctx.player_id))

    dt = 1.0 / fps

    try:
        while not ctx.game_over:
            # Обновить состояние на основе входящих сообщений
            await process_incoming_messages(client, ctx)

            # Отправить команды игрока, если есть
            for cmd in input_handler.poll_commands():
                if ctx.player_id is None:
                    continue
                msg = PlayerCommandMessage(player_id=ctx.player_id, command=cmd)
                await client.send(msg)

            # Рендер: если ещё нет состояния от сервера — показать экраны ожидания
            if ctx.last_state is not None and ctx.player_id is not None:
                lanes_count = len(ctx.last_state.lanes)
                buffer = render_game_state(
                    ctx.last_state,
                    render_config,
                    view_player_id=ctx.player_id,
                    event_lines=list(ctx.event_log),
                    selected_lane_index=ctx.selected_lane_index,
                    show_help=ctx.show_help,
                    game_config=game_config,
                )
            else:
                buffer = ScreenBuffer(render_config.width, render_config.hud_height + 1)
                buffer.clear(" ")
                buffer.put_text(0, 0, "Waiting for server state...")

            print_buffer(buffer)

            await asyncio.sleep(dt)

        # Игра завершена — можно показать финальный статус
        if ctx.game_over_reason:
            # Можно вывести reason в stderr/лог
            print(f"Game over: {ctx.game_over_reason}")
    except KeyboardInterrupt:
        pass
    finally:
        input_handler.stop()
        await client.close()


async def run_network_client_window(host: str, port: int, name: str, fps: int = 60) -> None:
    """Запустить сетевого клиента в GUI-окне."""
    try:
        from ascii_rts_castle.client.ui_window import AsciiWindow, WindowConfig
    except ImportError as e:
        raise ImportError(
            "GUI mode requires pygame. Install it with: pip install -e '.[gui]'"
        ) from e

    game_config = create_default_game_config()
    render_config = RenderConfig(
        width=240, hud_height=3, lane_height=8, show_event_log=True, log_height=12, action_bar_height=3
    )

    client = NetworkClient(host=host, port=port)
    await client.connect()

    ctx = ClientGameContext()

    await client.send(JoinRequest(name=name))
    await wait_for_join_accepted(client, ctx)

    if ctx.player_id is None:
        raise RuntimeError("JoinAccepted did not set player_id")

    # Настройка окна
    lanes_count = 3  # По умолчанию, обновится после первого StateSnapshot
    total_rows = (
        5  # Запас сверху для верхней линии
        + render_config.hud_height
        + lanes_count * render_config.lane_height
        + render_config.log_height
        + render_config.action_bar_height
    )
    window = AsciiWindow(
        WindowConfig(cols=render_config.width, rows=total_rows, title="ASCII RTS (Network GUI)")
    )
    window.set_render_config(render_config)

    dt = 1.0 / fps

    # Получаем список зданий и апгрейдов для обработки действий
    building_templates_list = list(game_config.building_templates.values())[:4]
    upgrade_templates_list = list(game_config.upgrade_templates.values())[:4]

    try:
        while not ctx.game_over and window.running:
            # 1. Обработка входящих сообщений
            await process_incoming_messages(client, ctx)
            
            # Обновляем lanes_count из состояния
            if ctx.last_state is not None:
                lanes_count = len(ctx.last_state.lanes)

            # 2. Обработка действий из окна
            actions = window.poll_actions()
            for action in actions:
                if action.action_type == ActionType.QUIT:
                    ctx.game_over = True
                    break
                elif action.action_type == ActionType.LANE_UP:
                    ctx.selected_lane_index = (ctx.selected_lane_index - 1) % lanes_count
                elif action.action_type == ActionType.LANE_DOWN:
                    ctx.selected_lane_index = (ctx.selected_lane_index + 1) % lanes_count
                elif action.action_type == ActionType.HELP:
                    ctx.show_help = not ctx.show_help
                elif action.action_type == ActionType.BUILD and action.value is not None and ctx.player_id is not None:
                    slot = int(action.value)
                    if 0 <= slot < len(building_templates_list):
                        template = building_templates_list[slot]
                        sorted_lane_ids = sorted(ctx.last_state.lanes.keys(), key=int) if ctx.last_state else []
                        if ctx.selected_lane_index < len(sorted_lane_ids):
                            lane_id = sorted_lane_ids[ctx.selected_lane_index]
                            cmd = BuildCommand(
                                player_id=ctx.player_id,
                                lane_id=lane_id,
                                building_type_id=template.id,
                            )
                            msg = PlayerCommandMessage(player_id=ctx.player_id, command=cmd)
                            await client.send(msg)
                elif action.action_type == ActionType.UPGRADE and action.value is not None and ctx.player_id is not None:
                    slot = int(action.value)
                    if 0 <= slot < len(upgrade_templates_list):
                        template = upgrade_templates_list[slot]
                        cmd = ResearchUpgradeCommand(
                            player_id=ctx.player_id,
                            upgrade_id=template.id,
                        )
                        msg = PlayerCommandMessage(player_id=ctx.player_id, command=cmd)
                        await client.send(msg)
                elif action.action_type == ActionType.BASE_ABILITY and action.value is not None and ctx.player_id is not None:
                    slot = int(action.value)
                    if game_config and game_config.base_ability_templates:
                        ability_templates_list = list(game_config.base_ability_templates.values())[:4]
                        if 0 <= slot < len(ability_templates_list):
                            template = ability_templates_list[slot]
                            sorted_lane_ids = sorted(ctx.last_state.lanes.keys(), key=int) if ctx.last_state else []
                            if ctx.selected_lane_index < len(sorted_lane_ids):
                                lane_id = sorted_lane_ids[ctx.selected_lane_index]
                                cmd = ActivateBaseAbilityCommand(
                                    player_id=ctx.player_id,
                                    lane_id=lane_id,
                                    ability_id=template.id,
                                )
                                msg = PlayerCommandMessage(player_id=ctx.player_id, command=cmd)
                                await client.send(msg)
                elif action.action_type == ActionType.TEXT_INPUT and action.text and ctx.player_id is not None:
                    # Fallback для текстового ввода
                    parsed = parse_command_line(action.text, ctx.player_id)
                    if parsed.should_quit:
                        ctx.game_over = True
                        break
                    for cmd in parsed.commands:
                        msg = PlayerCommandMessage(player_id=ctx.player_id, command=cmd)
                        await client.send(msg)

            # 3. Рендер
            if ctx.last_state is not None and ctx.player_id is not None:
                buffer = render_game_state(
                    ctx.last_state,
                    render_config,
                    view_player_id=ctx.player_id,
                    event_lines=list(ctx.event_log),
                    selected_lane_index=ctx.selected_lane_index,
                    show_help=ctx.show_help,
                    game_config=game_config,
                )
            else:
                # Экран ожидания
                buffer = ScreenBuffer(render_config.width, 5)
                buffer.clear(" ")
                buffer.put_text(0, 0, "Waiting for server state...")

            window.draw(buffer)

            await asyncio.sleep(dt)
    finally:
        await client.close()
        window.close()


def main() -> None:
    args = _parse_args()
    if args.mode == "local":
        if args.ui == "terminal":
            run_local_demo(ai_enabled=args.ai)
        else:
            run_local_demo_window(fps=args.fps, ai_enabled=args.ai)
    else:
        if args.ui == "terminal":
            asyncio.run(run_network_client(args.host, args.port, args.name, fps=args.fps))
        else:
            asyncio.run(run_network_client_window(args.host, args.port, args.name, fps=args.fps))


if __name__ == "__main__":
    main()
