@echo off
REM Скрипт для установки зависимостей и запуска сервера

echo ========================================
echo Установка и запуск сервера
echo ========================================
echo.

REM Проверка наличия Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не найден! Убедитесь, что Python 3.11+ установлен и добавлен в PATH.
    pause
    exit /b 1
)

REM Установка зависимостей
echo [ШАГ 1/2] Установка зависимостей...
call setup_dependencies.bat
if errorlevel 1 (
    echo [ОШИБКА] Не удалось установить зависимости!
    pause
    exit /b 1
)

echo.
echo ========================================
echo [ШАГ 2/2] Запуск сервера
echo ========================================
echo.

REM Запуск сервера с параметрами по умолчанию
REM Можно передать аргументы: setup_and_run_server.bat --port 9000 --required-players 3
call run_server.bat %*

