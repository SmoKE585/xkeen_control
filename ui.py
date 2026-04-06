import os
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QTextOption
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileIconProvider,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QPlainTextEdit,
    QStyle,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from config import TEMP_CONFIG_DIR, XRAY_CONFIG_DIR, format_host
from models import ConnectivityCheck, RouterStats

if TYPE_CHECKING:
    from app import VPNTrayApp


class InfoCard(QFrame):
    def __init__(self, title: str, accent: str = "#176b87", parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("InfoCard")
        self.accent = accent

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("CardTitle")
        layout.addWidget(self.title_label)

        self.value_label = QLabel("...")
        self.value_label.setObjectName("CardValue")
        self.value_label.setWordWrap(True)
        self.value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.value_label)

        self.hint_label = QLabel("Ожидание данных")
        self.hint_label.setObjectName("CardHint")
        self.hint_label.setWordWrap(True)
        layout.addWidget(self.hint_label)

        layout.addStretch(1)

    def set_content(self, value: str, hint: str) -> None:
        self.value_label.setText(value)
        self.hint_label.setText(hint)

    def set_badge(self, value: str, fg: str, bg: str, hint: str) -> None:
        self.value_label.setText(value)
        self.value_label.setStyleSheet(
            f"color: {fg}; background: {bg}; border-radius: 12px; padding: 10px 14px; font: 700 17px 'Segoe UI';"
        )
        self.hint_label.setText(hint)

    def clear_badge_style(self) -> None:
        self.value_label.setStyleSheet("")


class RouteCard(QFrame):
    def __init__(self, check: ConnectivityCheck, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("RouteCard")

        ok = check.ok
        tone_fg = "#1f7a4c" if ok else "#b44335"
        tone_bg = "#d9f2e4" if ok else "#f9ddd8"
        status_text = "OK"
        if ok and check.status_code is not None:
            status_text += f" [{check.status_code}]"
        if ok and check.latency_ms is not None:
            status_text += f"  {check.latency_ms} мс"
        if not ok:
            status_text = check.error or "Нет доступа"

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        text_box = QVBoxLayout()
        text_box.setSpacing(4)

        name = QLabel(check.name)
        name.setObjectName("RouteTitle")
        text_box.addWidget(name)

        details = QLabel(f"{format_host(check.url)}  |  {check.expected}")
        details.setObjectName("RouteHint")
        details.setWordWrap(True)
        text_box.addWidget(details)

        layout.addLayout(text_box, 1)

        badge = QLabel(status_text)
        badge.setStyleSheet(
            f"color: {tone_fg}; background: {tone_bg}; border-radius: 10px; padding: 8px 12px; font: 700 11pt 'Segoe UI';"
        )
        badge.setAlignment(Qt.AlignCenter)
        badge.setWordWrap(True)
        badge.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        layout.addWidget(badge, 0, Qt.AlignTop)


class SettingsDialog(QDialog):
    def __init__(self, app: "VPNTrayApp", parent: QWidget | None = None):
        super().__init__(parent)
        self.app = app
        self.setWindowTitle("Настройки")
        self.setModal(True)
        self.resize(520, 240)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        title = QLabel("Настройки xKeen Control")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        self.startup_checkbox = QCheckBox("Запускать приложение вместе с Windows")
        self.startup_checkbox.setChecked(self.app.is_startup_enabled())
        layout.addWidget(self.startup_checkbox)

        editor_path = self.app.get_notepadpp_path() or "Notepad++ не найден, будет использовано системное приложение"
        editor_label = QLabel(f"Редактор: {editor_path}")
        editor_label.setWordWrap(True)
        editor_label.setObjectName("MutedLabel")
        layout.addWidget(editor_label)

        layout.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def save(self) -> None:
        try:
            self.app.set_startup_enabled(self.startup_checkbox.isChecked())
            QMessageBox.information(self, "Настройки", "Сохранено.")
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить настройки:\n{exc}")


class MainWindow(QMainWindow):
    BG = "#f4efe6"
    PANEL = "#fbf7f0"
    PANEL_ALT = "#efe6d5"

    def __init__(self, app: "VPNTrayApp"):
        super().__init__()
        self.app = app
        self.setWindowTitle("xKeen Control")
        self.resize(1280, 820)
        self.setMinimumSize(1120, 720)

        self._apply_styles()
        self._build_ui()
        self._setup_tray()
        self._update_editor_title()

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #f4efe6;
                color: #1f2937;
                font: 10pt 'Segoe UI';
            }
            QFrame#Panel, QFrame#InfoCard, QFrame#RouteCard {
                background: #fbf7f0;
                border: 1px solid #d8cbb4;
                border-radius: 18px;
            }
            QLabel#HeroTitle {
                font: 700 24pt 'Segoe UI';
                color: #1f2937;
            }
            QLabel#HeroSubtitle {
                font: 10pt 'Segoe UI';
                color: #6b7280;
            }
            QLabel#SectionTitle {
                font: 700 15pt 'Segoe UI';
                color: #1f2937;
            }
            QLabel#CardTitle {
                font: 10pt 'Segoe UI';
                color: #6b7280;
            }
            QLabel#CardValue {
                font: 700 16pt 'Segoe UI';
                color: #1f2937;
            }
            QLabel#CardHint, QLabel#MutedLabel, QLabel#RouteHint {
                font: 9pt 'Segoe UI';
                color: #6b7280;
            }
            QLabel#RouteTitle {
                font: 700 11pt 'Segoe UI';
                color: #1f2937;
            }
            QPushButton {
                border: none;
                border-radius: 12px;
                padding: 10px 14px;
                font: 600 10pt 'Segoe UI';
                background: #d8edf5;
                color: #176b87;
            }
            QPushButton:hover {
                background: #c8e4ee;
            }
            QPushButton:disabled {
                background: #ebe5d9;
                color: #998f80;
            }
            QPushButton#PrimaryButton {
                background: #176b87;
                color: white;
            }
            QPushButton#PrimaryButton:hover {
                background: #12586f;
            }
            QListWidget, QPlainTextEdit {
                background: #fffdfa;
                border: 1px solid #d8cbb4;
                border-radius: 14px;
                padding: 8px;
            }
            QListWidget::item {
                padding: 8px 10px;
                border-radius: 8px;
            }
            QListWidget::item:selected {
                background: #176b87;
                color: white;
            }
            QPlainTextEdit {
                background: #1e293b;
                color: #e5edf7;
                font: 10.5pt 'Consolas';
            }
            """
        )

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        hero = QFrame()
        hero.setObjectName("Panel")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(22, 20, 22, 20)

        title_box = QVBoxLayout()
        title = QLabel("xKeen Control")
        title.setObjectName("HeroTitle")
        subtitle = QLabel("Управление сервисом xkeen на роутере Keenetic")
        subtitle.setObjectName("HeroSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        hero_layout.addLayout(title_box, 1)

        hero_actions = QHBoxLayout()
        self.refresh_button = QPushButton("Обновить")
        self.refresh_button.setObjectName("PrimaryButton")
        self.refresh_button.clicked.connect(self.app.refresh_async)
        hero_actions.addWidget(self.refresh_button)

        self.settings_button = QPushButton("Настройки")
        self.settings_button.clicked.connect(self.show_settings)
        hero_actions.addWidget(self.settings_button)
        hero_layout.addLayout(hero_actions)

        root.addWidget(hero)

        body = QHBoxLayout()
        body.setSpacing(16)
        root.addLayout(body, 1)

        left = QVBoxLayout()
        left.setSpacing(16)
        body.addLayout(left, 7)

        right = QVBoxLayout()
        right.setSpacing(16)
        body.addLayout(right, 5)

        metrics_panel = QFrame()
        metrics_panel.setObjectName("Panel")
        metrics_layout = QGridLayout(metrics_panel)
        metrics_layout.setContentsMargins(18, 18, 18, 18)
        metrics_layout.setHorizontalSpacing(12)
        metrics_layout.setVerticalSpacing(12)

        self.status_card = InfoCard("Состояние xkeen")
        self.uptime_card = InfoCard("Аптайм")
        self.load_card = InfoCard("Средняя нагрузка")
        self.cpu_card = InfoCard("Нагрузка xkeen")
        self.memory_card = InfoCard("RAM")

        metrics_layout.addWidget(self.status_card, 0, 0)
        metrics_layout.addWidget(self.uptime_card, 0, 1)
        metrics_layout.addWidget(self.load_card, 0, 2)
        metrics_layout.addWidget(self.cpu_card, 1, 0)
        metrics_layout.addWidget(self.memory_card, 1, 1, 1, 2)

        left.addWidget(metrics_panel)

        actions_panel = QFrame()
        actions_panel.setObjectName("Panel")
        actions_layout = QVBoxLayout(actions_panel)
        actions_layout.setContentsMargins(18, 18, 18, 18)
        actions_layout.setSpacing(12)

        actions_title = QLabel("Быстрые действия")
        actions_title.setObjectName("SectionTitle")
        actions_layout.addWidget(actions_title)

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(10)

        self.on_button = QPushButton("Включить")
        self.on_button.setObjectName("PrimaryButton")
        self.on_button.clicked.connect(self.app.action_on)
        buttons_row.addWidget(self.on_button)

        self.off_button = QPushButton("Выключить")
        self.off_button.clicked.connect(self.app.action_off)
        buttons_row.addWidget(self.off_button)

        self.restart_button = QPushButton("Перезапустить")
        self.restart_button.clicked.connect(self.app.action_restart)
        buttons_row.addWidget(self.restart_button)

        actions_layout.addLayout(buttons_row)
        left.addWidget(actions_panel)

        diag_panel = QFrame()
        diag_panel.setObjectName("Panel")
        diag_layout = QVBoxLayout(diag_panel)
        diag_layout.setContentsMargins(18, 18, 18, 18)
        diag_layout.setSpacing(10)

        diag_title = QLabel("Диагностика роутера")
        diag_title.setObjectName("SectionTitle")
        diag_layout.addWidget(diag_title)

        self.diagnostics_text = QPlainTextEdit()
        self.diagnostics_text.setReadOnly(True)
        self.diagnostics_text.setWordWrapMode(QTextOption.NoWrap)
        diag_layout.addWidget(self.diagnostics_text, 1)
        left.addWidget(diag_panel, 1)

        routes_panel = QFrame()
        routes_panel.setObjectName("Panel")
        routes_layout = QVBoxLayout(routes_panel)
        routes_layout.setContentsMargins(18, 18, 18, 18)
        routes_layout.setSpacing(10)

        routes_title = QLabel("Маршруты и доступность")
        routes_title.setObjectName("SectionTitle")
        routes_layout.addWidget(routes_title)

        self.routes_container = QVBoxLayout()
        self.routes_container.setSpacing(10)
        routes_layout.addLayout(self.routes_container)
        routes_layout.addStretch(1)
        right.addWidget(routes_panel)

        configs_panel = QFrame()
        configs_panel.setObjectName("Panel")
        configs_layout = QVBoxLayout(configs_panel)
        configs_layout.setContentsMargins(18, 18, 18, 18)
        configs_layout.setSpacing(12)

        configs_title = QLabel("Конфиги xkeen")
        configs_title.setObjectName("SectionTitle")
        configs_layout.addWidget(configs_title)

        configs_hint = QLabel("Файлы читаются по SSH из `/opt/etc/xray/configs`")
        configs_hint.setObjectName("MutedLabel")
        configs_layout.addWidget(configs_hint)

        self.configs_list = QListWidget()
        self.configs_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.configs_list.itemDoubleClicked.connect(lambda _: self.open_selected_config())
        configs_layout.addWidget(self.configs_list, 1)

        cfg_buttons = QHBoxLayout()
        cfg_buttons.setSpacing(10)

        self.reload_configs_button = QPushButton("Обновить список")
        self.reload_configs_button.clicked.connect(self.app.reload_configs)
        cfg_buttons.addWidget(self.reload_configs_button)

        self.open_config_button = QPushButton("Открыть в Notepad++")
        self.open_config_button.setObjectName("PrimaryButton")
        self.open_config_button.clicked.connect(self.open_selected_config)
        cfg_buttons.addWidget(self.open_config_button)

        self.open_folder_button = QPushButton("Открыть temp")
        self.open_folder_button.clicked.connect(self.open_config_folder)
        cfg_buttons.addWidget(self.open_folder_button)

        configs_layout.addLayout(cfg_buttons)
        right.addWidget(configs_panel, 1)

    def _setup_tray(self) -> None:
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setToolTip("xKeen Control")

    def on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_main()

    def _update_editor_title(self) -> None:
        editor_name = "Notepad++" if self.app.get_notepadpp_path() else "системный редактор"
        self.setWindowTitle(f"xKeen Control [{editor_name}]")

    def show_main(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def show_settings(self) -> None:
        dialog = SettingsDialog(self.app, self)
        dialog.exec()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        event.ignore()
        self.hide()

    def show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)

    def set_busy(self, busy: bool) -> None:
        for button in (
            self.refresh_button,
            self.settings_button,
            self.on_button,
            self.off_button,
            self.restart_button,
            self.reload_configs_button,
            self.open_config_button,
            self.open_folder_button,
        ):
            button.setDisabled(busy)

    def set_connection_state(self, ok: bool) -> None:
        if ok:
            self.status_card.hint_label.setText("Данные обновлены")
        else:
            self.status_card.hint_label.setText("Ошибка SSH")

    def set_status_text(self, status: str) -> None:
        if status == "on":
            self.status_card.set_badge("ВКЛЮЧЕН", "#1f7a4c", "#d9f2e4", "Маршруты активны")
        elif status == "off":
            self.status_card.set_badge("ВЫКЛЮЧЕН", "#b44335", "#f9ddd8", "xkeen остановлен")
        else:
            self.status_card.set_badge("НЕИЗВЕСТНО", "#9a6700", "#f3e7c6", "Нет данных")

    def update_stats_cards(self, stats: RouterStats) -> None:
        self.uptime_card.clear_badge_style()
        self.load_card.clear_badge_style()
        self.cpu_card.clear_badge_style()
        self.memory_card.clear_badge_style()

        self.uptime_card.set_content(stats.uptime, "Время работы роутера")
        self.load_card.set_content(stats.load_average, "Средняя нагрузка")
        self.cpu_card.set_content(stats.xray_cpu, "CPU процесса xkeen")
        self.memory_card.set_content(stats.memory, "Использовано / всего / свободно")
        self.diagnostics_text.setPlainText(stats.text)

    def update_connectivity_checks(self, checks: list[ConnectivityCheck]) -> None:
        while self.routes_container.count():
            item = self.routes_container.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not checks:
            self.routes_container.addWidget(QLabel("Нет данных по маршрутам"))
            return

        for check in checks:
            self.routes_container.addWidget(RouteCard(check))

    def update_configs(self, items: list[str]) -> None:
        self.configs_list.clear()
        icon_provider = QFileIconProvider()
        for item in items:
            list_item = QListWidgetItem(item)
            if not item.startswith("["):
                list_item.setIcon(icon_provider.icon(QFileIconProvider.File))
            self.configs_list.addItem(list_item)

    def _get_selected_config_path(self) -> str | None:
        item = self.configs_list.currentItem()
        if not item:
            return None
        name = item.text()
        if name.startswith("["):
            return None
        return os.path.join(XRAY_CONFIG_DIR, name)

    def open_selected_config(self) -> None:
        path = self._get_selected_config_path()
        if not path:
            return
        try:
            self.app.run_config_editor(path)
        except Exception as exc:
            self.show_error("Ошибка", f"Не удалось открыть файл:\n{exc}")

    def open_config_folder(self) -> None:
        try:
            os.makedirs(TEMP_CONFIG_DIR, exist_ok=True)
            os.startfile(TEMP_CONFIG_DIR)
        except Exception as exc:
            self.show_error("Ошибка", str(exc))
