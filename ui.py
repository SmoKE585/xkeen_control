import os
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextOption
from PySide6.QtWidgets import (
    QFileIconProvider,
    QCheckBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QSystemTrayIcon,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config import SITE_CHECKS_FILE, TEMP_CONFIG_DIR, XRAY_CONFIG_DIR, format_host
from models import ConnectivityCheck, RouterStats

if TYPE_CHECKING:
    from app import VPNTrayApp


class InfoCard(QFrame):
    def __init__(self, title: str):
        super().__init__()
        self.setObjectName("InfoCard")
        box = QVBoxLayout(self)
        box.setContentsMargins(16, 14, 16, 14)
        self.title = QLabel(title)
        self.title.setObjectName("CardTitle")
        self.value = QLabel("...")
        self.value.setObjectName("CardValue")
        self.value.setWordWrap(True)
        self.hint = QLabel("Ожидание данных")
        self.hint.setObjectName("CardHint")
        self.hint.setWordWrap(True)
        box.addWidget(self.title)
        box.addWidget(self.value)
        box.addWidget(self.hint)

    def set_content(self, value: str, hint: str) -> None:
        self.value.setText(value)
        self.value.setStyleSheet("")
        self.hint.setText(hint)

    def set_badge(self, value: str, fg: str, bg: str, hint: str) -> None:
        self.value.setText(value)
        self.value.setStyleSheet(f"color:{fg};background:{bg};border-radius:10px;padding:10px 12px;font:700 17px 'Segoe UI';")
        self.hint.setText(hint)


class RouteCard(QFrame):
    def __init__(self, check: ConnectivityCheck):
        super().__init__()
        self.setObjectName("RouteCard")
        ok = check.ok
        fg = "#1f7a4c" if ok else "#b44335"
        bg = "#d9f2e4" if ok else "#f9ddd8"
        text = "OK"
        if ok and check.status_code is not None:
            text += f" [{check.status_code}]"
        if ok and check.latency_ms is not None:
            text += f"  {check.latency_ms} мс"
        if not ok:
            text = check.error or "Нет доступа"

        row = QHBoxLayout(self)
        row.setContentsMargins(14, 12, 14, 12)
        info = QVBoxLayout()
        title = QLabel(check.name)
        title.setObjectName("RouteTitle")
        hint = QLabel(f"{format_host(check.url)}  |  {check.expected}")
        hint.setObjectName("RouteHint")
        hint.setWordWrap(True)
        info.addWidget(title)
        info.addWidget(hint)
        row.addLayout(info, 1)
        badge = QLabel(text)
        badge.setWordWrap(True)
        badge.setStyleSheet(f"color:{fg};background:{bg};border-radius:10px;padding:8px 12px;font:700 11pt 'Segoe UI';")
        row.addWidget(badge, 0, Qt.AlignTop)


class MainWindow(QMainWindow):
    def __init__(self, app: "VPNTrayApp"):
        super().__init__()
        self.app = app
        self.outbounds_data = {"outbounds": []}
        self.routing_data = {"routing": {"rules": []}}
        self._out_guard = False
        self._route_guard = False
        self.setWindowTitle("xKeen Control")
        self.resize(1400, 880)
        self.setMinimumSize(1180, 760)
        self._apply_styles()
        self._build_ui()
        self._setup_tray()
        self.startup_checkbox.setChecked(self.app.is_startup_enabled())
        self.editor_label.setText(self.app.get_notepadpp_path() or "системный редактор")
        self.temp_label.setText(TEMP_CONFIG_DIR)
        self.site_checks_path.setText(SITE_CHECKS_FILE)
        self.load_outbounds_tab()
        self.load_routing_tab()
        self.load_site_checks_tab()

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            "QMainWindow,QWidget{background:#f4efe6;color:#1f2937;font:10pt 'Segoe UI';}"
            "QFrame#Panel,QFrame#InfoCard,QFrame#RouteCard{background:#fbf7f0;border:1px solid #d8cbb4;border-radius:18px;}"
            "QLabel#HeroTitle{font:700 24pt 'Segoe UI';} QLabel#HeroSubtitle,QLabel#CardHint,QLabel#RouteHint,QLabel#Muted{font:9pt 'Segoe UI';color:#6b7280;}"
            "QLabel#Section{font:700 15pt 'Segoe UI';} QLabel#CardTitle{font:10pt 'Segoe UI';color:#6b7280;} QLabel#CardValue{font:700 16pt 'Segoe UI';}"
            "QLabel#RouteTitle{font:700 11pt 'Segoe UI';}"
            "QPushButton{border:none;border-radius:12px;padding:10px 14px;font:600 10pt 'Segoe UI';background:#d8edf5;color:#176b87;}"
            "QPushButton#Primary{background:#176b87;color:white;} QPushButton:disabled{background:#ebe5d9;color:#998f80;}"
            "QListWidget,QPlainTextEdit,QLineEdit,QTableWidget{background:#fffdfa;border:1px solid #d8cbb4;border-radius:12px;padding:6px;}"
            "QListWidget::item{padding:8px 10px;border-radius:8px;} QListWidget::item:selected{background:#176b87;color:white;}"
            "QTabBar::tab{background:#efe6d5;border:1px solid #d8cbb4;border-bottom:none;padding:10px 16px;border-top-left-radius:12px;border-top-right-radius:12px;margin-right:6px;}"
            "QTabBar::tab:selected{background:#fbf7f0;color:#176b87;}"
            "QPlainTextEdit#Diagnostics{background:#1e293b;color:#e5edf7;font:10.5pt 'Consolas';}"
        )

    def _build_ui(self) -> None:
        root_widget = QWidget()
        self.setCentralWidget(root_widget)
        root = QVBoxLayout(root_widget)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        hero = QFrame()
        hero.setObjectName("Panel")
        hero_l = QHBoxLayout(hero)
        hero_l.setContentsMargins(22, 18, 22, 18)
        txt = QVBoxLayout()
        t = QLabel("xKeen Control")
        t.setObjectName("HeroTitle")
        s = QLabel("Управление сервисом xkeen на роутере Keenetic")
        s.setObjectName("HeroSubtitle")
        txt.addWidget(t)
        txt.addWidget(s)
        hero_l.addLayout(txt, 1)
        self.refresh_button = QPushButton("Обновить")
        self.refresh_button.setObjectName("Primary")
        self.refresh_button.clicked.connect(self.app.refresh_async)
        self.settings_button = QPushButton("Настройки")
        self.settings_button.clicked.connect(self.show_settings)
        hero_l.addWidget(self.refresh_button)
        hero_l.addWidget(self.settings_button)
        root.addWidget(hero)

        self.main_tabs = QTabWidget()
        root.addWidget(self.main_tabs, 1)
        self.summary_tab = QWidget()
        self.settings_tab = QWidget()
        self.main_tabs.addTab(self.summary_tab, "Сводка")
        self.main_tabs.addTab(self.settings_tab, "Настройки")
        self._build_summary_tab()
        self._build_settings_tab()

    def _build_summary_tab(self) -> None:
        main = QHBoxLayout(self.summary_tab)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(16)
        left = QVBoxLayout()
        right = QVBoxLayout()
        main.addLayout(left, 7)
        main.addLayout(right, 5)

        metrics = QFrame()
        metrics.setObjectName("Panel")
        grid = QGridLayout(metrics)
        grid.setContentsMargins(18, 18, 18, 18)
        self.status_card = InfoCard("Состояние xkeen")
        self.uptime_card = InfoCard("Аптайм")
        self.load_card = InfoCard("Средняя нагрузка")
        self.cpu_card = InfoCard("Нагрузка xkeen")
        self.memory_card = InfoCard("RAM")
        grid.addWidget(self.status_card, 0, 0)
        grid.addWidget(self.uptime_card, 0, 1)
        grid.addWidget(self.load_card, 0, 2)
        grid.addWidget(self.cpu_card, 1, 0)
        grid.addWidget(self.memory_card, 1, 1, 1, 2)
        left.addWidget(metrics)

        actions = QFrame()
        actions.setObjectName("Panel")
        a_box = QVBoxLayout(actions)
        title = QLabel("Быстрые действия")
        title.setObjectName("Section")
        a_box.addWidget(title)
        row = QHBoxLayout()
        self.on_button = QPushButton("Включить")
        self.on_button.setObjectName("Primary")
        self.on_button.clicked.connect(self.app.action_on)
        self.off_button = QPushButton("Выключить")
        self.off_button.clicked.connect(self.app.action_off)
        self.restart_button = QPushButton("Перезапустить")
        self.restart_button.clicked.connect(self.app.action_restart)
        row.addWidget(self.on_button)
        row.addWidget(self.off_button)
        row.addWidget(self.restart_button)
        a_box.addLayout(row)
        left.addWidget(actions)

        diag = QFrame()
        diag.setObjectName("Panel")
        d_box = QVBoxLayout(diag)
        dt = QLabel("Диагностика роутера")
        dt.setObjectName("Section")
        self.diagnostics_text = QPlainTextEdit()
        self.diagnostics_text.setObjectName("Diagnostics")
        self.diagnostics_text.setReadOnly(True)
        self.diagnostics_text.setWordWrapMode(QTextOption.NoWrap)
        d_box.addWidget(dt)
        d_box.addWidget(self.diagnostics_text, 1)
        left.addWidget(diag, 1)

        routes = QFrame()
        routes.setObjectName("Panel")
        r_box = QVBoxLayout(routes)
        rt = QLabel("Маршруты и доступность")
        rt.setObjectName("Section")
        r_box.addWidget(rt)
        self.routes_container = QVBoxLayout()
        r_box.addLayout(self.routes_container)
        r_box.addStretch(1)
        right.addWidget(routes)

        cfg = QFrame()
        cfg.setObjectName("Panel")
        c_box = QVBoxLayout(cfg)
        ct = QLabel("Конфиги")
        ct.setObjectName("Section")
        hint = QLabel("Открытие файла через SSH -> temp -> редактор")
        hint.setObjectName("Muted")
        self.configs_list = QListWidget()
        self.configs_list.itemDoubleClicked.connect(lambda _: self.open_selected_config())
        buttons = QHBoxLayout()
        self.reload_configs_button = QPushButton("Обновить список")
        self.reload_configs_button.clicked.connect(self.app.reload_configs)
        self.open_config_button = QPushButton("Открыть в Notepad++")
        self.open_config_button.setObjectName("Primary")
        self.open_config_button.clicked.connect(self.open_selected_config)
        self.open_folder_button = QPushButton("Открыть temp")
        self.open_folder_button.clicked.connect(self.open_config_folder)
        buttons.addWidget(self.reload_configs_button)
        buttons.addWidget(self.open_config_button)
        buttons.addWidget(self.open_folder_button)
        c_box.addWidget(ct)
        c_box.addWidget(hint)
        c_box.addWidget(self.configs_list, 1)
        c_box.addLayout(buttons)
        right.addWidget(cfg, 1)

    def _build_settings_tab(self) -> None:
        root = QVBoxLayout(self.settings_tab)
        root.setContentsMargins(0, 0, 0, 0)
        self.settings_tabs = QTabWidget()
        root.addWidget(self.settings_tabs)
        self.general_tab = QWidget()
        self.outbounds_tab = QWidget()
        self.routing_tab = QWidget()
        self.site_checks_tab = QWidget()
        self.settings_tabs.addTab(self.general_tab, "Общие")
        self.settings_tabs.addTab(self.outbounds_tab, "04_outbounds")
        self.settings_tabs.addTab(self.routing_tab, "05_routing")
        self.settings_tabs.addTab(self.site_checks_tab, "Проверки сайтов")
        self._build_general_tab()
        self._build_outbounds_tab()
        self._build_routing_tab()
        self._build_site_checks_tab()

    def _build_general_tab(self) -> None:
        layout = QVBoxLayout(self.general_tab)
        panel = QFrame()
        panel.setObjectName("Panel")
        form = QFormLayout(panel)
        form.setContentsMargins(20, 20, 20, 20)
        self.startup_checkbox = QCheckBox("Запускать приложение вместе с Windows")
        self.editor_label = QLabel()
        self.editor_label.setWordWrap(True)
        self.temp_label = QLabel()
        self.temp_label.setWordWrap(True)
        self.site_checks_path = QLabel()
        self.site_checks_path.setWordWrap(True)
        form.addRow("Автозапуск", self.startup_checkbox)
        form.addRow("Редактор", self.editor_label)
        form.addRow("Temp папка", self.temp_label)
        form.addRow("Файл проверок", self.site_checks_path)
        btn = QPushButton("Сохранить")
        btn.setObjectName("Primary")
        btn.clicked.connect(self.save_general_settings)
        form.addRow(btn)
        layout.addWidget(panel)
        layout.addStretch(1)

    def _build_outbounds_tab(self) -> None:
        layout = QVBoxLayout(self.outbounds_tab)
        split = QSplitter()
        layout.addWidget(split, 1)
        left = QFrame(); left.setObjectName("Panel")
        l_box = QVBoxLayout(left); l_box.setContentsMargins(16, 16, 16, 16)
        self.outbounds_list = QListWidget()
        self.outbounds_list.currentRowChanged.connect(self.on_outbound_selected)
        l_box.addWidget(self.outbounds_list, 1)
        lr = QHBoxLayout()
        a = QPushButton("Добавить"); a.clicked.connect(self.add_outbound)
        d = QPushButton("Удалить"); d.clicked.connect(self.remove_outbound)
        lr.addWidget(a); lr.addWidget(d); l_box.addLayout(lr); split.addWidget(left)
        right = QFrame(); right.setObjectName("Panel")
        form = QFormLayout(right); form.setContentsMargins(20, 20, 20, 20)
        self.outbound_tag = QLineEdit(); self.outbound_protocol = QLineEdit(); self.outbound_address = QLineEdit()
        self.outbound_port = QLineEdit(); self.outbound_user_id = QLineEdit(); self.outbound_network = QLineEdit()
        self.outbound_security = QLineEdit(); self.outbound_public_key = QLineEdit(); self.outbound_fingerprint = QLineEdit()
        self.outbound_server_name = QLineEdit(); self.outbound_short_id = QLineEdit(); self.outbound_spider_x = QLineEdit()
        for w in (self.outbound_tag,self.outbound_protocol,self.outbound_address,self.outbound_port,self.outbound_user_id,self.outbound_network,self.outbound_security,self.outbound_public_key,self.outbound_fingerprint,self.outbound_server_name,self.outbound_short_id,self.outbound_spider_x):
            w.textChanged.connect(self.sync_outbound_form_to_model)
        form.addRow("Tag", self.outbound_tag); form.addRow("Protocol", self.outbound_protocol); form.addRow("Address", self.outbound_address)
        form.addRow("Port", self.outbound_port); form.addRow("User ID", self.outbound_user_id); form.addRow("Network", self.outbound_network)
        form.addRow("Security", self.outbound_security); form.addRow("Public key", self.outbound_public_key); form.addRow("Fingerprint", self.outbound_fingerprint)
        form.addRow("Server name", self.outbound_server_name); form.addRow("Short ID", self.outbound_short_id); form.addRow("Spider X", self.outbound_spider_x)
        row = QHBoxLayout(); r = QPushButton("Перечитать"); r.clicked.connect(self.load_outbounds_tab); s = QPushButton("Сохранить 04_outbounds"); s.setObjectName("Primary"); s.clicked.connect(self.save_outbounds_tab); row.addWidget(r); row.addWidget(s); form.addRow(row)
        split.addWidget(right); split.setSizes([320, 780])

    def _build_routing_tab(self) -> None:
        layout = QVBoxLayout(self.routing_tab)
        split = QSplitter()
        layout.addWidget(split, 1)
        left = QFrame(); left.setObjectName("Panel")
        l_box = QVBoxLayout(left); l_box.setContentsMargins(16, 16, 16, 16)
        self.routing_list = QListWidget()
        self.routing_list.currentRowChanged.connect(self.on_routing_selected)
        l_box.addWidget(self.routing_list, 1)
        lr = QHBoxLayout()
        a = QPushButton("Добавить"); a.clicked.connect(self.add_routing_rule)
        d = QPushButton("Удалить"); d.clicked.connect(self.remove_routing_rule)
        lr.addWidget(a); lr.addWidget(d); l_box.addLayout(lr); split.addWidget(left)
        right = QFrame(); right.setObjectName("Panel")
        form = QFormLayout(right); form.setContentsMargins(20, 20, 20, 20)
        self.rule_tag = QLineEdit(); self.rule_type = QLineEdit(); self.rule_outbound = QLineEdit(); self.rule_network = QLineEdit(); self.rule_port = QLineEdit()
        self.rule_inbound = QPlainTextEdit(); self.rule_domain = QPlainTextEdit(); self.rule_ip = QPlainTextEdit(); self.rule_protocol = QPlainTextEdit()
        for e in (self.rule_inbound,self.rule_domain,self.rule_ip,self.rule_protocol): e.setFixedHeight(90)
        for w in (self.rule_tag,self.rule_type,self.rule_outbound,self.rule_network,self.rule_port): w.textChanged.connect(self.sync_routing_form_to_model)
        for w in (self.rule_inbound,self.rule_domain,self.rule_ip,self.rule_protocol): w.textChanged.connect(self.sync_routing_form_to_model)
        form.addRow("Rule tag", self.rule_tag); form.addRow("Type", self.rule_type); form.addRow("Outbound tag", self.rule_outbound)
        form.addRow("Network", self.rule_network); form.addRow("Port", self.rule_port); form.addRow("Inbound tags", self.rule_inbound)
        form.addRow("Domains", self.rule_domain); form.addRow("IP", self.rule_ip); form.addRow("Protocol", self.rule_protocol)
        row = QHBoxLayout(); r = QPushButton("Перечитать"); r.clicked.connect(self.load_routing_tab); s = QPushButton("Сохранить 05_routing"); s.setObjectName("Primary"); s.clicked.connect(self.save_routing_tab); row.addWidget(r); row.addWidget(s); form.addRow(row)
        split.addWidget(right); split.setSizes([340, 760])

    def _build_site_checks_tab(self) -> None:
        layout = QVBoxLayout(self.site_checks_tab)
        panel = QFrame(); panel.setObjectName("Panel")
        box = QVBoxLayout(panel); box.setContentsMargins(18, 18, 18, 18)
        t = QLabel("Сайты для проверки"); t.setObjectName("Section")
        h = QLabel("Укажите сайт и ожидаемый outbound tag из 04_outbounds"); h.setObjectName("Muted")
        self.site_checks_table = QTableWidget(0, 3)
        self.site_checks_table.setHorizontalHeaderLabels(["Название", "URL", "Outbound"])
        self.site_checks_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.site_checks_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.site_checks_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        buttons = QHBoxLayout()
        a = QPushButton("Добавить"); a.clicked.connect(self.add_site_check_row)
        d = QPushButton("Удалить"); d.clicked.connect(self.remove_site_check_row)
        s = QPushButton("Сохранить проверки"); s.setObjectName("Primary"); s.clicked.connect(self.save_site_checks_tab)
        buttons.addWidget(a); buttons.addWidget(d); buttons.addWidget(s); buttons.addStretch(1)
        box.addWidget(t); box.addWidget(h); box.addWidget(self.site_checks_table, 1); box.addLayout(buttons)
        layout.addWidget(panel)

    def _setup_tray(self) -> None:
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setToolTip("xKeen Control")

    def show_main(self) -> None:
        self.main_tabs.setCurrentIndex(0)
        self.show(); self.raise_(); self.activateWindow()

    def show_settings(self) -> None:
        self.main_tabs.setCurrentIndex(1)
        self.show(); self.raise_(); self.activateWindow()

    def on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_main()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        event.ignore(); self.hide()

    def show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)

    def set_busy(self, busy: bool) -> None:
        for w in (self.refresh_button,self.settings_button,self.on_button,self.off_button,self.restart_button,self.reload_configs_button,self.open_config_button,self.open_folder_button):
            w.setDisabled(busy)

    def set_connection_state(self, ok: bool) -> None:
        self.status_card.hint.setText("Данные обновлены" if ok else "Ошибка SSH")

    def set_status_text(self, status: str) -> None:
        if status == "on":
            self.status_card.set_badge("ВКЛЮЧЕН", "#1f7a4c", "#d9f2e4", "Маршруты активны")
        elif status == "off":
            self.status_card.set_badge("ВЫКЛЮЧЕН", "#b44335", "#f9ddd8", "xkeen остановлен")
        else:
            self.status_card.set_badge("НЕИЗВЕСТНО", "#9a6700", "#f3e7c6", "Нет данных")

    def update_stats_cards(self, stats: RouterStats) -> None:
        self.uptime_card.set_content(stats.uptime, "Время работы роутера")
        self.load_card.set_content(stats.load_average, "Средняя нагрузка")
        self.cpu_card.set_content(stats.xray_cpu, "CPU процесса xkeen")
        self.memory_card.set_content(stats.memory, "Использовано / всего / свободно")
        self.diagnostics_text.setPlainText(stats.text)

    def update_connectivity_checks(self, checks: list[ConnectivityCheck]) -> None:
        while self.routes_container.count():
            item = self.routes_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not checks:
            self.routes_container.addWidget(QLabel("Нет данных по маршрутам"))
            return
        for check in checks:
            self.routes_container.addWidget(RouteCard(check))

    def update_configs(self, items: list[str]) -> None:
        self.configs_list.clear()
        icon_provider = QFileIconProvider()
        for item in items:
            widget_item = QListWidgetItem(item)
            if not item.startswith("["):
                widget_item.setIcon(icon_provider.icon(QFileIconProvider.File))
            self.configs_list.addItem(widget_item)

    def _get_selected_config_path(self) -> str | None:
        item = self.configs_list.currentItem()
        if not item or item.text().startswith("["):
            return None
        return os.path.join(XRAY_CONFIG_DIR, item.text())

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

    def save_general_settings(self) -> None:
        try:
            self.app.set_startup_enabled(self.startup_checkbox.isChecked())
            QMessageBox.information(self, "Настройки", "Сохранено.")
        except Exception as exc:
            self.show_error("Ошибка", f"Не удалось сохранить настройки:\n{exc}")

    def load_outbounds_tab(self) -> None:
        try:
            self.outbounds_data = self.app.load_outbounds_config()
        except Exception as exc:
            self.show_error("Ошибка", f"Не удалось загрузить 04_outbounds.json:\n{exc}")
            return
        self.outbounds_list.clear()
        for out in self.outbounds_data.get("outbounds", []):
            self.outbounds_list.addItem(f"{out.get('tag','<без tag>')} [{out.get('protocol','')}]")
        if self.outbounds_list.count():
            self.outbounds_list.setCurrentRow(0)
        else:
            self.clear_outbound_form()

    def clear_outbound_form(self) -> None:
        self._out_guard = True
        for w in (self.outbound_tag,self.outbound_protocol,self.outbound_address,self.outbound_port,self.outbound_user_id,self.outbound_network,self.outbound_security,self.outbound_public_key,self.outbound_fingerprint,self.outbound_server_name,self.outbound_short_id,self.outbound_spider_x):
            w.setText("")
        self._out_guard = False

    def on_outbound_selected(self, index: int) -> None:
        self._out_guard = True
        outs = self.outbounds_data.get("outbounds", [])
        if index < 0 or index >= len(outs):
            self.clear_outbound_form(); self._out_guard = False; return
        item = outs[index]
        vnext = (((item.get("settings") or {}).get("vnext") or [{}])[0]); users = vnext.get("users") or [{}]
        stream = item.get("streamSettings") or {}; reality = stream.get("realitySettings") or {}
        self.outbound_tag.setText(str(item.get("tag",""))); self.outbound_protocol.setText(str(item.get("protocol","")))
        self.outbound_address.setText(str(vnext.get("address",""))); self.outbound_port.setText("" if vnext.get("port") is None else str(vnext.get("port")))
        self.outbound_user_id.setText(str(users[0].get("id",""))); self.outbound_network.setText(str(stream.get("network",""))); self.outbound_security.setText(str(stream.get("security","")))
        self.outbound_public_key.setText(str(reality.get("publicKey",""))); self.outbound_fingerprint.setText(str(reality.get("fingerprint","")))
        self.outbound_server_name.setText(str(reality.get("serverName",""))); self.outbound_short_id.setText(str(reality.get("shortId",""))); self.outbound_spider_x.setText(str(reality.get("spiderX","")))
        self._out_guard = False

    def sync_outbound_form_to_model(self) -> None:
        if self._out_guard: return
        index = self.outbounds_list.currentRow(); outs = self.outbounds_data.get("outbounds", [])
        if index < 0 or index >= len(outs): return
        item = outs[index]; item["tag"] = self.outbound_tag.text().strip(); item["protocol"] = self.outbound_protocol.text().strip()
        settings = item.setdefault("settings", {}); vnext_list = settings.setdefault("vnext", [{}])
        if not vnext_list: vnext_list.append({})
        vnext = vnext_list[0]
        vnext["address"] = self.outbound_address.text().strip()
        port_text = self.outbound_port.text().strip()
        if port_text:
            try: vnext["port"] = int(port_text)
            except ValueError: vnext["port"] = port_text
        users = vnext.setdefault("users", [{}])
        if not users: users.append({})
        user = users[0]
        user["id"] = self.outbound_user_id.text().strip(); user.setdefault("flow",""); user.setdefault("encryption","none"); user.setdefault("level",0)
        stream = item.setdefault("streamSettings", {}); stream["network"] = self.outbound_network.text().strip(); stream["security"] = self.outbound_security.text().strip()
        reality = stream.setdefault("realitySettings", {})
        reality["publicKey"] = self.outbound_public_key.text().strip(); reality["fingerprint"] = self.outbound_fingerprint.text().strip(); reality["serverName"] = self.outbound_server_name.text().strip(); reality["shortId"] = self.outbound_short_id.text().strip(); reality["spiderX"] = self.outbound_spider_x.text().strip()
        current = self.outbounds_list.currentItem()
        if current: current.setText(f"{item.get('tag','<без tag>')} [{item.get('protocol','')}]")

    def add_outbound(self) -> None:
        self.outbounds_data.setdefault("outbounds", []).append({"tag":"NEW","protocol":"vless","settings":{"vnext":[{"address":"","port":443,"users":[{"id":"","flow":"","encryption":"none","level":0}]}]},"streamSettings":{"network":"tcp","security":"reality","realitySettings":{"publicKey":"","fingerprint":"chrome","serverName":"","shortId":"","spiderX":"/"}}})
        self.outbounds_list.addItem("NEW [vless]"); self.outbounds_list.setCurrentRow(self.outbounds_list.count()-1)

    def remove_outbound(self) -> None:
        index = self.outbounds_list.currentRow()
        if index < 0: return
        self.outbounds_data["outbounds"].pop(index); self.outbounds_list.takeItem(index)
        if self.outbounds_list.count(): self.outbounds_list.setCurrentRow(min(index, self.outbounds_list.count()-1))
        else: self.clear_outbound_form()

    def save_outbounds_tab(self) -> None:
        try:
            self.sync_outbound_form_to_model(); self.app.save_outbounds_config(self.outbounds_data); QMessageBox.information(self, "Сохранено", "04_outbounds.json обновлён."); self.app.refresh_async()
        except Exception as exc:
            self.show_error("Ошибка", f"Не удалось сохранить 04_outbounds.json:\n{exc}")

    def load_routing_tab(self) -> None:
        try:
            self.routing_data = self.app.load_routing_config()
        except Exception as exc:
            self.show_error("Ошибка", f"Не удалось загрузить 05_routing.json:\n{exc}")
            return
        self.routing_list.clear()
        for rule in self.routing_data.get("routing", {}).get("rules", []):
            self.routing_list.addItem(rule.get("ruleTag") or rule.get("outboundTag") or "rule")
        if self.routing_list.count():
            self.routing_list.setCurrentRow(0)
        else:
            self.clear_routing_form()

    def clear_routing_form(self) -> None:
        self._route_guard = True
        self.rule_tag.setText(""); self.rule_type.setText(""); self.rule_outbound.setText(""); self.rule_network.setText(""); self.rule_port.setText("")
        self.rule_inbound.setPlainText(""); self.rule_domain.setPlainText(""); self.rule_ip.setPlainText(""); self.rule_protocol.setPlainText("")
        self._route_guard = False

    def on_routing_selected(self, index: int) -> None:
        self._route_guard = True
        rules = self.routing_data.get("routing", {}).get("rules", [])
        if index < 0 or index >= len(rules):
            self.clear_routing_form(); self._route_guard = False; return
        rule = rules[index]
        self.rule_tag.setText(str(rule.get("ruleTag",""))); self.rule_type.setText(str(rule.get("type",""))); self.rule_outbound.setText(str(rule.get("outboundTag","")))
        self.rule_network.setText(str(rule.get("network",""))); self.rule_port.setText(str(rule.get("port","")))
        self.rule_inbound.setPlainText("\n".join(rule.get("inboundTag", []))); self.rule_domain.setPlainText("\n".join(rule.get("domain", []))); self.rule_ip.setPlainText("\n".join(rule.get("ip", []))); self.rule_protocol.setPlainText("\n".join(rule.get("protocol", [])))
        self._route_guard = False

    def _lines(self, text: str) -> list[str]:
        return [line.strip() for line in text.splitlines() if line.strip()]

    def sync_routing_form_to_model(self) -> None:
        if self._route_guard: return
        index = self.routing_list.currentRow(); rules = self.routing_data.get("routing", {}).get("rules", [])
        if index < 0 or index >= len(rules): return
        rule = rules[index]; rule["ruleTag"] = self.rule_tag.text().strip(); rule["type"] = self.rule_type.text().strip() or "field"; rule["outboundTag"] = self.rule_outbound.text().strip()
        for key, value in (("network", self.rule_network.text().strip()), ("port", self.rule_port.text().strip())):
            if value: rule[key] = value
            else: rule.pop(key, None)
        for key, value in (("inboundTag", self._lines(self.rule_inbound.toPlainText())), ("domain", self._lines(self.rule_domain.toPlainText())), ("ip", self._lines(self.rule_ip.toPlainText())), ("protocol", self._lines(self.rule_protocol.toPlainText()))):
            if value: rule[key] = value
            else: rule.pop(key, None)
        current = self.routing_list.currentItem()
        if current: current.setText(rule.get("ruleTag") or rule.get("outboundTag") or "rule")

    def add_routing_rule(self) -> None:
        self.routing_data.setdefault("routing", {}).setdefault("rules", []).append({"type":"field","ruleTag":"new_rule","inboundTag":["redirect","tproxy"],"domain":[],"outboundTag":"direct"})
        self.routing_list.addItem("new_rule"); self.routing_list.setCurrentRow(self.routing_list.count()-1)

    def remove_routing_rule(self) -> None:
        index = self.routing_list.currentRow()
        if index < 0: return
        self.routing_data["routing"]["rules"].pop(index); self.routing_list.takeItem(index)
        if self.routing_list.count(): self.routing_list.setCurrentRow(min(index, self.routing_list.count()-1))
        else: self.clear_routing_form()

    def save_routing_tab(self) -> None:
        try:
            self.sync_routing_form_to_model(); self.app.save_routing_config(self.routing_data); QMessageBox.information(self, "Сохранено", "05_routing.json обновлён."); self.app.refresh_async()
        except Exception as exc:
            self.show_error("Ошибка", f"Не удалось сохранить 05_routing.json:\n{exc}")

    def load_site_checks_tab(self) -> None:
        self.site_checks_table.setRowCount(0)
        for item in self.app.load_site_checks():
            row = self.site_checks_table.rowCount(); self.site_checks_table.insertRow(row)
            self.site_checks_table.setItem(row, 0, QTableWidgetItem(item.get("name","")))
            self.site_checks_table.setItem(row, 1, QTableWidgetItem(item.get("url","")))
            self.site_checks_table.setItem(row, 2, QTableWidgetItem(item.get("expected","")))

    def add_site_check_row(self) -> None:
        row = self.site_checks_table.rowCount(); self.site_checks_table.insertRow(row)
        self.site_checks_table.setItem(row, 0, QTableWidgetItem("Новый сайт"))
        self.site_checks_table.setItem(row, 1, QTableWidgetItem("https://example.com"))
        self.site_checks_table.setItem(row, 2, QTableWidgetItem("GE"))

    def remove_site_check_row(self) -> None:
        row = self.site_checks_table.currentRow()
        if row >= 0: self.site_checks_table.removeRow(row)

    def save_site_checks_tab(self) -> None:
        checks = []
        for row in range(self.site_checks_table.rowCount()):
            name_item = self.site_checks_table.item(row, 0); url_item = self.site_checks_table.item(row, 1); out_item = self.site_checks_table.item(row, 2)
            name = name_item.text().strip() if name_item else ""; url = url_item.text().strip() if url_item else ""; expected = out_item.text().strip() if out_item else ""
            if name and url: checks.append({"name": name, "url": url, "expected": expected or "direct"})
        try:
            self.app.save_site_checks(checks); QMessageBox.information(self, "Сохранено", "Проверки сайтов обновлены."); self.app.refresh_async()
        except Exception as exc:
            self.show_error("Ошибка", f"Не удалось сохранить проверки сайтов:\n{exc}")
