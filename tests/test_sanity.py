"""Базовые тесты для проверки импорта и конфигурации."""

from ascii_rts_castle import config


def test_basic_import() -> None:
    assert isinstance(config.GAME_NAME, str)
    assert isinstance(config.VERSION, str)
