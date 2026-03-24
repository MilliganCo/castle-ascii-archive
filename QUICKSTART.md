# Быстрый старт (Windows)

## Первый запуск

### Вариант 1: Python-скрипты (рекомендуется)

**Сервер:**
```bash
python -m ascii_rts_castle.server.main
```

**Клиент (GUI режим - окно):**
```bash
# Локальный режим
python run_client_gui.py --mode local

# Локальный режим с AI противником
python run_client_gui.py --mode local --ai

# Сетевой режим
python run_client_gui.py --mode network --host 127.0.0.1 --port 8765 --name Player1
```

**Клиент (терминальный режим):**
```bash
# Локальный режим
python run_client_terminal.py --mode local

# Сетевой режим
python run_client_terminal.py --mode network --host 127.0.0.1 --port 8765 --name Player1
```

### Вариант 2: Автоматическая установка и запуск (Windows .bat)

**Сервер:**
```cmd
setup_and_run_server.bat
```

**Клиент (локальный режим для тестирования):**
```cmd
REM Терминальный режим
setup_and_run_client.bat --mode local

REM GUI режим (окно)
setup_and_run_client.bat --mode local --ui window

REM С AI противником (Player 2 управляется AI)
setup_and_run_client.bat --mode local --ui window --ai
```

**Клиент (сетевой режим):**
```cmd
REM Терминальный режим
setup_and_run_client.bat --mode network --host 127.0.0.1 --port 8765 --name Player1

REM GUI режим (окно)
setup_and_run_client.bat --mode network --ui window --host 127.0.0.1 --port 8765 --name Player1
```

### Вариант 2: Ручная установка зависимостей

1. Установите зависимости один раз:
   ```cmd
   setup_dependencies.bat
   ```

2. Запускайте сервер:
   ```cmd
   run_server.bat
   ```

3. Запускайте клиент:
   ```cmd
   run_client.bat
   ```

## Доступные скрипты

### Python-скрипты (кроссплатформенные)

#### `run_client_gui.py`
Запускает клиент в GUI-режиме (графическое окно через pygame).

**Примеры:**
```bash
# Локальный режим
python run_client_gui.py --mode local

# Сетевой режим
python run_client_gui.py --mode network --host 127.0.0.1 --port 8765 --name Player1
```

#### `run_client_terminal.py`
Запускает клиент в терминальном режиме.

**Примеры:**
```bash
# Локальный режим
python run_client_terminal.py --mode local

# Сетевой режим
python run_client_terminal.py --mode network --host 127.0.0.1 --port 8765 --name Player1
```

### Windows .bat скрипты

#### `setup_dependencies.bat`
Устанавливает все зависимости проекта (выполняется автоматически в `setup_and_run_*.bat`).

### `run_server.bat`
Запускает сервер с параметрами по умолчанию:
- Host: `0.0.0.0`
- Port: `8765`
- Требуется игроков: `2`
- Максимум игроков: `4`
- Уровень логирования: `INFO`

**Примеры использования:**
```cmd
REM Базовый запуск
run_server.bat

REM С кастомным портом и количеством игроков
run_server.bat --port 9000 --required-players 3

REM С кастомным конфигом карты
run_server.bat --config-file configs/maps/default.json

REM Все параметры
run_server.bat --host 0.0.0.0 --port 8765 --required-players 2 --max-players 4 --log-level DEBUG --config-file configs/maps/default.json
```

### `run_client.bat`
Запускает клиент с параметрами по умолчанию:
- Режим: `network`
- Host: `127.0.0.1`
- Port: `8765`
- Имя: `Player`

**Примеры использования:**
```cmd
REM Локальный режим (демо с AI) - терминал
run_client.bat --mode local

REM Локальный режим (демо с AI) - GUI окно
run_client.bat --mode local --ui window

REM Сетевой режим (подключение к серверу) - терминал
run_client.bat --mode network --host 127.0.0.1 --port 8765 --name Player1

REM Сетевой режим (подключение к серверу) - GUI окно
run_client.bat --mode network --ui window --host 127.0.0.1 --port 8765 --name Player1

REM Подключение к удалённому серверу - GUI окно
run_client.bat --mode network --ui window --host 192.168.1.100 --port 8765 --name Player1
```

### `setup_and_run_server.bat`
Устанавливает зависимости (если нужно) и запускает сервер. Можно передать аргументы:
```cmd
setup_and_run_server.bat --port 9000 --required-players 3
```

### `setup_and_run_client.bat`
Устанавливает зависимости (если нужно) и запускает клиент. Можно передать аргументы:
```cmd
REM Локальный режим в терминале
setup_and_run_client.bat --mode local

REM Локальный режим в GUI окне
setup_and_run_client.bat --mode local --ui window

REM Сетевой режим в GUI окне
setup_and_run_client.bat --mode network --ui window --host 192.168.1.100
```

## Типичный сценарий игры

1. **Запустите сервер** (в первом терминале):
   ```cmd
   setup_and_run_server.bat
   ```
   Дождитесь сообщения о том, что сервер запущен и ждёт подключений.

2. **Запустите первого клиента** (во втором терминале):
   ```cmd
   REM Терминальный режим
   setup_and_run_client.bat --mode network --name Player1
   
   REM Или GUI режим
   setup_and_run_client.bat --mode network --ui window --name Player1
   ```

3. **Запустите второго клиента** (в третьем терминале):
   ```cmd
   REM Терминальный режим
   setup_and_run_client.bat --mode network --name Player2
   
   REM Или GUI режим
   setup_and_run_client.bat --mode network --ui window --name Player2
   ```

4. Когда оба клиента подключены и готовы, игра начнётся автоматически.

**Примечание:** Для GUI режима требуется установка pygame. Он устанавливается автоматически при запуске `setup_and_run_client.bat`, но если возникли проблемы, установите вручную:
```cmd
pip install -e ".[gui]"
```

## Управление в игре

### Выбор линии
- **Up / Down** — переключение между линиями (1/3, 2/3, 3/3)

### Постройка зданий
- **1, 2, 3, 4** — построить здание из панели действий (или клик мышью в GUI режиме)
- Здания отображаются в панели действий внизу экрана

### Исследование апгрейдов
- **Q, W, E, R** — исследовать апгрейд из панели действий (или клик мышью в GUI режиме)
- Апгрейды отображаются в панели действий внизу экрана

### Другие действия
- **H** — показать/скрыть экран подсказки
- **ESC** или **q** — выход из игры

### Текстовый ввод (fallback)
В терминальном режиме также доступен текстовый ввод команд:
- `b <lane> <building>` — построить здание
- `r <upgrade>` — исследовать апгрейд
- `q` или `quit` — выход

Подробнее см. в [README.md](README.md).

