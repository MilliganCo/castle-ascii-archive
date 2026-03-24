@echo off
REM Скрипт для запуска игрового клиента

echo ========================================
echo Запуск клиента ascii-rts-castle
echo ========================================
echo.

REM Проверка наличия Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не найден! Убедитесь, что Python 3.11+ установлен и добавлен в PATH.
    pause
    exit /b 1
)

REM Параметры по умолчанию
set MODE=network
set UI=terminal
set FPS=60
set HOST=127.0.0.1
set PORT=8765
set NAME=Player

REM Парсинг аргументов командной строки
:parse_args
if "%~1"=="" goto run_client
if "%~1"=="--mode" (
    set MODE=%~2
    shift
    shift
    goto parse_args
)
if "%~1"=="--ui" (
    set UI=%~2
    shift
    shift
    goto parse_args
)
if "%~1"=="--fps" (
    set FPS=%~2
    shift
    shift
    goto parse_args
)
if "%~1"=="--host" (
    set HOST=%~2
    shift
    shift
    goto parse_args
)
if "%~1"=="--port" (
    set PORT=%~2
    shift
    shift
    goto parse_args
)
if "%~1"=="--name" (
    set NAME=%~2
    shift
    shift
    goto parse_args
)
shift
goto parse_args

:run_client
echo [INFO] Параметры клиента:
echo   Режим: %MODE%
echo   UI: %UI%
echo   FPS: %FPS%
if "%MODE%"=="network" (
    echo   Хост сервера: %HOST%
    echo   Порт сервера: %PORT%
    echo   Имя игрока: %NAME%
)
echo.
echo [INFO] Запуск клиента...
if "%UI%"=="window" (
    echo [INFO] GUI режим: для выхода нажмите ESC или закройте окно
    echo [INFO] Управление: Up/Down - выбор линии, 1-4 - здания, Q/W/E/R - апгрейды, H - помощь
) else (
    echo [INFO] Терминальный режим: для выхода введите 'q' или 'quit'
)
echo.

REM Запуск клиента
if "%MODE%"=="local" (
    python -m ascii_rts_castle.client.main --mode local --ui %UI% --fps %FPS%
) else (
    python -m ascii_rts_castle.client.main --mode network --ui %UI% --fps %FPS% --host %HOST% --port %PORT% --name %NAME%
)

if errorlevel 1 (
    echo.
    echo [ОШИБКА] Клиент завершился с ошибкой!
    pause
    exit /b 1
)

echo.
echo [INFO] Клиент остановлен.
pause

