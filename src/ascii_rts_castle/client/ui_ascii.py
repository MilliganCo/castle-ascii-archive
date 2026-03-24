"""
ASCII-рендер для отображения игрового состояния в терминале.

Основной интерфейс — `ScreenBuffer` и функция `render_game_state`,
которые удобно тестировать независимо от реального терминала.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ascii_rts_castle.config import BuildingTemplate, GameConfig, UpgradeTemplate, create_default_game_config
from ascii_rts_castle.shared.models import Building, GameState, Lane, LaneId, PlayerId, Unit


@dataclass
class RenderConfig:
    """Конфигурация ASCII-рендера."""

    width: int = 240  # Увеличено для лучшей читаемости (было 200)
    hud_height: int = 3
    lane_height: int = 8  # Увеличено для лучшей видимости линий и зданий (было 6)
    show_borders: bool = True
    show_event_log: bool = True
    log_height: int = 10  # Увеличено
    action_bar_height: int = 3  # высота панели действий


@dataclass
class Cell:
    """Ячейка буфера с символом и цветом."""
    ch: str = " "
    color: Optional[Tuple[int, int, int]] = None  # RGB цвет для GUI режима


@dataclass
class ScreenBuffer:
    """Простой буфер символов для постройки ASCII-карты с поддержкой цвета."""

    width: int
    height: int
    cells: List[List[Cell]] = field(init=False)

    def __post_init__(self) -> None:
        self.cells = [[Cell() for _ in range(self.width)] for _ in range(self.height)]

    def clear(self, fill: str = " ") -> None:
        for y in range(self.height):
            for x in range(self.width):
                self.cells[y][x] = Cell(ch=fill)

    def put(self, x: int, y: int, ch: str, color: Optional[Tuple[int, int, int]] = None) -> None:
        if not (0 <= x < self.width and 0 <= y < self.height):
            return
        if not ch:
            return
        self.cells[y][x] = Cell(ch=ch[0], color=color)

    def put_colored(self, x: int, y: int, ch: str, color: Tuple[int, int, int]) -> None:
        """Установить символ с цветом."""
        self.put(x, y, ch, color)

    def put_text(self, x: int, y: int, text: str, color: Optional[Tuple[int, int, int]] = None) -> None:
        for i, ch in enumerate(text):
            self.put(x + i, y, ch, color)

    def as_lines(self) -> List[str]:
        """Возвращает строки без цвета (для терминала)."""
        return ["".join(cell.ch for cell in row) for row in self.cells]

    def as_str(self) -> str:
        return "\n".join(self.as_lines())


def clear_terminal() -> None:
    """Очистить терминал и вернуть курсор в левый верхний угол."""

    sys.stdout.write("\x1b[2J\x1b[H")
    sys.stdout.flush()


def print_buffer(buffer: ScreenBuffer) -> None:
    """Вывести буфер в терминал."""

    clear_terminal()
    sys.stdout.write(buffer.as_str())
    sys.stdout.flush()


# Маппинг команд → символов
TEAM_BASE_CHARS: Dict[int, str] = {
    1: "A",
    2: "B",
    3: "C",
    4: "D",
}

TEAM_UNIT_CHARS: Dict[int, str] = {
    1: "a",
    2: "b",
    3: "c",
    4: "d",
}

BUILDING_CHAR: str = "S"  # structure (fallback)
ROAD_CHAR: str = "."

# Символы для разных типов юнитов
UNIT_TYPE_CHAR: Dict[str, str] = {
    "infantry": "I",
    "archer": "A",
    "mage": "M",
    "siege": "S",
}

# Символы для разных типов зданий
BUILDING_TYPE_CHAR: Dict[str, str] = {
    "barracks": "B",
    "archery_range": "R",
    "mage_tower": "T",
    "siege_workshop": "W",
    "gold_mine": "G",
}

# ANSI-цвета
RESET = "\x1b[0m"

# Команды: Team 1 — зелёные, Team 2 — красные и т.д.
TEAM_COLORS: Dict[int, str] = {
    1: "\x1b[32m",  # green
    2: "\x1b[31m",  # red
    3: "\x1b[34m",  # blue
    4: "\x1b[33m",  # yellow
}

BASE_COLOR = "\x1b[1m"  # жирный
BUILDING_COLOR = "\x1b[36m"  # cyan
HUD_COLOR = "\x1b[37m"  # white


def render_game_state(
    state: GameState,
    config: RenderConfig,
    view_player_id: Optional[PlayerId] = None,
    event_lines: Optional[List[str]] = None,
    selected_lane_index: int = 0,
    show_help: bool = False,
    game_config: Optional[GameConfig] = None,
) -> ScreenBuffer:
    """
    Построить ASCII-представление состояния игры.

    view_player_id — игрок, для которого рисуем HUD (его ресурсы и т.п.).
    event_lines — список строк событий для отображения в логе.
    selected_lane_index — индекс выбранной линии (0-based).
    show_help — показывать ли экран подсказки.
    game_config — конфигурация игры для панели действий.
    """

    if show_help:
        return _render_help_screen(config, game_config)

    lanes_count = len(state.lanes)
    log_h = config.log_height if config.show_event_log else 0
    action_h = config.action_bar_height
    # Добавляем запас для верхней линии, которая может быть выше hud_height из-за синусного сдвига
    # Верхняя линия может подняться на offset_amplitude (1.5) выше начальной позиции
    top_margin = 5  # Запас сверху для верхней линии
    map_height = top_margin + config.hud_height + lanes_count * config.lane_height + log_h + action_h

    buffer = ScreenBuffer(width=config.width, height=map_height)
    buffer.clear(" ")

    # Рисуем HUD со смещением вниз на top_margin
    _render_hud_with_offset(buffer, state, config, view_player_id, selected_lane_index, lanes_count, top_margin)
    _render_lanes_and_entities_with_offset(buffer, state, config, selected_lane_index, top_margin)
    
    if event_lines is None:
        event_lines = []
    # Лог событий тоже нужно сместить
    _render_event_log_with_offset(buffer, config, lanes_count, event_lines, top_margin)
    _render_action_bar(buffer, config, lanes_count, game_config, view_player_id, state, selected_lane_index)

    return buffer


def _render_hud(
    buffer: ScreenBuffer,
    state: GameState,
    config: RenderConfig,
    view_player_id: Optional[PlayerId],
    selected_lane_index: int,
    lanes_count: int,
) -> None:
    """Отрисовка HUD без смещения (для обратной совместимости)."""
    _render_hud_with_offset(buffer, state, config, view_player_id, selected_lane_index, lanes_count, 0)


def _render_hud_with_offset(
    buffer: ScreenBuffer,
    state: GameState,
    config: RenderConfig,
    view_player_id: Optional[PlayerId],
    selected_lane_index: int,
    lanes_count: int,
    y_offset: int,
) -> None:
    """Отрисовка HUD со смещением по Y."""
    # Строка 0: общая информация
    line0 = f"Tick: {state.tick}  Time: {state.time:.1f}s"
    if state.winner_team_id is not None:
        line0 += f"  WINNER: Team {int(state.winner_team_id)}"
    buffer.put_text(0, y_offset + 0, line0[: config.width])

    # Строка 1: информация о выбранном игроке
    if view_player_id is not None and view_player_id in state.players and config.hud_height >= 2:
        player = state.players[view_player_id]
        # Найти базу своей команды и базу противника
        own_base_hp: Optional[float] = None
        enemy_base_hp: Optional[float] = None
        for base in state.bases.values():
            if base.team_id == player.team_id:
                own_base_hp = base.hp
            else:
                enemy_base_hp = base.hp

        parts = [
            f"P{int(player.id)} T{int(player.team_id)}",
            f"Gold={int(player.gold)}",
            f"Inc={player.income_per_sec:.1f}/s",
            f"Lane: {selected_lane_index + 1}/{lanes_count}",
        ]
        if own_base_hp is not None:
            parts.append(f"BaseHP={own_base_hp:.0f}")
        if enemy_base_hp is not None:
            parts.append(f"EnemyBaseHP={enemy_base_hp:.0f}")

        buffer.put_text(0, y_offset + 1, " | ".join(parts)[: config.width])

    # Строка 2: подсказки управления
    if config.hud_height >= 3:
        buffer.put_text(
            0,
            y_offset + 2,
            "Up/Down: select lane | 1-4: build | Q/W/E/R: upgrade | H: help | ESC/q: quit"[: config.width],
        )


def lane_position_to_xy(
    lane_index: int,
    position: float,
    lane_length: float,
    config: RenderConfig,
    lanes_count: int,
    y_offset: int = 0,
) -> Tuple[int, int]:
    """
    Преобразует позицию на линии в экранные координаты (x, y) с пересечением в центре.
    
    Три линии от баз B к базам A, все пересекаются в одной центральной точке.
    """
    if lane_length <= 0:
        return (0, 0)
    
    import math
    
    # Нормализованная позиция (0.0 = база B, 1.0 = база A)
    t = max(0.0, min(1.0, position / lane_length if lane_length > 0 else 0.0))
    
    # Фиксированные точки баз
    x_B = 3  # Левая база (B)
    x_A = config.width - 4  # Правая база (A)
    
    # Высота области линий
    lane_area_height = lanes_count * config.lane_height
    mid_y = y_offset + config.hud_height + lane_area_height // 2
    
    # Y координаты для трёх линий у баз - линии дальше друг от друга
    # Верхняя линия начинается выше, нижняя ниже, средняя в центре
    lane_spacing = config.lane_height  # Расстояние между линиями
    if lane_index == 0:  # Верхняя линия
        y_B_line = y_offset + config.hud_height + lane_spacing // 2
        y_A_line = y_offset + config.hud_height + lane_spacing // 2
    elif lane_index == 1:  # Средняя линия
        y_B_line = mid_y
        y_A_line = mid_y
    else:  # lane_index == 2, нижняя линия
        y_B_line = y_offset + config.hud_height + lane_area_height - lane_spacing // 2
        y_A_line = y_offset + config.hud_height + lane_area_height - lane_spacing // 2
    
    # Общий центр пересечения - все линии сходятся в одной точке
    x_C = config.width // 2
    # Верхняя линия не должна подниматься слишком высоко в центре - делаем её чуть ниже
    if lane_index == 0:
        # Верхняя линия сходится чуть ниже центра, чтобы не "висеть в воздухе"
        y_C = mid_y - 2  # На 2 пикселя ниже центра
    elif lane_index == 2:
        # Нижняя линия сходится ближе к центральной (приподнимаем)
        y_C = mid_y + 1  # На 1 пиксель выше центра (было +2)
    else:
        y_C = mid_y  # Средняя линия точно в центре
    t_center = 0.5
    
    # Вычисляем координаты
    if t <= t_center:
        # От базы B до центра
        s = t / t_center  # 0..1
        x0, y0 = x_B, y_B_line
        x1, y1 = x_C, y_C
    else:
        # От центра до базы A
        s = (t - t_center) / (1 - t_center)  # 0..1
        x0, y0 = x_C, y_C
        x1, y1 = x_A, y_A_line
    
    # Линейная интерполяция
    x = (1 - s) * x0 + s * x1
    y = (1 - s) * y0 + s * y1
    
    # Добавляем синусный сдвиг для дугообразной формы
    # Амплитуда больше для более выраженной дуги
    offset_amplitude = [3.0, 2.0, 3.0][lane_index]  # Разная амплитуда для разных линий
    # Используем sin для создания плавной дуги
    y += int(round(offset_amplitude * math.sin(t * math.pi)))
    
    x = int(round(x))
    y = int(round(y))
    
    # Ограничиваем координаты (учитываем, что верхняя линия может быть выше)
    x = max(0, min(config.width - 1, x))
    # Y координата уже включает y_offset, ограничиваем только снизу
    min_y = y_offset  # Разрешаем рисовать с начала области линий
    max_y = y_offset + config.hud_height + lane_area_height + 5  # Запас для синусного сдвига
    y = max(min_y, min(max_y, y))
    
    return (x, y)


def _render_lanes_and_entities(
    buffer: ScreenBuffer,
    state: GameState,
    config: RenderConfig,
    selected_lane_index: int,
) -> None:
    """Отрисовка линий без смещения (для обратной совместимости)."""
    _render_lanes_and_entities_with_offset(buffer, state, config, selected_lane_index, 0)


def _render_lanes_and_entities_with_offset(
    buffer: ScreenBuffer,
    state: GameState,
    config: RenderConfig,
    selected_lane_index: int,
    y_offset: int,
) -> None:
    """Отрисовка линий со смещением по Y."""
    if not state.lanes:
        return

    sorted_lane_ids: List[LaneId] = sorted(state.lanes.keys(), key=int)
    lanes_count = len(sorted_lane_ids)
    
    # Сначала рисуем декорации (фон) со смещением
    _render_decorations_with_offset(buffer, config, lanes_count, y_offset, state)

    for lane_index, lane_id in enumerate(sorted_lane_ids):
        lane = state.lanes[lane_id]
        is_selected = lane_index == selected_lane_index
        
        # Рисуем дорогу по кривой со смещением
        _render_lane_background_curved_with_offset(buffer, lane, lane_index, lanes_count, config, is_selected, y_offset)
        
        # Рисуем сущности (здания перед юнитами) со смещением
        _render_bases_on_lane_curved_with_offset(buffer, state, lane, lane_index, lanes_count, config, y_offset)
        _render_buildings_on_lane_curved_with_offset(buffer, state, lane, lane_index, lanes_count, config, y_offset)
        _render_neutral_objects_on_lane_curved_with_offset(buffer, state, lane, lane_index, lanes_count, config, y_offset)
        _render_units_on_lane_curved_with_offset(buffer, state, lane, lane_index, lanes_count, config, y_offset)
        # Рисуем визуальные эффекты способностей
        _render_visual_effects_on_lane_curved_with_offset(buffer, state, lane, lane_index, lanes_count, config, y_offset)


def _render_lane_background_curved(
    buffer: ScreenBuffer,
    lane: Lane,
    lane_index: int,
    lanes_count: int,
    config: RenderConfig,
    is_selected: bool,
) -> None:
    """Отрисовывает кривую дорогу для линии по кривой Безье."""
    _render_lane_background_curved_with_offset(buffer, lane, lane_index, lanes_count, config, is_selected, 0)


def _render_lane_background_curved_with_offset(
    buffer: ScreenBuffer,
    lane: Lane,
    lane_index: int,
    lanes_count: int,
    config: RenderConfig,
    is_selected: bool,
    y_offset: int,
) -> None:
    """Отрисовывает кривую дорогу для линии со смещением по Y."""
    lane_length = lane.length
    # Рисуем дорогу по контрольным точкам (больше шагов для плавности)
    steps = config.width * 2  # Больше точек для плавной кривой
    road_points: List[Tuple[int, int]] = []
    for i in range(steps):
        position = (i / steps) * lane_length
        x, y = lane_position_to_xy(lane_index, position, lane_length, config, lanes_count, y_offset)
        road_points.append((x, y))
    
    # Рисуем дорогу, убирая дубликаты
    seen_points: set[Tuple[int, int]] = set()
    for x, y in road_points:
        if (x, y) not in seen_points and 0 <= y < buffer.height:
            seen_points.add((x, y))
            # Выделяем выбранную линию
            if is_selected:
                buffer.put(x, y, "=")
            else:
                buffer.put(x, y, ROAD_CHAR)


def _render_decorations(
    buffer: ScreenBuffer,
    config: RenderConfig,
    lanes_count: int,
) -> None:
    """Отрисовывает декорации (лес/горы) по краям карты."""
    _render_decorations_with_offset(buffer, config, lanes_count, 0)


def _render_decorations_with_offset(
    buffer: ScreenBuffer,
    config: RenderConfig,
    lanes_count: int,
    y_offset: int,
    state: Optional[GameState] = None,
) -> None:
    """Отрисовывает декорации (лес/горы) по краям карты со смещением и тусклые анимированные декорации."""
    import math
    
    lane_area_height = lanes_count * config.lane_height
    start_y = y_offset + config.hud_height
    end_y = start_y + lane_area_height
    
    # Лес/горы слева (около базы B)
    for y in range(start_y, end_y):
        if y < buffer.height and y % 3 == 0:  # Редко, чтобы не перегружать
            buffer.put(0, y, "^")
            buffer.put(1, y, "#")
    
    # Лес/горы справа (около базы A)
    for y in range(start_y, end_y):
        if y < buffer.height and y % 3 == 1:  # Смещение относительно левой стороны
            buffer.put(config.width - 2, y, "^")
            buffer.put(config.width - 1, y, "#")
    
    # Редкие точки между линиями для заполнения пространства
    for y in range(start_y + 1, end_y - 1, 2):
        if y < buffer.height and y % 4 == 0:
            buffer.put(config.width // 4, y, "~")
            buffer.put(3 * config.width // 4, y, "~")
    
    # Тусклые анимированные декорации (периодически появляющиеся/исчезающие)
    if state is not None:
        # Используем tick для анимации
        time_factor = state.time if hasattr(state, 'time') else 0.0
        
        # Декоративные символы: ✿, ✾, ✽, ❋, ❊, ❉, ❈, ❇, ❆, ❅, ❄, ✲, ✱, ✰, ✯, ✮, ✭, ✬, ✫, ✪
        decor_chars = ["✿", "✾", "✽", "❋", "❊", "❉", "❈", "❇", "❆", "❅", "❄", "✲", "✱", "✰", "✯", "✮", "✭", "✬", "✫", "✪"]
        
        # Тусклые цвета (низкая яркость)
        dim_colors = [
            (40, 60, 40),    # Тёмно-зелёный
            (60, 40, 40),    # Тёмно-красный
            (40, 40, 60),    # Тёмно-синий
            (50, 50, 30),    # Тёмно-жёлтый
            (50, 40, 50),    # Тёмно-фиолетовый
        ]
        
        # Размещаем декорации случайно, но с анимацией появления/исчезания
        for i in range(15):  # Количество декораций
            # Используем детерминированную "случайность" на основе позиции
            seed_x = (i * 17 + int(time_factor * 2)) % config.width
            seed_y = (i * 23 + int(time_factor * 3)) % lane_area_height + start_y
            
            if seed_y < start_y or seed_y >= end_y or seed_y >= buffer.height:
                continue
            
            # Анимация: синусоидальная прозрачность (появляется и исчезает)
            anim_phase = (time_factor * 0.5 + i * 0.3) % (2 * math.pi)
            alpha = (math.sin(anim_phase) + 1.0) / 2.0  # 0.0 - 1.0
            
            # Показываем только если alpha > 0.3 (чтобы не было полностью невидимым)
            if alpha > 0.3:
                char_idx = i % len(decor_chars)
                color_idx = i % len(dim_colors)
                
                # Применяем alpha к цвету (делаем ещё тусклее)
                base_color = dim_colors[color_idx]
                final_color = tuple(int(c * alpha * 0.6) for c in base_color)  # Дополнительно уменьшаем яркость
                
                # Проверяем, что не перезаписываем важные элементы (дороги, юниты, здания)
                # Размещаем только в свободных местах
                if 5 < seed_x < config.width - 5:  # Не слишком близко к краям
                    buffer.put_colored(seed_x, seed_y, decor_chars[char_idx], final_color)


def _position_to_x(position: float, lane_length: float, config: RenderConfig) -> int:
    """Устаревшая функция, используется для обратной совместимости."""
    if lane_length <= 0:
        return 0
    usable_width = max(1, config.width - 2)
    scale = usable_width / lane_length
    x = int(position * scale) + 1
    if x < 0:
        return 0
    if x >= config.width:
        return config.width - 1
    return x


def _render_bases_on_lane_curved(
    buffer: ScreenBuffer,
    state: GameState,
    lane: Lane,
    lane_index: int,
    lanes_count: int,
    config: RenderConfig,
) -> None:
    """Отрисовка баз без смещения (для обратной совместимости)."""
    _render_bases_on_lane_curved_with_offset(buffer, state, lane, lane_index, lanes_count, config, 0)


def _render_bases_on_lane_curved_with_offset(
    buffer: ScreenBuffer,
    state: GameState,
    lane: Lane,
    lane_index: int,
    lanes_count: int,
    config: RenderConfig,
    y_offset: int,
) -> None:
    """Отрисовка баз со смещением по Y."""
    lane_length = lane.length

    # Используем bases_list для многолинейной карты, иначе bases для обратной совместимости
    bases_to_render = state.bases_list if state.bases_list else list(state.bases.values())
    
    for base in bases_to_render:
        if base.lane_id != lane.id:
            continue
        if not base.alive:
            continue
        team_num = int(base.team_id)
        ch = TEAM_BASE_CHARS.get(team_num, "H")
        x, y = lane_position_to_xy(lane_index, base.position, lane_length, config, lanes_count, y_offset)
        if 0 <= y < buffer.height:
            buffer.put(x, y, ch)


def _render_buildings_on_lane_curved(
    buffer: ScreenBuffer,
    state: GameState,
    lane: Lane,
    lane_index: int,
    lanes_count: int,
    config: RenderConfig,
) -> None:
    """Отрисовка зданий без смещения (для обратной совместимости)."""
    _render_buildings_on_lane_curved_with_offset(buffer, state, lane, lane_index, lanes_count, config, 0)


def _render_buildings_on_lane_curved_with_offset(
    buffer: ScreenBuffer,
    state: GameState,
    lane: Lane,
    lane_index: int,
    lanes_count: int,
    config: RenderConfig,
    y_offset: int,
) -> None:
    """Отрисовывает здания на линии с разными символами и вертикальным смещением."""
    lane_length = lane.length
    
    # Группируем здания по командам и позициям для правильного размещения
    buildings_team1: List[Tuple[Building, int, int, str]] = []
    buildings_team2: List[Tuple[Building, int, int, str]] = []
    
    # Группируем здания по командам и позициям для правильного размещения
    # Используем более точное определение "одной позиции" - округляем position до ближайшего целого
    buildings_by_position: Dict[Tuple[int, int, int], List[Tuple[Building, str]]] = {}
    
    for building_id in lane.building_ids:
        building: Optional[Building] = state.buildings.get(building_id)
        if building is None:
            continue
        
        # Определяем символ по типу здания
        # Супер-здания (level > 1) отображаются заглавной буквой
        base_char = BUILDING_TYPE_CHAR.get(building.template_id, BUILDING_CHAR)
        building_char = base_char.upper() if building.level > 1 else base_char
        
        # Округляем позицию здания для группировки (здания в пределах 2 единиц считаются на одной позиции)
        position_rounded = int(round(building.position / 2.0)) * 2
        team_id_int = int(building.team_id)
        
        key = (position_rounded, lane_index, team_id_int)
        if key not in buildings_by_position:
            buildings_by_position[key] = []
        buildings_by_position[key].append((building, building_char))
    
    # Теперь размещаем здания с учетом их группировки
    for (position_rounded, _, team_id_int), buildings_list in buildings_by_position.items():
        for idx, (building, building_char) in enumerate(buildings_list):
            # Вычисляем позицию дороги для этого здания
            x_road, y_road = lane_position_to_xy(lane_index, building.position, lane_length, config, lanes_count, y_offset)
            
            # Определяем базовую Y координату для здания
            if team_id_int == 1:
                base_y = y_road - 1
            else:
                base_y = y_road + 1
            
            # Смещаем здания по X, если их несколько на одной позиции
            # Первое здание на позиции x_road, остальные смещаем вправо
            x_final = x_road + idx
            
            # Ограничиваем координаты
            x_final = max(0, min(config.width - 1, x_final))
            base_y = max(0, min(buffer.height - 1, base_y))
            
            if team_id_int == 1:
                buildings_team1.append((building, x_final, base_y, building_char))
            else:
                buildings_team2.append((building, x_final, base_y, building_char))
    
    # Рисуем здания команды 1 (выше дороги)
    for building, x, y, ch in buildings_team1:
        if 0 <= y < buffer.height:
            # Цвет по команде (светлее баз)
            team_color = (150, 200, 255) if int(building.team_id) == 1 else (255, 200, 150)
            # Супер-здания (level > 1) отображаются с ярким цветом и символом *
            if building.level > 1:
                # Яркий цвет для супер-зданий
                super_color = (255, 255, 0) if int(building.team_id) == 1 else (255, 100, 0)  # Ярко-жёлтый или оранжевый
                buffer.put_colored(x, y, ch, super_color)
                # Добавляем символ * рядом для визуального отличия
                if x + 1 < config.width:
                    buffer.put_colored(x + 1, y, "*", super_color)
            else:
                buffer.put_colored(x, y, ch, team_color)
    
    # Рисуем здания команды 2 (ниже дороги)
    for building, x, y, ch in buildings_team2:
        if 0 <= y < buffer.height:
            team_color = (150, 200, 255) if int(building.team_id) == 1 else (255, 200, 150)
            # Супер-здания (level > 1) отображаются с ярким цветом и символом *
            if building.level > 1:
                # Яркий цвет для супер-зданий
                super_color = (255, 255, 0) if int(building.team_id) == 1 else (255, 100, 0)  # Ярко-жёлтый или оранжевый
                buffer.put_colored(x, y, ch, super_color)
                # Добавляем символ * рядом для визуального отличия
                if x + 1 < config.width:
                    buffer.put_colored(x + 1, y, "*", super_color)
            else:
                buffer.put_colored(x, y, ch, team_color)


def _render_units_on_lane_curved(
    buffer: ScreenBuffer,
    state: GameState,
    lane: Lane,
    lane_index: int,
    lanes_count: int,
    config: RenderConfig,
) -> None:
    """Отрисовка юнитов без смещения (для обратной совместимости)."""
    _render_units_on_lane_curved_with_offset(buffer, state, lane, lane_index, lanes_count, config, 0)


def _render_neutral_objects_on_lane_curved_with_offset(
    buffer: ScreenBuffer,
    state: GameState,
    lane: Lane,
    lane_index: int,
    lanes_count: int,
    config: RenderConfig,
    y_offset: int,
) -> None:
    """Отрисовка нейтральных объектов со смещением по Y."""
    from ascii_rts_castle.shared.models import NeutralObject
    
    lane_length = lane.length
    for obj in state.neutral_objects.values():
        if not obj.alive or obj.lane_id != lane.id:
            continue
        
        # Определяем символ и цвет по типу объекта
        if obj.object_type == "gold":
            obj_char = "$"
            color = (255, 215, 0)  # Золотой
        elif obj.object_type == "chest":
            obj_char = "C"
            color = (139, 69, 19)  # Коричневый
        elif obj.object_type == "monster":
            # Разные символы для разных типов монстров
            if obj.monster_type == "tank":
                obj_char = "T"
            elif obj.monster_type == "fast":
                obj_char = "F"
            elif obj.monster_type == "ranged":
                obj_char = "R"
            else:
                obj_char = "X"
            
            # Цвет по HP монстра (тускнеет при потере HP)
            hp_ratio = obj.hp / obj.max_hp if obj.max_hp > 0 else 1.0
            base_color = (128, 0, 128)  # Базовый фиолетовый
            # Применяем тусклость в зависимости от HP
            brightness = int(128 + (hp_ratio * 127))  # От 128 до 255
            color = (brightness, 0, brightness)
        else:
            continue
        
        x, y = lane_position_to_xy(lane_index, obj.position, lane_length, config, lanes_count, y_offset)
        if 0 <= y < buffer.height:
            buffer.put_colored(x, y, obj_char, color)


def _render_units_on_lane_curved_with_offset(
    buffer: ScreenBuffer,
    state: GameState,
    lane: Lane,
    lane_index: int,
    lanes_count: int,
    config: RenderConfig,
    y_offset: int,
) -> None:
    """Отрисовка юнитов со смещением по Y."""
    lane_length = lane.length
    for unit_id in lane.unit_ids:
        unit: Optional[Unit] = state.units.get(unit_id)
        if unit is None or not unit.alive:
            continue
        
        # Определяем символ по типу юнита
        unit_char = UNIT_TYPE_CHAR.get(unit.template_id, TEAM_UNIT_CHARS.get(int(unit.team_id), "?"))
        
        # Вычисляем цвет команды с тусклостью в зависимости от HP
        hp_ratio = unit.hp / unit.max_hp if unit.max_hp > 0 else 1.0
        team_id_int = int(unit.team_id)
        
        # Базовые цвета команд (яркие)
        team_base_colors = {
            1: (100, 200, 255),  # Голубой для команды 1
            2: (255, 150, 100),  # Оранжевый для команды 2
            3: (150, 150, 255),  # Синий для команды 3
            4: (255, 255, 100),  # Жёлтый для команды 4
        }
        
        base_color = team_base_colors.get(team_id_int, (200, 200, 200))
        
        # Применяем тусклость в зависимости от HP (от яркого к тусклому)
        # hp_ratio от 1.0 (яркий) до 0.0 (очень тусклый)
        brightness_multiplier = 0.3 + (hp_ratio * 0.7)  # От 0.3 до 1.0
        color = tuple(int(c * brightness_multiplier) for c in base_color)
        
        x, y = lane_position_to_xy(lane_index, unit.position, lane_length, config, lanes_count, y_offset)
        if 0 <= y < buffer.height:
            buffer.put_colored(x, y, unit_char, color)


def _render_visual_effects_on_lane_curved_with_offset(
    buffer: ScreenBuffer,
    state: GameState,
    lane: Lane,
    lane_index: int,
    lanes_count: int,
    config: RenderConfig,
    y_offset: int,
) -> None:
    """Отрисовка визуальных эффектов способностей со смещением по Y."""
    from ascii_rts_castle.shared.models import VisualEffect
    
    lane_length = lane.length
    
    for effect in state.visual_effects:
        if effect.lane_id != lane.id:
            continue
        
        if effect.remaining_time <= 0:
            continue
        
        x, y = lane_position_to_xy(lane_index, effect.position, lane_length, config, lanes_count, y_offset)
        if not (0 <= y < buffer.height and 0 <= x < config.width):
            continue
        
        # Разные визуальные эффекты для разных способностей
        if effect.effect_type == "lightning":
            # Молния: яркие символы молнии
            lightning_chars = ["!", "|", "⚡"]
            char_idx = int((effect.duration - effect.remaining_time) * 10) % len(lightning_chars)
            color = (255, 255, 100)  # Ярко-жёлтый
            buffer.put_colored(x, y, lightning_chars[char_idx], color)
            # Также рисуем вокруг для эффекта вспышки
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < config.width and 0 <= ny < buffer.height:
                    dim_color = tuple(int(c * 0.5) for c in color)
                    buffer.put_colored(nx, ny, "*", dim_color)
        
        elif effect.effect_type == "shield":
            # Щит: пульсирующий символ щита вокруг базы
            shield_chars = ["◉", "○", "◯"]
            char_idx = int((effect.duration - effect.remaining_time) * 3) % len(shield_chars)
            team_id_int = int(effect.team_id)
            shield_colors = {
                1: (100, 200, 255),  # Голубой
                2: (255, 150, 100),  # Оранжевый
                3: (150, 150, 255),  # Синий
                4: (255, 255, 100),  # Жёлтый
            }
            base_color = shield_colors.get(team_id_int, (200, 200, 200))
            # Пульсация яркости
            pulse = 0.7 + 0.3 * abs((effect.remaining_time / effect.duration) - 0.5) * 2
            color = tuple(int(c * pulse) for c in base_color)
            buffer.put_colored(x, y, shield_chars[char_idx], color)
        
        elif effect.effect_type == "summon":
            # Вызов: символы появления
            summon_chars = ["+", "✚", "✛"]
            char_idx = int((effect.duration - effect.remaining_time) * 5) % len(summon_chars)
            team_id_int = int(effect.team_id)
            summon_colors = {
                1: (100, 255, 100),  # Зелёный
                2: (255, 100, 100),  # Красный
                3: (100, 100, 255),  # Синий
                4: (255, 255, 100),  # Жёлтый
            }
            color = summon_colors.get(team_id_int, (200, 200, 200))
            buffer.put_colored(x, y, summon_chars[char_idx], color)
        
        elif effect.effect_type == "heal":
            # Лечение: символы восстановления
            heal_chars = ["♥", "♡", "+"]
            char_idx = int((effect.duration - effect.remaining_time) * 4) % len(heal_chars)
            color = (100, 255, 100)  # Зелёный для лечения
            buffer.put_colored(x, y, heal_chars[char_idx], color)


def _render_event_log(
    buffer: ScreenBuffer,
    config: RenderConfig,
    lanes_count: int,
    event_lines: List[str],
) -> None:
    """Отрисовка лога событий без смещения (для обратной совместимости)."""
    _render_event_log_with_offset(buffer, config, lanes_count, event_lines, 0)


def _render_event_log_with_offset(
    buffer: ScreenBuffer,
    config: RenderConfig,
    lanes_count: int,
    event_lines: List[str],
    y_offset: int,
) -> None:
    """Отрисовать лог событий внизу экрана со смещением."""
    if not config.show_event_log or config.log_height <= 0:
        return

    base_y = y_offset + config.hud_height + lanes_count * config.lane_height
    # Берём только последние log_height событий
    visible_events = event_lines[-config.log_height :]
    # Рисуем снизу вверх: последнее событие внизу
    start_index = max(0, config.log_height - len(visible_events))
    for i, text in enumerate(visible_events):
        y = base_y + start_index + i
        if y >= buffer.height - config.action_bar_height:
            break
        if 0 <= y < buffer.height:
            line = text[: config.width]
            buffer.put_text(0, y, line)


def _render_action_bar(
    buffer: ScreenBuffer,
    config: RenderConfig,
    lanes_count: int,
    game_config: Optional[GameConfig],
    view_player_id: Optional[PlayerId],
    state: GameState,
    selected_lane_index: int = 0,
) -> None:
    """Отрисовывает панель действий внизу экрана."""
    if game_config is None:
        game_config = create_default_game_config()
    
    action_y = buffer.height - config.action_bar_height
    
    # Получаем информацию об активных исследованиях
    player = state.players.get(view_player_id) if view_player_id else None
    active_upgrades_dict: Dict[str, float] = {}
    if player:
        for upgrade_id, active_upgrade in player.active_upgrades.items():
            active_upgrades_dict[upgrade_id] = active_upgrade.remaining_time
    
    # Строка 1: Здания с реальной стоимостью (с учётом прогрессии)
    building_slots = []
    building_templates_list = list(game_config.building_templates.values())[:5]  # Первые 5 зданий (включая Gold Mine)
    
    # Получаем выбранную линию для расчёта стоимости
    sorted_lane_ids = sorted(state.lanes.keys(), key=int)
    selected_lane_id = sorted_lane_ids[selected_lane_index] if selected_lane_index < len(sorted_lane_ids) else None
    selected_lane = state.lanes.get(selected_lane_id) if selected_lane_id else None
    
    for i, template in enumerate(building_templates_list):
        key = str(i + 1)
        # Вычисляем реальную стоимость с учётом прогрессии
        actual_cost = template.cost
        if player and selected_lane:
            # Подсчитываем количество зданий того же типа на выбранной линии
            same_type_count = 0
            for bid in selected_lane.building_ids:
                if bid in state.buildings:
                    b = state.buildings[bid]
                    if (b.owner_player_id == view_player_id 
                        and b.template_id == template.id
                        and b.level == 1):  # Только обычные здания, не супер
                        same_type_count += 1
            
            # Прогрессивная стоимость: каждое следующее здание дороже на 50%
            cost_multiplier = 1.0 + (same_type_count * 0.5)
            actual_cost = int(template.cost * cost_multiplier)
        
        building_slots.append(f"[{key}] {template.name[:8]}({actual_cost})")
    
    buffer.put_text(0, action_y, " ".join(building_slots)[: config.width])
    
    # Строка 2: Апгрейды с прогрессом исследований
    upgrade_slots = []
    upgrade_templates_list = list(game_config.upgrade_templates.values())[:4]  # Первые 4 апгрейда
    keys = ["Q", "W", "E", "R"]
    for i, template in enumerate(upgrade_templates_list):
        if i < len(keys):
            key = keys[i]
            # Проверяем статус апгрейда
            current_level = player.upgrades.get(template.id, 0) if player else 0
            remaining_time = active_upgrades_dict.get(template.id, 0.0)
            
            if current_level >= template.max_level:
                status = "(max)"
            elif remaining_time > 0:
                status = f"(R:{remaining_time:.1f}s)"
            elif player and player.gold < template.cost:
                status = "(no gold)"
            else:
                status = ""
            
            upgrade_slots.append(f"[{key}] {template.name[:10]}({template.cost}){status}")
    
    buffer.put_text(0, action_y + 1, " ".join(upgrade_slots)[: config.width])
    
    # Строка 3: Способности базы
    ability_slots = []
    if game_config and game_config.base_ability_templates:
        ability_templates_list = list(game_config.base_ability_templates.values())[:4]  # Первые 4 способности
        keys = ["Z", "X", "C", "V"]
        
        # Находим базу игрока на выбранной линии
        sorted_lane_ids = sorted(state.lanes.keys(), key=int)
        selected_lane_id = sorted_lane_ids[selected_lane_index] if selected_lane_index < len(sorted_lane_ids) else None
        base = None
        if player and selected_lane_id:
            for b in state.bases_list:
                if b.team_id == player.team_id and b.lane_id == selected_lane_id and b.alive:
                    base = b
                    break
        
        for i, template in enumerate(ability_templates_list):
            if i < len(keys):
                key = keys[i]
                # Проверяем кулдаун способности
                cooldown_attr = f"{template.id}_cooldown_remaining"
                remaining_cooldown = getattr(base, cooldown_attr, 0.0) if base else 0.0
                
                if remaining_cooldown > 0:
                    status = f"(CD:{remaining_cooldown:.1f}s)"
                elif player and player.gold < template.cost:
                    status = "(no gold)"
                else:
                    status = ""
                
                # Проверяем активный щит
                if template.id == "shield" and base and base.shield_active:
                    status = f"(ACTIVE:{base.shield_duration_remaining:.1f}s)"
                
                ability_slots.append(f"[{key}] {template.name[:8]}({int(template.cost)}){status}")
        
        buffer.put_text(0, action_y + 2, " ".join(ability_slots)[: config.width])
    else:
        buffer.put_text(0, action_y + 2, "[H] Help | [ESC/q] Quit"[: config.width])


def _render_help_screen(config: RenderConfig, game_config: Optional[GameConfig]) -> ScreenBuffer:
    """Отрисовывает полноэкранный экран подсказки."""
    if game_config is None:
        game_config = create_default_game_config()
    
    height = 30
    buffer = ScreenBuffer(width=config.width, height=height)
    buffer.clear(" ")
    
    y = 0
    buffer.put_text(0, y, "=" * config.width)
    y += 1
    buffer.put_text(0, y, "ASCII RTS CASTLE - HELP".center(config.width))
    y += 1
    buffer.put_text(0, y, "=" * config.width)
    y += 2
    
    # Управление
    buffer.put_text(0, y, "УПРАВЛЕНИЕ:")
    y += 1
    buffer.put_text(2, y, "Up/Down - выбор линии")
    y += 1
    buffer.put_text(2, y, "1-5 - построить здание (см. панель действий)")
    y += 1
    buffer.put_text(2, y, "Q/W/E/R - исследовать апгрейд (см. панель действий)")
    y += 1
    buffer.put_text(2, y, "Z/X/C/V - активировать способность базы (см. панель действий)")
    y += 1
    buffer.put_text(2, y, "H - показать/скрыть эту подсказку")
    y += 1
    buffer.put_text(2, y, "ESC или q - выход из игры")
    y += 2
    
    # Здания
    buffer.put_text(0, y, "ЗДАНИЯ:")
    y += 1
    for i, template in enumerate(list(game_config.building_templates.values())[:5]):
        key = str(i + 1)
        buffer.put_text(2, y, f"[{key}] {template.name} - {template.cost} золота")
        if template.unit_template_id:
            buffer.put_text(20, y, f"(спавнит: {template.unit_template_id})")
        elif template.income_bonus_per_sec > 0:
            buffer.put_text(20, y, f"(доход: +{template.income_bonus_per_sec:.1f}/сек)")
        y += 1
    y += 1
    
    # Апгрейды
    buffer.put_text(0, y, "АПГРЕЙДЫ:")
    y += 1
    keys = ["Q", "W", "E", "R"]
    for i, template in enumerate(list(game_config.upgrade_templates.values())[:4]):
        if i < len(keys):
            key = keys[i]
            buffer.put_text(2, y, f"[{key}] {template.name} - {template.cost} золота")
            buffer.put_text(30, y, f"({template.description})")
        y += 1
    y += 1
    
    # Способности базы
    if game_config.base_ability_templates:
        buffer.put_text(0, y, "СПОСОБНОСТИ БАЗЫ:")
        y += 1
        keys = ["Z", "X", "C", "V"]
        for i, template in enumerate(list(game_config.base_ability_templates.values())[:4]):
            if i < len(keys):
                key = keys[i]
                buffer.put_text(2, y, f"[{key}] {template.name} - {int(template.cost)} золота")
                buffer.put_text(30, y, f"({template.description})")
            y += 1
        y += 1
    
    buffer.put_text(0, y, "=" * config.width)
    y += 1
    buffer.put_text(0, y, "Нажмите H для возврата к игре".center(config.width))
    
    return buffer
