@echo off
REM Скрипт для установки зависимостей и запуска клиента

echo ========================================
echo Установка и запуск клиента
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
echo [ШАГ 2/2] Запуск клиента
echo ========================================
echo.

REM Запуск клиента с параметрами по умолчанию
REM Можно передать аргументы: setup_and_run_client.bat --mode local или --host 192.168.1.100
call run_client.bat %*

