@echo off
REM Скрипт для запуска игрового сервера

echo ========================================
echo Запуск сервера ascii-rts-castle
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
set HOST=0.0.0.0
set PORT=8765
set REQUIRED_PLAYERS=2
set MAX_PLAYERS=4
set LOG_LEVEL=INFO
set CONFIG_FILE=

REM Парсинг аргументов командной строки
:parse_args
if "%~1"=="" goto run_server
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
if "%~1"=="--required-players" (
    set REQUIRED_PLAYERS=%~2
    shift
    shift
    goto parse_args
)
if "%~1"=="--max-players" (
    set MAX_PLAYERS=%~2
    shift
    shift
    goto parse_args
)
if "%~1"=="--log-level" (
    set LOG_LEVEL=%~2
    shift
    shift
    goto parse_args
)
if "%~1"=="--config-file" (
    set CONFIG_FILE=%~2
    shift
    shift
    goto parse_args
)
shift
goto parse_args

:run_server
echo [INFO] Параметры сервера:
echo   Host: %HOST%
echo   Port: %PORT%
echo   Требуется игроков: %REQUIRED_PLAYERS%
echo   Максимум игроков: %MAX_PLAYERS%
echo   Уровень логирования: %LOG_LEVEL%
if not "%CONFIG_FILE%"=="" (
    echo   Конфиг карты: %CONFIG_FILE%
) else (
    echo   Конфиг карты: (по умолчанию)
)
echo.
echo [INFO] Запуск сервера...
echo [INFO] Для остановки нажмите Ctrl+C
echo.

REM Запуск сервера
if "%CONFIG_FILE%"=="" (
    python -m ascii_rts_castle.server.main --host %HOST% --port %PORT% --required-players %REQUIRED_PLAYERS% --max-players %MAX_PLAYERS% --log-level %LOG_LEVEL%
) else (
    python -m ascii_rts_castle.server.main --host %HOST% --port %PORT% --required-players %REQUIRED_PLAYERS% --max-players %MAX_PLAYERS% --log-level %LOG_LEVEL% --config-file %CONFIG_FILE%
)

if errorlevel 1 (
    echo.
    echo [ОШИБКА] Сервер завершился с ошибкой!
    pause
    exit /b 1
)

echo.
echo [INFO] Сервер остановлен.
pause

