"""
Ядро игры (GameEngine) с детерминированной логикой.

Реализует основную игровую механику: движение юнитов, бой, спавн, ресурсы.
"""

from __future__ import annotations

import logging
from collections import deque
from typing import Deque, List, Optional, Tuple

from ascii_rts_castle.config import GameConfig, UpgradeEffect
from ascii_rts_castle.shared.commands import (
    ActivateBaseAbilityCommand,
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
    NeutralObject,
    NeutralObjectId,
    Player,
    PlayerId,
    TeamId,
    Unit,
    UnitId,
    VisualEffect,
)

logger = logging.getLogger(__name__)


class GameEngine:
    def __init__(self, config: GameConfig, players_team_mapping: dict[PlayerId, TeamId]) -> None:
        self.config = config
        self.state = GameState()
        self._pending_commands: List[GameCommand] = []
        self._events: Deque[str] = deque(maxlen=50)  # последние 50 событий

        self._init_players(players_team_mapping)
        self._init_lanes_and_bases()
        self._last_neutral_spawn_tick = 0  # Счётчик для спавна нейтральных объектов

    def enqueue_command(self, command: GameCommand) -> None:
        """Сложить команду в очередь для применения на следующем тике."""
        self._pending_commands.append(command)

    def _add_event(self, text: str) -> None:
        """Добавить событие в лог."""
        self._events.append(text)

    def consume_events(self) -> List[str]:
        """
        Забрать все накопленные события с прошлого вызова.
        """
        events = list(self._events)
        self._events.clear()
        return events

    def tick(self, dt: float) -> None:
        """Основной шаг симуляции."""
        if not self.state.running:
            return

        self._apply_pending_commands()
        self._update_upgrades(dt)
        self._update_spawning(dt)
        self._update_neutral_objects(dt)  # Обновляем нейтральные объекты
        self._update_units(dt)
        self._update_bases(dt)
        self._update_resources(dt)
        self._check_end_conditions()

        self.state.tick += 1
        self.state.time += dt

    def _init_players(self, players_team_mapping: dict[PlayerId, TeamId]) -> None:
        """Инициализировать игроков из маппинга."""
        for player_id, team_id in players_team_mapping.items():
            self.state.players[player_id] = Player(
                id=player_id,
                team_id=team_id,
                gold=float(self.config.starting_gold),
                income_per_sec=self.config.starting_income_per_sec,
            )

    def _init_lanes_and_bases(self) -> None:
        """Инициализировать линии и базы команд."""
        # Определяем команды из игроков
        teams: set[TeamId] = {player.team_id for player in self.state.players.values()}
        teams_list = sorted(teams)

        for lane_cfg in self.config.lanes:
            lane_id = LaneId(lane_cfg.id)
            lane = Lane(id=lane_id, length=lane_cfg.length)
            self.state.lanes[lane_id] = lane

            # Создаём базы для каждой команды на каждой линии
            for i, team_id in enumerate(teams_list):
                # База команды 1 в позиции 0.0, команды 2 в позиции length
                position = 0.0 if i == 0 else lane_cfg.length
                base = Base(
                    team_id=team_id,
                    lane_id=lane_id,
                    position=position,
                    hp=self.config.base_hp,
                    max_hp=self.config.base_hp,
                    alive=True,
                    attack_range=self.config.base_attack_range,
                    attack_damage=self.config.base_attack_damage,
                    attack_cooldown=self.config.base_attack_cooldown,
                    attack_cooldown_remaining=0.0,
                )
                # Добавляем в список всех баз
                self.state.bases_list.append(base)
                # Для обратной совместимости храним первую базу команды в словаре
                if team_id not in self.state.bases:
                    self.state.bases[team_id] = base

    def _apply_pending_commands(self) -> None:
        """Применить все команды из очереди."""
        for command in self._pending_commands:
            if isinstance(command, BuildCommand):
                self._handle_build_command(command)
            elif isinstance(command, UpgradeBuildingCommand):
                self._handle_upgrade_command(command)
            elif isinstance(command, ResearchUpgradeCommand):
                self._handle_research_upgrade_command(command)
            elif isinstance(command, ActivateBaseAbilityCommand):
                self._handle_activate_base_ability_command(command)

        self._pending_commands.clear()

    def _handle_build_command(self, command: BuildCommand) -> None:
        """Обработать команду строительства."""
        # Проверяем существование игрока и линии
        if command.player_id not in self.state.players:
            return
        if command.lane_id not in self.state.lanes:
            return

        player = self.state.players[command.player_id]
        lane = self.state.lanes[command.lane_id]

        # Проверяем существование шаблона здания
        if command.building_type_id not in self.config.building_templates:
            return

        template = self.config.building_templates[command.building_type_id]

        # Подсчитываем количество зданий того же типа на этой линии для прогрессивной стоимости
        same_type_count = 0
        for bid in lane.building_ids:
            if bid in self.state.buildings:
                b = self.state.buildings[bid]
                if (b.owner_player_id == command.player_id 
                    and b.template_id == command.building_type_id
                    and b.level == 1):  # Только обычные здания, не супер
                    same_type_count += 1
        
        # Прогрессивная стоимость: каждое следующее здание дороже на 50%
        cost_multiplier = 1.0 + (same_type_count * 0.5)
        actual_cost = int(template.cost * cost_multiplier)

        # Проверяем золото
        if player.gold < actual_cost:
            return

        # Списываем золото
        player.gold -= actual_cost

        # Определяем позицию здания
        # Для команды с базой на 0.0 строим в 0.1 * length
        # Для команды с базой на length строим в 0.9 * length
        # Ищем базу команды на текущей линии
        team_base = None
        for base in self.state.bases.values():
            if base.team_id == player.team_id and base.lane_id == command.lane_id:
                team_base = base
                break
        # Если базы на этой линии нет, используем первую найденную базу команды
        if team_base is None:
            for base in self.state.bases.values():
                if base.team_id == player.team_id:
                    team_base = base
                    break
        
        if team_base is None:
            return  # Нет базы для команды
        
        if team_base.position == 0.0:
            position = 0.1 * lane.length
        else:
            position = 0.9 * lane.length

        # Вычисляем spawn_interval с учётом апгрейдов
        base_spawn_interval = (
            template.spawn_interval if template.spawn_interval is not None else 0.0
        )
        effective_spawn_interval = base_spawn_interval

        if template.spawn_interval is not None:
            # Применяем апгрейды к spawn_interval
            building_upgrades = self._get_building_upgrades(player, command.building_type_id)
            for eff in building_upgrades:
                if eff.stat == "spawn_interval":
                    effective_spawn_interval = self._apply_effect(effective_spawn_interval, eff)

        # Проверяем, есть ли уже 3 одинаковых здания на этой линии
        same_buildings = []
        for bid in lane.building_ids:
            if bid in self.state.buildings:
                b = self.state.buildings[bid]
                if (b.owner_player_id == command.player_id 
                    and b.template_id == command.building_type_id
                    and b.level == 1):  # Только обычные здания, не супер
                    same_buildings.append(bid)
        
        # Если есть 3 одинаковых здания, превращаем их в супер-здание
        if len(same_buildings) >= 3:
            # Удаляем 3 здания
            for bid in same_buildings[:3]:
                if bid in self.state.buildings:
                    del self.state.buildings[bid]
                if bid in lane.building_ids:
                    lane.building_ids.remove(bid)
            
            # Создаём супер-здание (level 2)
            building_id = BuildingId(self.state.next_building_id)
            self.state.next_building_id += 1
            
            # Супер-здание спавнит медленнее, но юниты сильнее
            super_spawn_interval = effective_spawn_interval * 1.5  # Медленнее спавн
            
            building = Building(
                id=building_id,
                owner_player_id=command.player_id,
                team_id=player.team_id,
                lane_id=command.lane_id,
                position=position,
                template_id=command.building_type_id,
                level=2,  # Супер-здание
                spawn_interval=super_spawn_interval if template.spawn_interval is not None else 0.0,
                spawn_timer=super_spawn_interval if template.spawn_interval is not None else 0.0,
            )
            
            self.state.buildings[building_id] = building
            lane.building_ids.append(building_id)
            
            self._add_event(f"P{int(player.id)} merged 3 {template.name} into SUPER {template.name} on lane {int(lane.id)}")
        else:
            # Обычное строительство
            building_id = BuildingId(self.state.next_building_id)
            self.state.next_building_id += 1

            building = Building(
                id=building_id,
                owner_player_id=command.player_id,
                team_id=player.team_id,
                lane_id=command.lane_id,
                position=position,
                template_id=command.building_type_id,
                level=1,
                spawn_interval=effective_spawn_interval if template.spawn_interval is not None else 0.0,
                spawn_timer=effective_spawn_interval if template.spawn_interval is not None else 0.0,
            )

            self.state.buildings[building_id] = building
            lane.building_ids.append(building_id)

            # Событие о строительстве (показываем реальную стоимость, если она отличается)
            if actual_cost != template.cost:
                self._add_event(f"P{int(player.id)} built {template.name} on lane {int(lane.id)} (cost: {actual_cost})")
            else:
                self._add_event(f"P{int(player.id)} built {template.name} on lane {int(lane.id)}")

    def _handle_upgrade_command(self, command: UpgradeBuildingCommand) -> None:
        """Обработать команду апгрейда здания."""
        # На Этапе 1 просто увеличиваем level без реального эффекта
        if command.building_id not in self.state.buildings:
            return
        if command.player_id not in self.state.players:
            return

        building = self.state.buildings[command.building_id]
        if building.owner_player_id != command.player_id:
            return

        building.level += 1

    def _handle_research_upgrade_command(self, command: ResearchUpgradeCommand) -> None:
        """Обработать команду исследования апгрейда (с временем исследования)."""
        if command.player_id not in self.state.players:
            return
        if command.upgrade_id not in self.config.upgrade_templates:
            return

        player = self.state.players[command.player_id]
        template = self.config.upgrade_templates[command.upgrade_id]

        # Проверяем текущий уровень
        current_level = player.upgrades.get(command.upgrade_id, 0)
        if current_level >= template.max_level:
            return  # Уже на максимальном уровне

        # Проверяем, не исследуется ли уже этот апгрейд
        if command.upgrade_id in player.active_upgrades:
            return  # Уже в процессе исследования

        # Проверяем золото
        if player.gold < template.cost:
            return

        # Списываем золото
        player.gold -= template.cost

        # Вычисляем время исследования
        research_time = template.research_time_base + current_level * template.research_time_per_level

        # Создаём активное исследование
        from ascii_rts_castle.shared.models import ActiveUpgrade
        active_upgrade = ActiveUpgrade(
            upgrade_id=command.upgrade_id,
            remaining_time=research_time,
            target_level=current_level + 1,
        )
        player.active_upgrades[command.upgrade_id] = active_upgrade

        # Событие о начале исследования
        self._add_event(
            f"P{int(player.id)} started research {template.name} (lvl {current_level + 1}, {research_time:.1f}s)"
        )

    def _handle_activate_base_ability_command(self, command: ActivateBaseAbilityCommand) -> None:
        """Обработать команду активации способности базы."""
        if command.player_id not in self.state.players:
            return
        if command.lane_id not in self.state.lanes:
            return
        if command.ability_id not in self.config.base_ability_templates:
            return
        
        player = self.state.players[command.player_id]
        template = self.config.base_ability_templates[command.ability_id]
        
        # Находим базу игрока на указанной линии
        base = None
        for b in self.state.bases_list:
            if b.team_id == player.team_id and b.lane_id == command.lane_id and b.alive:
                base = b
                break
        
        if base is None:
            return  # База не найдена
        
        # Проверяем кулдаун способности
        cooldown_attr = f"{command.ability_id}_cooldown_remaining"
        if hasattr(base, cooldown_attr):
            current_cooldown = getattr(base, cooldown_attr)
            if current_cooldown > 0:
                return  # Способность на кулдауне
        
        # Проверяем золото
        if player.gold < template.cost:
            return
        
        # Списываем золото
        player.gold -= template.cost
        
        # Активируем способность
        if command.ability_id == "shield":
            base.shield_active = True
            base.shield_duration_remaining = template.shield_duration
            # Добавляем визуальный эффект щита
            effect = VisualEffect(
                effect_type="shield",
                lane_id=command.lane_id,
                position=base.position,
                team_id=player.team_id,
                duration=template.shield_duration,
                remaining_time=template.shield_duration,
            )
            self.state.visual_effects.append(effect)
            self._add_event(f"P{int(player.id)} activated Shield on lane {int(command.lane_id)}")
        
        elif command.ability_id == "lightning":
            # Наносим урон всем вражеским юнитам в радиусе на ВСЕХ линиях
            # Lightning работает на ближайшую территорию от своей базы по всем линиям
            hit_count = 0
            
            # Находим все базы игрока для определения области действия
            player_bases = [b for b in self.state.bases_list if b.team_id == player.team_id and b.alive]
            
            # Проверяем все линии
            for lane_id, lane in self.state.lanes.items():
                # Находим базу игрока на этой линии (или ближайшую)
                base_on_lane = None
                for b in player_bases:
                    if b.lane_id == lane_id:
                        base_on_lane = b
                        break
                
                # Если базы на этой линии нет, пропускаем (Lightning работает только от баз игрока)
                if base_on_lane is None:
                    continue
                
                for unit_id in lane.unit_ids:
                    if unit_id in self.state.units:
                        unit = self.state.units[unit_id]
                        if unit.alive and unit.team_id != player.team_id:
                            # Вычисляем расстояние от базы до юнита на этой линии
                            distance = abs(unit.position - base_on_lane.position)
                            
                            if distance <= template.lightning_range:
                                unit.hp -= template.lightning_damage
                                hit_count += 1
                                if unit.hp <= 0:
                                    unit.alive = False
                                # Добавляем визуальный эффект молнии на позицию юнита
                                effect = VisualEffect(
                                    effect_type="lightning",
                                    lane_id=lane_id,
                                    position=unit.position,
                                    team_id=player.team_id,
                                    duration=0.5,  # Короткий эффект молнии
                                    remaining_time=0.5,
                                )
                                self.state.visual_effects.append(effect)
            
            base.lightning_cooldown_remaining = template.cooldown
            self._add_event(f"P{int(player.id)} activated Lightning Strike on lane {int(command.lane_id)}, hit {hit_count} enemies")
        
        elif command.ability_id == "summon":
            # Вызываем юнитов у базы
            if template.summon_unit_type not in self.config.unit_templates:
                return
            
            unit_template = self.config.unit_templates[template.summon_unit_type]
            lane = self.state.lanes[command.lane_id]
            
            # Применяем апгрейды к статам юнита
            unit_upgrades = self._get_unit_upgrades(player, template.summon_unit_type)
            
            hp = unit_template.max_hp
            damage = unit_template.damage
            attack_range = unit_template.attack_range
            speed = unit_template.speed
            
            for eff in unit_upgrades:
                if eff.stat == "max_hp":
                    hp = self._apply_effect(hp, eff)
                elif eff.stat == "damage":
                    damage = self._apply_effect(damage, eff)
                elif eff.stat == "attack_range":
                    attack_range = self._apply_effect(attack_range, eff)
                elif eff.stat == "speed":
                    speed = self._apply_effect(speed, eff)
            
            # Спавним юнитов рядом с базой
            spawn_position = base.position + (1.0 if base.position == 0.0 else -1.0)
            for _ in range(template.summon_count):
                unit_id = UnitId(self.state.next_unit_id)
                self.state.next_unit_id += 1
                
                unit = Unit(
                    id=unit_id,
                    team_id=player.team_id,
                    lane_id=command.lane_id,
                    position=spawn_position,
                    max_hp=hp,
                    hp=hp,
                    damage=damage,
                    attack_range=attack_range,
                    attack_cooldown=unit_template.attack_cooldown,
                    attack_cooldown_remaining=0.0,
                    speed=speed,
                    state="moving",
                    alive=True,
                    template_id=unit_template.id,
                    vs_base_damage_multiplier=unit_template.vs_base_damage_multiplier,
                )
                
                self.state.units[unit_id] = unit
                lane.unit_ids.append(unit_id)
            
            # Добавляем визуальный эффект вызова
            effect = VisualEffect(
                effect_type="summon",
                lane_id=command.lane_id,
                position=spawn_position,
                team_id=player.team_id,
                duration=1.0,
                remaining_time=1.0,
            )
            self.state.visual_effects.append(effect)
            
            base.summon_cooldown_remaining = template.cooldown
            self._add_event(f"P{int(player.id)} summoned {template.summon_count} {template.summon_unit_type} on lane {int(command.lane_id)}")
        
        elif command.ability_id == "heal":
            # Лечим базу
            heal_amount = min(template.heal_amount, base.max_hp - base.hp)
            base.hp += heal_amount
            # Добавляем визуальный эффект лечения
            effect = VisualEffect(
                effect_type="heal",
                lane_id=command.lane_id,
                position=base.position,
                team_id=player.team_id,
                duration=1.0,
                remaining_time=1.0,
            )
            self.state.visual_effects.append(effect)
            base.heal_cooldown_remaining = template.cooldown
            self._add_event(f"P{int(player.id)} healed base on lane {int(command.lane_id)} for {heal_amount:.0f} HP")

    def _apply_effect(self, value: float, eff: UpgradeEffect) -> float:
        """Применить эффект апгрейда к значению."""
        if eff.op == "add":
            return value + eff.value
        elif eff.op == "mul":
            return value * eff.value
        return value

    def _get_unit_upgrades(self, player: Player, unit_template_id: str) -> List[UpgradeEffect]:
        """Получить все эффекты апгрейдов для юнита."""
        effects: List[UpgradeEffect] = []
        for upgrade_id, level in player.upgrades.items():
            if upgrade_id not in self.config.upgrade_templates:
                continue
            upgrade_template = self.config.upgrade_templates[upgrade_id]
            if (
                upgrade_template.target_type == "unit"
                and upgrade_template.target_id == unit_template_id
            ):
                # Применяем эффект level раз (для будущих многоуровневых апгрейдов)
                for _ in range(level):
                    effects.extend(upgrade_template.effects)
        return effects

    def _get_building_upgrades(
        self, player: Player, building_template_id: str
    ) -> List[UpgradeEffect]:
        """Получить все эффекты апгрейдов для здания."""
        effects: List[UpgradeEffect] = []
        for upgrade_id, level in player.upgrades.items():
            if upgrade_id not in self.config.upgrade_templates:
                continue
            upgrade_template = self.config.upgrade_templates[upgrade_id]
            if (
                upgrade_template.target_type == "building"
                and upgrade_template.target_id == building_template_id
            ):
                # Применяем эффект level раз
                for _ in range(level):
                    effects.extend(upgrade_template.effects)
        return effects

    def _update_spawning(self, dt: float) -> None:
        """Обновить спавн юнитов из зданий."""
        for building in list(self.state.buildings.values()):
            # Пропускаем здания без спавна
            if building.spawn_interval <= 0:
                continue

            building.spawn_timer -= dt

            if building.spawn_timer <= 0:
                # Получаем шаблон здания
                if building.template_id not in self.config.building_templates:
                    continue

                building_template = self.config.building_templates[building.template_id]

                # Пропускаем здания без спавна юнитов
                if building_template.unit_template_id is None:
                    continue

                # Находим шаблон юнита
                if building_template.unit_template_id not in self.config.unit_templates:
                    continue

                unit_template = self.config.unit_templates[building_template.unit_template_id]

                # Получаем игрока для применения апгрейдов
                player = self.state.players.get(building.owner_player_id)
                if player is None:
                    continue

                # Применяем апгрейды к статам юнита
                unit_upgrades = self._get_unit_upgrades(player, building_template.unit_template_id)

                hp = unit_template.max_hp
                damage = unit_template.damage
                attack_range = unit_template.attack_range
                speed = unit_template.speed

                # Если это супер-здание (level > 1), юниты сильнее, но медленнее
                if building.level > 1:
                    hp *= 2.0  # В 2 раза больше HP
                    damage *= 1.8  # На 80% больше урона
                    speed *= 0.6  # На 40% медленнее

                for eff in unit_upgrades:
                    if eff.stat == "max_hp":
                        hp = self._apply_effect(hp, eff)
                    elif eff.stat == "damage":
                        damage = self._apply_effect(damage, eff)
                    elif eff.stat == "attack_range":
                        attack_range = self._apply_effect(attack_range, eff)
                    elif eff.stat == "speed":
                        speed = self._apply_effect(speed, eff)

                # Создаём юнита с модифицированными статами
                unit_id = UnitId(self.state.next_unit_id)
                self.state.next_unit_id += 1

                unit = Unit(
                    id=unit_id,
                    team_id=building.team_id,
                    lane_id=building.lane_id,
                    position=building.position,
                    max_hp=hp,
                    hp=hp,
                    damage=damage,
                    attack_range=attack_range,
                    attack_cooldown=unit_template.attack_cooldown,
                    attack_cooldown_remaining=0.0,
                    speed=speed,
                    state="moving",
                    alive=True,
                    template_id=unit_template.id,
                    vs_base_damage_multiplier=unit_template.vs_base_damage_multiplier,
                )

                self.state.units[unit_id] = unit
                lane = self.state.lanes[building.lane_id]
                lane.unit_ids.append(unit_id)

                # Сбрасываем таймер
                building.spawn_timer = building.spawn_interval

    def _update_units(self, dt: float) -> None:
        """Обновить состояние всех юнитов: движение, атака, смерть."""
        for unit in list(self.state.units.values()):
            if not unit.alive:
                continue

            # Уменьшаем кулдаун атаки
            unit.attack_cooldown_remaining = max(0.0, unit.attack_cooldown_remaining - dt)

            # Ищем цель
            target_info = self._find_target_for_unit(unit)
            lane = self.state.lanes[unit.lane_id]

            if target_info is not None:
                target_type, target = target_info
                distance = abs(unit.position - target.position)

                if distance <= unit.attack_range:
                    # Атакуем цель
                    unit.state = "attacking"

                    if unit.attack_cooldown_remaining <= 0:
                        # Наносим урон
                        if target_type == "base":
                            # По базам используем множитель
                            damage_dealt = unit.damage * unit.vs_base_damage_multiplier
                            # Применяем защиту щита, если активен
                            if target.shield_active:
                                damage_dealt *= (1.0 - target.shield_damage_reduction)
                            target.hp -= damage_dealt
                        else:
                            # По юнитам обычный урон
                            target.hp -= unit.damage
                        unit.attack_cooldown_remaining = unit.attack_cooldown

                        # Проверяем смерть цели
                        if target.hp <= 0:
                            if target_type == "unit":
                                target.alive = False
                            elif target_type == "base":
                                if target.alive:  # переход к смерти
                                    target.alive = False
                                    self._add_event(
                                        f"Base of Team {int(target.team_id)} was destroyed"
                                    )
                else:
                    # Двигаемся к цели
                    unit.state = "moving"
                    direction = self._get_unit_direction(unit, lane)
                    unit.position += direction * unit.speed * dt
                    unit.position = max(0.0, min(unit.position, lane.length))
            else:
                # Нет цели, двигаемся к вражеской базе
                unit.state = "moving"
                direction = self._get_unit_direction(unit, lane)
                unit.position += direction * unit.speed * dt
                unit.position = max(0.0, min(unit.position, lane.length))

        # Удаляем мёртвые юниты
        self._cleanup_dead_units()

    def _find_target_for_unit(self, unit: Unit) -> Optional[Tuple[str, Unit | Base]]:
        """
        Найти ближайшую вражескую цель для юнита.
        
        В центральной зоне юниты с разных линий могут сражаться друг с другом.

        Возвращает ('unit', target_unit) или ('base', target_base) или None.
        """
        lane = self.state.lanes[unit.lane_id]
        lane_length = lane.length
        
        # Вычисляем границы центральной зоны
        center_start = self.config.center_start_ratio * lane_length
        center_end = self.config.center_end_ratio * lane_length
        
        # Проверяем, находится ли юнит в центральной зоне
        in_center = center_start <= unit.position <= center_end
        
        enemy_units: List[Unit] = []
        enemy_base: Optional[Base] = None

        if in_center:
            # В центральной зоне: ищем врагов на всех линиях, но только тех, кто тоже в центре
            for other_lane in self.state.lanes.values():
                for unit_id in other_lane.unit_ids:
                    if unit_id in self.state.units:
                        other_unit = self.state.units[unit_id]
                        if (other_unit.alive 
                            and other_unit.team_id != unit.team_id
                            and center_start <= other_unit.position <= center_end):
                            enemy_units.append(other_unit)
        else:
            # Вне центра: ищем врагов только на своей линии
            for unit_id in lane.unit_ids:
                if unit_id in self.state.units:
                    other_unit = self.state.units[unit_id]
                    if other_unit.alive and other_unit.team_id != unit.team_id:
                        enemy_units.append(other_unit)

        # Ищем вражескую базу в этой линии (используем bases_list для многолинейной карты)
        bases_to_check = self.state.bases_list if self.state.bases_list else list(self.state.bases.values())
        for base in bases_to_check:
            if base.lane_id == unit.lane_id and base.team_id != unit.team_id and base.alive:
                enemy_base = base
                break

        # Выбираем ближайшую цель
        best_target: Optional[Tuple[str, Unit | Base, float]] = None

        for enemy_unit in enemy_units:
            distance = abs(unit.position - enemy_unit.position)
            if best_target is None or distance < best_target[2]:
                best_target = ("unit", enemy_unit, distance)

        if enemy_base is not None:
            distance = abs(unit.position - enemy_base.position)
            if best_target is None or distance < best_target[2]:
                best_target = ("base", enemy_base, distance)

        if best_target is None:
            return None

        return (best_target[0], best_target[1])

    def _get_unit_direction(self, unit: Unit, lane: Lane) -> float:
        """Определить направление движения юнита (1.0 или -1.0)."""
        # Ищем базу команды на текущей линии юнита
        team_base = None
        for base in self.state.bases_list:
            if base.team_id == unit.team_id and base.lane_id == unit.lane_id:
                team_base = base
                break
        # Если базы на этой линии нет, используем первую найденную базу команды
        if team_base is None:
            for base in self.state.bases_list:
                if base.team_id == unit.team_id:
                    team_base = base
                    break
        
        if team_base is None:
            return 1.0  # По умолчанию движемся вперёд
        
        if team_base.position == 0.0:
            # База на старте, движемся вперёд (увеличиваем position)
            return 1.0
        else:
            # База в конце, движемся назад (уменьшаем position)
            return -1.0

    def _cleanup_dead_units(self) -> None:
        """Удалить мёртвые юниты из состояния."""
        dead_unit_ids: List[UnitId] = []

        for unit_id, unit in self.state.units.items():
            if not unit.alive:
                dead_unit_ids.append(unit_id)
                # Удаляем из линии
                lane = self.state.lanes[unit.lane_id]
                if unit_id in lane.unit_ids:
                    lane.unit_ids.remove(unit_id)

        for unit_id in dead_unit_ids:
            del self.state.units[unit_id]

    def _update_resources(self, dt: float) -> None:
        """Обновить ресурсы игроков."""
        for player in self.state.players.values():
            # Базовый доход
            base_income = player.income_per_sec

            # Бонус от экономических зданий
            building_bonus = 0.0
            for building in self.state.buildings.values():
                if building.owner_player_id == player.id:
                    if building.template_id in self.config.building_templates:
                        building_template = self.config.building_templates[building.template_id]
                        if building_template.income_bonus_per_sec > 0:
                            building_bonus += building_template.income_bonus_per_sec

            # Итоговый доход
            total_income = base_income + building_bonus
            player.gold += total_income * dt

    def _update_bases(self, dt: float) -> None:
        """Обновить атаку баз по юнитам."""
        for base in self.state.bases_list:
            if not base.alive:
                continue
            
            # Уменьшаем кулдаун атаки
            base.attack_cooldown_remaining = max(0.0, base.attack_cooldown_remaining - dt)
            
            # Ищем ближайшего вражеского юнита на той же линии
            lane = self.state.lanes.get(base.lane_id)
            if lane is None:
                continue
            
            closest_enemy: Optional[Unit] = None
            closest_distance: float = float('inf')
            
            for unit_id in lane.unit_ids:
                if unit_id not in self.state.units:
                    continue
                unit = self.state.units[unit_id]
                if not unit.alive or unit.team_id == base.team_id:
                    continue
                
                distance = abs(unit.position - base.position)
                if distance <= base.attack_range and distance < closest_distance:
                    closest_enemy = unit
                    closest_distance = distance
            
            # Атакуем, если цель найдена и кулдаун готов
            if closest_enemy is not None and base.attack_cooldown_remaining <= 0:
                closest_enemy.hp -= base.attack_damage
                base.attack_cooldown_remaining = base.attack_cooldown
                
                # Событие только при убийстве
                if closest_enemy.hp <= 0:
                    closest_enemy.alive = False
                    self._add_event(
                        f"Base of Team {int(base.team_id)} killed enemy unit on lane {int(base.lane_id)}"
                    )
            
            # Обновляем способности базы
            # Уменьшаем кулдауны способностей
            base.lightning_cooldown_remaining = max(0.0, base.lightning_cooldown_remaining - dt)
            base.summon_cooldown_remaining = max(0.0, base.summon_cooldown_remaining - dt)
            base.heal_cooldown_remaining = max(0.0, base.heal_cooldown_remaining - dt)
            
            # Обновляем щит
            if base.shield_active:
                base.shield_duration_remaining = max(0.0, base.shield_duration_remaining - dt)
                if base.shield_duration_remaining <= 0:
                    base.shield_active = False
                    self._add_event(f"Shield on base Team {int(base.team_id)} lane {int(base.lane_id)} expired")
            
            # Применяем снижение урона от щита при получении урона (обрабатывается в _update_units при атаке базы)

    def _update_upgrades(self, dt: float) -> None:
        """Обновить прогресс исследований апгрейдов."""
        for player in self.state.players.values():
            completed_upgrades: List[str] = []
            
            for upgrade_id, active_upgrade in player.active_upgrades.items():
                active_upgrade.remaining_time -= dt
                
                if active_upgrade.remaining_time <= 0:
                    # Исследование завершено
                    template = self.config.upgrade_templates.get(upgrade_id)
                    if template is None:
                        completed_upgrades.append(upgrade_id)
                        continue
                    
                    # Увеличиваем уровень
                    player.upgrades[upgrade_id] = active_upgrade.target_level
                    
                    # Применяем эффекты для player-wide апгрейдов
                    if template.target_type == "player":
                        for eff in template.effects:
                            if eff.stat == "income_per_sec":
                                if eff.op == "add":
                                    player.income_per_sec += eff.value
                                elif eff.op == "mul":
                                    player.income_per_sec *= eff.value
                    
                    # Событие о завершении
                    self._add_event(
                        f"P{int(player.id)} completed research {template.name} (lvl {active_upgrade.target_level})"
                    )
                    
                    completed_upgrades.append(upgrade_id)
            
            # Удаляем завершённые исследования
            for upgrade_id in completed_upgrades:
                del player.active_upgrades[upgrade_id]

    def _update_neutral_objects(self, dt: float) -> None:
        """Обновить нейтральные объекты: спавн, взаимодействие с юнитами."""
        import random
        
        # Спавним нейтральные объекты каждые 300 тиков (примерно раз в 5 секунд при 60 FPS)
        if self.state.tick - self._last_neutral_spawn_tick >= 300:
            self._last_neutral_spawn_tick = self.state.tick
            
            # Случайно выбираем линию и позицию
            if self.state.lanes:
                lane_id = random.choice(list(self.state.lanes.keys()))
                lane = self.state.lanes[lane_id]
                
                # Позиция в центральной зоне (между 0.3 и 0.7 длины линии)
                position = random.uniform(0.3 * lane.length, 0.7 * lane.length)
                
                # Случайно выбираем тип объекта
                obj_type = random.choice(["gold", "chest", "monster"])
                
                neutral_id = NeutralObjectId(self.state.next_neutral_object_id)
                self.state.next_neutral_object_id += 1
                
                if obj_type == "gold":
                    # Золото: случайное количество 20-50
                    value = random.uniform(20.0, 50.0)
                    obj = NeutralObject(
                        id=neutral_id,
                        lane_id=lane_id,
                        position=position,
                        object_type="gold",
                        value=value,
                    )
                elif obj_type == "chest":
                    # Сундук: случайный апгрейд
                    upgrade_ids = list(self.config.upgrade_templates.keys())
                    if upgrade_ids:
                        value = random.choice(upgrade_ids)
                        obj = NeutralObject(
                            id=neutral_id,
                            lane_id=lane_id,
                            position=position,
                            object_type="chest",
                            value=value,  # Храним upgrade_id как строку
                        )
                    else:
                        return  # Нет апгрейдов для сундука
                else:  # monster
                    # Разные типы монстров с разными механиками
                    monster_type = random.choice(["normal", "tank", "fast", "ranged"])
                    if monster_type == "tank":
                        # Танк: много HP, медленный, сильный урон
                        obj = NeutralObject(
                            id=neutral_id,
                            lane_id=lane_id,
                            position=position,
                            object_type="monster",
                            value=0.0,
                            hp=300.0,
                            max_hp=300.0,
                            damage=20.0,
                            attack_range=1.0,
                            attack_cooldown=1.5,
                            monster_type="tank",
                        )
                    elif monster_type == "fast":
                        # Быстрый: мало HP, быстрый, средний урон
                        obj = NeutralObject(
                            id=neutral_id,
                            lane_id=lane_id,
                            position=position,
                            object_type="monster",
                            value=0.0,
                            hp=80.0,
                            max_hp=80.0,
                            damage=12.0,
                            attack_range=1.5,
                            attack_cooldown=0.8,
                            monster_type="fast",
                        )
                    elif monster_type == "ranged":
                        # Дальнобойный: средний HP, дальняя атака
                        obj = NeutralObject(
                            id=neutral_id,
                            lane_id=lane_id,
                            position=position,
                            object_type="monster",
                            value=0.0,
                            hp=120.0,
                            max_hp=120.0,
                            damage=18.0,
                            attack_range=3.0,
                            attack_cooldown=1.2,
                            monster_type="ranged",
                        )
                    else:  # normal
                        # Обычный: средние характеристики
                        obj = NeutralObject(
                            id=neutral_id,
                            lane_id=lane_id,
                            position=position,
                            object_type="monster",
                            value=0.0,
                            hp=150.0,
                            max_hp=150.0,
                            damage=15.0,
                            attack_range=1.5,
                            attack_cooldown=1.2,
                            monster_type="normal",
                        )
                
                self.state.neutral_objects[neutral_id] = obj
        
        # Обновляем монстров: атакуют ближайших юнитов
        for obj in list(self.state.neutral_objects.values()):
            if not obj.alive or obj.object_type != "monster":
                continue
            
            obj.attack_cooldown_remaining = max(0.0, obj.attack_cooldown_remaining - dt)
            
            lane = self.state.lanes.get(obj.lane_id)
            if lane is None:
                continue
            
            # Ищем ближайшего юнита на этой линии
            closest_unit: Optional[Unit] = None
            closest_distance: float = float('inf')
            
            for unit_id in lane.unit_ids:
                if unit_id not in self.state.units:
                    continue
                unit = self.state.units[unit_id]
                if not unit.alive:
                    continue
                
                distance = abs(unit.position - obj.position)
                if distance <= obj.attack_range and distance < closest_distance:
                    closest_unit = unit
                    closest_distance = distance
            
            # Атакуем, если цель найдена и кулдаун готов
            if closest_unit is not None and obj.attack_cooldown_remaining <= 0:
                closest_unit.hp -= obj.damage
                obj.attack_cooldown_remaining = obj.attack_cooldown
                
                if closest_unit.hp <= 0:
                    closest_unit.alive = False
        
        # Проверяем взаимодействие юнитов с нейтральными объектами
        for unit in list(self.state.units.values()):
            if not unit.alive:
                continue
            
            for obj in list(self.state.neutral_objects.values()):
                if not obj.alive:
                    continue
                
                if obj.lane_id != unit.lane_id:
                    continue
                
                distance = abs(unit.position - obj.position)
                if distance <= 0.5:  # Юнит достаточно близко
                    if obj.object_type == "gold":
                        # Подбираем золото
                        for p in self.state.players.values():
                            if p.team_id == unit.team_id:
                                p.gold += obj.value
                                self._add_event(f"Team {int(unit.team_id)} collected {int(obj.value)} gold")
                                break
                        obj.alive = False
                    elif obj.object_type == "chest":
                        # Открываем сундук - даём апгрейд
                        upgrade_id = str(obj.value)
                        if upgrade_id in self.config.upgrade_templates:
                            for p in self.state.players.values():
                                if p.team_id == unit.team_id:
                                    # Даём апгрейд игроку (если ещё не максимальный уровень)
                                    template = self.config.upgrade_templates[upgrade_id]
                                    current_level = p.upgrades.get(upgrade_id, 0)
                                    if current_level < template.max_level:
                                        p.upgrades[upgrade_id] = current_level + 1
                                        self._add_event(f"Team {int(unit.team_id)} found upgrade: {template.name}")
                                    break
                        obj.alive = False
                    elif obj.object_type == "monster":
                        # Юниты атакуют монстра
                        if unit.attack_cooldown_remaining <= 0:
                            obj.hp -= unit.damage
                            unit.attack_cooldown_remaining = unit.attack_cooldown
                            
                            if obj.hp <= 0:
                                obj.alive = False
                                # Награда за убийство монстра
                                for p in self.state.players.values():
                                    if p.team_id == unit.team_id:
                                        p.gold += 30.0
                                        self._add_event(f"Team {int(unit.team_id)} killed monster, +30 gold")
                                        break
        
        # Удаляем мёртвые нейтральные объекты
        dead_objects = [oid for oid, obj in self.state.neutral_objects.items() if not obj.alive]
        for oid in dead_objects:
            del self.state.neutral_objects[oid]

    def _update_visual_effects(self, dt: float) -> None:
        """Обновить визуальные эффекты способностей."""
        remaining_effects = []
        for effect in self.state.visual_effects:
            effect.remaining_time -= dt
            if effect.remaining_time > 0:
                remaining_effects.append(effect)
        self.state.visual_effects = remaining_effects

    def _check_end_conditions(self) -> None:
        """Проверить условия окончания игры."""
        if not self.state.running:
            return

        # Группируем базы по командам (используем bases_list для многолинейной карты)
        teams: set[TeamId] = {base.team_id for base in self.state.bases_list}
        teams_with_alive_bases: set[TeamId] = {
            base.team_id for base in self.state.bases_list if base.alive
        }

        # Если у какой-то команды все базы мертвы
        dead_teams = teams - teams_with_alive_bases

        if dead_teams and len(teams_with_alive_bases) == 1:
            # Определяем победителя
            winner_team = list(teams_with_alive_bases)[0]
            self.state.running = False
            self.state.winner_team_id = winner_team
            self._add_event(f"Game Over! Team {int(winner_team)} wins!")
            logger.info("Game ended. Winner: Team %s", int(winner_team))
