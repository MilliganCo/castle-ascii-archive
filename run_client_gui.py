#!/usr/bin/env python3
"""
Скрипт для запуска клиента в GUI-режиме (окно).

Использование:
    python run_client_gui.py [--mode local|network] [--host HOST] [--port PORT] [--name NAME]
"""

from __future__ import annotations

import argparse
import asyncio
import sys

# Добавляем путь к модулям проекта
sys.path.insert(0, "src")

from ascii_rts_castle.client.main import (
    run_local_demo_window,
    run_network_client_window,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ASCII RTS Castle - GUI Client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  # Локальный режим (демо)
  python run_client_gui.py --mode local

  # Сетевой режим (подключение к серверу)
  python run_client_gui.py --mode network --host 127.0.0.1 --port 8765 --name Player1

  # Подключение к удалённому серверу
  python run_client_gui.py --mode network --host 192.168.1.100 --port 8765 --name Player1
        """,
    )
    parser.add_argument(
        "--mode",
        choices=["local", "network"],
        default="local",
        help="Режим работы: 'local' (локальная демка) или 'network' (сетевой клиент) (по умолчанию: local)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Адрес сервера для сетевого режима (по умолчанию: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Порт сервера для сетевого режима (по умолчанию: 8765)",
    )
    parser.add_argument(
        "--name",
        default="Player",
        help="Имя игрока для сетевого режима (по умолчанию: Player)",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=60,
        help="Целевой FPS для рендеринга (по умолчанию: 60)",
    )

    args = parser.parse_args()

    try:
        if args.mode == "local":
            print("Запуск локальной демки в GUI-режиме...")
            print("Для выхода нажмите ESC или закройте окно")
            print("Управление: Up/Down - выбор линии, 1-4 - здания, Q/W/E/R - апгрейды, H - помощь")
            run_local_demo_window(fps=args.fps)
        else:
            print(f"Подключение к серверу {args.host}:{args.port}...")
            print("Для выхода нажмите ESC или закройте окно")
            print("Управление: Up/Down - выбор линии, 1-4 - здания, Q/W/E/R - апгрейды, H - помощь")
            asyncio.run(run_network_client_window(args.host, args.port, args.name, fps=args.fps))
    except KeyboardInterrupt:
        print("\nПрервано пользователем")
        sys.exit(0)
    except ImportError as e:
        if "pygame" in str(e).lower():
            print("ОШИБКА: pygame не установлен!")
            print("Установите GUI зависимости:")
            print("  pip install -e '.[gui]'")
            sys.exit(1)
        raise
    except Exception as e:
        print(f"ОШИБКА: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

