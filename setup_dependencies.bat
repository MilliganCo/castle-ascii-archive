@echo off
REM Скрипт для установки всех зависимостей проекта

echo ========================================
echo Установка зависимостей ascii-rts-castle
echo ========================================
echo.

REM Проверка наличия Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не найден! Убедитесь, что Python 3.11+ установлен и добавлен в PATH.
    pause
    exit /b 1
)

echo [INFO] Python найден:
python --version
echo.

REM Установка проекта в режиме разработки
echo [INFO] Установка проекта и зависимостей...
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

if errorlevel 1 (
    echo [ОШИБКА] Не удалось установить зависимости!
    pause
    exit /b 1
)

REM Установка GUI зависимостей (опционально)
echo.
echo [INFO] Установка GUI зависимостей (pygame)...
python -m pip install -e ".[gui]"

if errorlevel 1 (
    echo [ПРЕДУПРЕЖДЕНИЕ] Не удалось установить GUI зависимости. GUI режим будет недоступен.
    echo [INFO] Для установки GUI зависимостей позже выполните: pip install -e ".[gui]"
) else (
    echo [INFO] GUI зависимости установлены успешно!
)

echo.
echo [УСПЕХ] Все зависимости установлены!
echo.
pause

