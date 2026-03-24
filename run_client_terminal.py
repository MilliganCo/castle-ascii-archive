#!/usr/bin/env python3
"""
Скрипт для запуска клиента в терминальном режиме.

Использование:
    python run_client_terminal.py [--mode local|network] [--host HOST] [--port PORT] [--name NAME]
"""

from __future__ import annotations

import argparse
import asyncio
import sys

# Добавляем путь к модулям проекта
sys.path.insert(0, "src")

from ascii_rts_castle.client.main import run_local_demo, run_network_client


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ASCII RTS Castle - Terminal Client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  # Локальный режим (демо)
  python run_client_terminal.py --mode local

  # Сетевой режим (подключение к серверу)
  python run_client_terminal.py --mode network --host 127.0.0.1 --port 8765 --name Player1

  # Подключение к удалённому серверу
  python run_client_terminal.py --mode network --host 192.168.1.100 --port 8765 --name Player1
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

    args = parser.parse_args()

    try:
        if args.mode == "local":
            print("Запуск локальной демки в терминальном режиме...")
            print("Для выхода введите 'q' или 'quit'")
            run_local_demo()
        else:
            print(f"Подключение к серверу {args.host}:{args.port}...")
            print("Для выхода введите 'q' или 'quit'")
            asyncio.run(run_network_client(args.host, args.port, args.name))
    except KeyboardInterrupt:
        print("\nПрервано пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"ОШИБКА: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

