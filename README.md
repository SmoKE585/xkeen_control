# xKeen Control

Приложение для Windows с иконкой в трее для управления сервисом `xkeen`, поднятым на роутере Keenetic.

> Примечание: приложение сделано через вайбкодинг на Codex 5.4.

## Что умеет

- показывает статус `xkeen` в трее
- включает, выключает и перезапускает `xkeen`
- перезапускает сервис по схеме `stop -> 3 сек -> start`
- включает или отключает автозапуск приложения вместе с Windows
- показывает сводку по роутеру: аптайм, среднюю нагрузку, CPU и память
- проверяет доступность сайтов по разным маршрутам
- открывает и редактирует JSON-конфиги по SSH
- скачивает конфиг во временную папку, открывает локально и заливает изменения обратно на роутер
- очищает временные файлы после завершения работы
- использует Notepad++, если он установлен
- работает на `PySide6`

## Основные файлы

- [app.py](./app.py) - запуск приложения, сигналы, трей и оркестрация
- [ui.py](./ui.py) - интерфейс PySide6 / Qt
- [services/router_service.py](./services/router_service.py) - работа с Keenetic и JSON-конфигами
- [services/editor_sync.py](./services/editor_sync.py) - temp-файлы и синхронизация редактирования
- [ssh_session.py](./ssh_session.py) - SSH-сессия на Paramiko
- [config.py](./config.py) - значения по умолчанию и чтение `.env`
- [vpn_tray.spec](./vpn_tray.spec) - сборка через PyInstaller

## Настройка

Пользовательские настройки задаются в файле `.env`.

Создайте `.env` рядом с приложением или возьмите за основу [.env.example](./.env.example):

```env
ROUTER_HOST=192.168.1.1
ROUTER_PORT=22
ROUTER_USER=root
ROUTER_PASSWORD=ваш_пароль
XRAY_CONFIG_DIR=/opt/etc/xray/configs
NOTEPADPP_PATH=C:\Program Files\Notepad++\notepad++.exe
```

Без пересборки можно менять:

- адрес и SSH-доступ к роутеру
- команды управления `xkeen`
- пути к конфигам и temp-папке
- путь к `Notepad++`
- стартовые сайты для проверок

`config.py` теперь нужен в основном как кодовый слой с дефолтами.

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

## Зависимости

- `paramiko`
- `PySide6`
- `pillow`
- `pyinstaller`
