# xKeen Control

Приложение для Windows с иконкой в трее для управления сервисом `xkeen`, поднятым на роутере Keenetic.

## Что умеет

- показывает статус `xkeen` в трее
- включает, выключает и перезапускает `xkeen`
- перезапускает сервис по схеме `stop -> 3 сек -> start`
- включает или отключает автозапуск приложения вместе с Windows
- показывает сводку по роутеру: аптайм, среднюю нагрузку, CPU и память
- проверяет доступность сайтов по разным маршрутам
- открывает и редактирует JSON-конфиги из SMB-каталога роутера
- использует Notepad++, если он установлен
- работает на `PySide6`

## Основные файлы

- [app.py](./app.py) - логика приложения, SSH-команды, действия трея
- [ui.py](./ui.py) - интерфейс PySide6 / Qt
- [ssh_session.py](./ssh_session.py) - SSH-сессия на Paramiko
- [config.py](./config.py) - настройки роутера, SMB и команд
- [vpn_tray.spec](./vpn_tray.spec) - сборка через PyInstaller

## Настройка

Основные параметры лежат в [config.py](./config.py):

- `ROUTER_HOST`
- `ROUTER_PORT`
- `ROUTER_USER`
- `ROUTER_PASSWORD`
- `SMB_HOST`
- `SMB_USER`
- `SMB_PASS`
- `XRAY_CONFIG_DIR`
- `CMD_VPN_ON`
- `CMD_VPN_OFF`
- `CMD_STATUS`
- `CONNECTIVITY_CHECKS`

Для локальных секретов создайте `config_local.py`. Этот файл перекрывает значения из `config.py` и не попадает в git.

Пример:

```python
SMB_PASS = "ваш_пароль"
ROUTER_PASSWORD = "ваш_пароль"
```

## Запуск

```powershell
python vpn_tray.py
```

## Сборка exe

```powershell
cmd /c build_exe.bat
```

Готовый файл:

```text
dist\vpn_tray.exe
```

## Требования

- Windows 10/11
- Python 3.11+
- доступ к Keenetic по SSH
- доступ к SMB-каталогу с конфигами

## Зависимости

- `paramiko`
- `PySide6`
- `pillow`
- `pyinstaller`
