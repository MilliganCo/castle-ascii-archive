"""
GUI-окно для ASCII-рендера через pygame.

Окно отображает ScreenBuffer как моноширинный текст и обрабатывает ввод команд.
"""

from __future__ import annotations

import pygame
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple

from ascii_rts_castle.client.ui_ascii import ScreenBuffer, RenderConfig


@dataclass
class WindowConfig:
    """Конфигурация окна."""

    cols: int = 240  # Увеличено (было 200)
    rows: int = 60  # Увеличено (было 50)
    font_size: int = 11  # Немного уменьшен для поддержки 240 колонок
    title: str = "ASCII RTS Castle"


class ActionType(Enum):
    """Тип действия от пользователя."""
    BUILD = "build"
    UPGRADE = "upgrade"
    BASE_ABILITY = "base_ability"
    LANE_UP = "lane_up"
    LANE_DOWN = "lane_down"
    HELP = "help"
    QUIT = "quit"
    TEXT_INPUT = "text_input"


@dataclass
class UserAction:
    """Действие пользователя."""
    action_type: ActionType
    value: Optional[str] = None  # building_id или upgrade_id для BUILD/UPGRADE
    text: Optional[str] = None  # для TEXT_INPUT


class AsciiWindow:
    """Окно для отображения ASCII-рендера и обработки ввода."""

    def __init__(self, cfg: WindowConfig) -> None:
        pygame.init()
        self.cfg = cfg

        # Попытка использовать системный моноширинный шрифт
        try:
            self.font = pygame.font.SysFont("Consolas", cfg.font_size)
        except Exception:
            try:
                self.font = pygame.font.SysFont("Courier New", cfg.font_size)
            except Exception:
                # Fallback на системный моноширинный
                self.font = pygame.font.SysFont("monospace", cfg.font_size)

        # Размер одной ячейки по пикселям
        sample = self.font.render("W", True, (255, 255, 255))
        self.cell_w = sample.get_width()
        self.cell_h = sample.get_height()

        self.width_px = self.cell_w * cfg.cols
        self.height_px = self.cell_h * cfg.rows

        self.screen = pygame.display.set_mode((self.width_px, self.height_px))
        pygame.display.set_caption(cfg.title)

        self.current_input: str = ""  # строка команд (fallback)
        self.running: bool = True
        self.render_config: Optional[RenderConfig] = None

    def close(self) -> None:
        """Закрыть окно и завершить pygame."""
        self.running = False
        pygame.quit()

    def poll_actions(self) -> List[UserAction]:
        """
        Обрабатывает события pygame и возвращает список действий пользователя.
        """
        actions: List[UserAction] = []

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                actions.append(UserAction(ActionType.QUIT))
            elif event.type == pygame.KEYDOWN:
                # Горячие клавиши для зданий (1-5)
                if pygame.K_1 <= event.key <= pygame.K_5:
                    slot = event.key - pygame.K_1
                    actions.append(UserAction(ActionType.BUILD, value=str(slot)))
                # Горячие клавиши для апгрейдов (Q, W, E, R)
                elif event.key == pygame.K_q:
                    actions.append(UserAction(ActionType.UPGRADE, value="0"))
                elif event.key == pygame.K_w:
                    actions.append(UserAction(ActionType.UPGRADE, value="1"))
                elif event.key == pygame.K_e:
                    actions.append(UserAction(ActionType.UPGRADE, value="2"))
                elif event.key == pygame.K_r:
                    actions.append(UserAction(ActionType.UPGRADE, value="3"))
                # Горячие клавиши для способностей базы (Z, X, C, V)
                elif event.key == pygame.K_z:
                    actions.append(UserAction(ActionType.BASE_ABILITY, value="0"))
                elif event.key == pygame.K_x:
                    actions.append(UserAction(ActionType.BASE_ABILITY, value="1"))
                elif event.key == pygame.K_c:
                    actions.append(UserAction(ActionType.BASE_ABILITY, value="2"))
                elif event.key == pygame.K_v:
                    actions.append(UserAction(ActionType.BASE_ABILITY, value="3"))
                # Выбор линии (Up/Down)
                elif event.key == pygame.K_UP:
                    actions.append(UserAction(ActionType.LANE_UP))
                elif event.key == pygame.K_DOWN:
                    actions.append(UserAction(ActionType.LANE_DOWN))
                # Help
                elif event.key == pygame.K_h:
                    actions.append(UserAction(ActionType.HELP))
                # Выход
                elif event.key == pygame.K_ESCAPE:
                    self.running = False
                    actions.append(UserAction(ActionType.QUIT))
                # Текстовый ввод (fallback)
                elif event.key == pygame.K_RETURN:
                    if self.current_input.strip():
                        actions.append(UserAction(ActionType.TEXT_INPUT, text=self.current_input))
                    self.current_input = ""
                elif event.key == pygame.K_BACKSPACE:
                    self.current_input = self.current_input[:-1]
                else:
                    # Печатные символы для текстового ввода
                    char = event.unicode
                    if char and char.isprintable() and char not in "12345qwerzxcv":
                        self.current_input += char
            elif event.type == pygame.MOUSEBUTTONDOWN:
                # Обработка кликов по панели действий
                if event.button == 1:  # Левая кнопка мыши
                    action = self._get_action_from_click(event.pos)
                    if action:
                        actions.append(action)

        return actions
    
    def _get_action_from_click(self, pos: Tuple[int, int]) -> Optional[UserAction]:
        """Определяет действие по координатам клика мыши."""
        if self.render_config is None:
            return None
        
        # Вычисляем координаты в символах
        click_x = pos[0] // self.cell_w
        click_y = pos[1] // self.cell_h
        
        # Панель действий находится внизу
        action_bar_y = self.cfg.rows - self.render_config.action_bar_height
        
        if click_y < action_bar_y:
            return None  # Клик не в панели действий
        
        # Строка 1 панели: здания [1] [2] [3] [4] [5]
        if click_y == action_bar_y:
            # Примерная позиция слотов (нужно будет уточнить)
            if 0 <= click_x < 20:
                return UserAction(ActionType.BUILD, value="0")
            elif 20 <= click_x < 40:
                return UserAction(ActionType.BUILD, value="1")
            elif 40 <= click_x < 60:
                return UserAction(ActionType.BUILD, value="2")
            elif 60 <= click_x < 80:
                return UserAction(ActionType.BUILD, value="3")
            elif 80 <= click_x < 100:
                return UserAction(ActionType.BUILD, value="4")
        # Строка 2 панели: апгрейды [Q] [W] [E] [R]
        elif click_y == action_bar_y + 1:
            if 0 <= click_x < 20:
                return UserAction(ActionType.UPGRADE, value="0")
            elif 20 <= click_x < 40:
                return UserAction(ActionType.UPGRADE, value="1")
            elif 40 <= click_x < 60:
                return UserAction(ActionType.UPGRADE, value="2")
            elif 60 <= click_x < 80:
                return UserAction(ActionType.UPGRADE, value="3")
        # Строка 3 панели: Способности базы [Z] [X] [C] [V] или Help
        elif click_y == action_bar_y + 2:
            # Способности занимают большую часть строки, Help в конце
            if self.render_config:
                config_width = self.render_config.width
            else:
                config_width = self.cfg.cols
            
            if 0 <= click_x < 20:
                return UserAction(ActionType.BASE_ABILITY, value="0")
            elif 20 <= click_x < 40:
                return UserAction(ActionType.BASE_ABILITY, value="1")
            elif 40 <= click_x < 60:
                return UserAction(ActionType.BASE_ABILITY, value="2")
            elif 60 <= click_x < 80:
                return UserAction(ActionType.BASE_ABILITY, value="3")
            elif click_x >= config_width - 20:  # Help в конце строки
                return UserAction(ActionType.HELP)
        
        return None
    
    def set_render_config(self, config: RenderConfig) -> None:
        """Устанавливает конфигурацию рендера для обработки кликов."""
        self.render_config = config

    def draw(self, buffer: ScreenBuffer) -> None:
        """Отрисовывает ScreenBuffer в окне с поддержкой цветов."""
        self.screen.fill((0, 0, 0))  # Чёрный фон

        # Отрисовка посимвольно для поддержки цветов
        for y in range(min(buffer.height, self.cfg.rows)):
            for x in range(min(buffer.width, self.cfg.cols)):
                cell = buffer.cells[y][x]
                ch = cell.ch
                color = cell.color if cell.color is not None else (200, 200, 200)
                
                # Рендерим символ с цветом
                surf = self.font.render(ch, True, color)
                self.screen.blit(surf, (x * self.cell_w, y * self.cell_h))

        pygame.display.flip()

