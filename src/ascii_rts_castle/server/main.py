"""
Точка входа серверного процесса.

Этап 5: полная реализация CLI с параметрами и запуском asyncio сервера.
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from ascii_rts_castle.config import create_default_game_config
from ascii_rts_castle.config_loader import load_game_config_from_file
from ascii_rts_castle.server.network import (
    DEFAULT_MAX_PLAYERS,
    DEFAULT_REQUIRED_PLAYERS,
    GameServer,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ASCII RTS Castle - Game Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind (default: 8765)")
    parser.add_argument(
        "--max-players",
        type=int,
        default=DEFAULT_MAX_PLAYERS,
        help=f"Maximum number of players (default: {DEFAULT_MAX_PLAYERS})",
    )
    parser.add_argument(
        "--required-players",
        type=int,
        default=DEFAULT_REQUIRED_PLAYERS,
        help=f"Number of players required to start the game (default: {DEFAULT_REQUIRED_PLAYERS})",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )
    parser.add_argument(
        "--config-file",
        default=None,
        help="Path to JSON game config file (if omitted, use built-in default config)",
    )
    return parser.parse_args()


async def _async_main() -> None:
    args = _parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.config_file:
        config = load_game_config_from_file(args.config_file)
    else:
        config = create_default_game_config()
    server = GameServer(
        config=config,
        host=args.host,
        port=args.port,
        max_players=args.max_players,
        required_players=args.required_players,
    )

    await server.start()
    try:
        await server.run_forever()
    finally:
        await server.stop()


def main() -> None:
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
