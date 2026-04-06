import os
import subprocess
import threading
from typing import TYPE_CHECKING, Optional

import tkinter as tk
from tkinter import messagebox, ttk

from config import APP_ICON_ICO, SMB_HOST, SMB_PASS, SMB_USER, XRAY_CONFIG_DIR, format_host
from models import ConnectivityCheck, RouterStats

if TYPE_CHECKING:
    from app import VPNTrayApp


class StatsWindow:
    BG = "#f4efe6"
    PANEL = "#fbf7f0"
    PANEL_ALT = "#efe6d5"
    INK = "#1f2937"
    MUTED = "#6b7280"
    BORDER = "#d8cbb4"
    ACCENT = "#176b87"
    ACCENT_SOFT = "#d8edf5"
    SUCCESS = "#1f7a4c"
    SUCCESS_SOFT = "#d9f2e4"
    DANGER = "#b44335"
    DANGER_SOFT = "#f9ddd8"
    WARN = "#9a6700"
    WARN_SOFT = "#f3e7c6"
    MONO_BG = "#1e293b"
    MONO_FG = "#e5edf7"

    def __init__(self, app: "VPNTrayApp"):
        self.app = app
        self.root = tk.Tk()
        self.root.title("Управление xkeen")
        self.root.geometry("1220x780")
        self.root.minsize(1080, 700)
        self.root.configure(bg=self.BG)

        if os.path.isfile(APP_ICON_ICO):
            try:
                self.root.iconbitmap(APP_ICON_ICO)
            except Exception:
                pass

        self.root.protocol("WM_DELETE_WINDOW", self.hide)
        self.root.withdraw()

        self.settings_window: Optional[tk.Toplevel] = None
        self.startup_var: Optional[tk.BooleanVar] = None
        self._auto_refresh_job: Optional[str] = None

        self._configure_styles()
        self._build_ui()
        self._update_editor_info()

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure(
            "Card.TFrame",
            background=self.PANEL,
            relief="flat",
            borderwidth=0,
        )
        style.configure(
            "PanelAlt.TFrame",
            background=self.PANEL_ALT,
            relief="flat",
            borderwidth=0,
        )
        style.configure(
            "Primary.TButton",
            font=("Bahnschrift SemiBold", 10),
            padding=(16, 10),
        )
        style.configure(
            "Secondary.TButton",
            font=("Bahnschrift SemiBold", 10),
            padding=(14, 10),
        )
        style.configure(
            "Ghost.TButton",
            font=("Bahnschrift", 10),
            padding=(14, 10),
        )

    def _create_card(self, parent: tk.Widget, bg: str, padx: int = 18, pady: int = 18) -> tk.Frame:
        outer = tk.Frame(parent, bg=self.BORDER, bd=0, highlightthickness=0)
        inner = tk.Frame(outer, bg=bg, bd=0, highlightthickness=0)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        inner.configure(padx=padx, pady=pady)
        return outer

    def start_auto_refresh(self) -> None:
        if self._auto_refresh_job:
            self.root.after_cancel(self._auto_refresh_job)
        self._auto_refresh()

    def _auto_refresh(self) -> None:
        if not self.root.winfo_viewable():
            self._auto_refresh_job = None
            return
        self.refresh_async()
        self._auto_refresh_job = self.root.after(10000, self._auto_refresh)

    def ensure_smb_connected(self) -> None:
        try:
            subprocess.run(
                ["net", "use", SMB_HOST, f"/user:{SMB_USER}", SMB_PASS],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        header_wrap = tk.Frame(self.root, bg=self.BG, padx=20, pady=20)
        header_wrap.grid(row=0, column=0, sticky="ew")
        header_wrap.columnconfigure(0, weight=1)
        header_wrap.columnconfigure(1, weight=1)

        header = self._create_card(header_wrap, self.PANEL_ALT, padx=22, pady=20)
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        header.columnconfigure(0, weight=1)
        header.columnconfigure(1, weight=0)
        header_inner = header.winfo_children()[0]
        header_inner.columnconfigure(0, weight=1)
        header_inner.columnconfigure(1, weight=0)

        title_block = tk.Frame(header_inner, bg=self.PANEL_ALT)
        title_block.grid(row=0, column=0, sticky="w")

        tk.Label(
            title_block,
            text="Управление xkeen",
            bg=self.PANEL_ALT,
            fg=self.INK,
            font=("Bahnschrift SemiBold", 24),
        ).pack(anchor="w")
        tk.Label(
            title_block,
            text="Keenetic, маршруты и конфиги",
            bg=self.PANEL_ALT,
            fg=self.MUTED,
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(4, 0))

        header_actions = tk.Frame(header_inner, bg=self.PANEL_ALT)
        header_actions.grid(row=0, column=1, sticky="e")

        self.btn_refresh = ttk.Button(header_actions, text="Обновить", command=self.refresh_async, style="Primary.TButton")
        self.btn_refresh.grid(row=0, column=0, padx=(0, 8))

        self.btn_settings = ttk.Button(header_actions, text="Настройки", command=self.show_settings, style="Ghost.TButton")
        self.btn_settings.grid(row=0, column=1)

        content = tk.Frame(self.root, bg=self.BG, padx=20, pady=0)
        content.grid(row=1, column=0, sticky="nsew", pady=(0, 20))
        content.columnconfigure(0, weight=7)
        content.columnconfigure(1, weight=5)
        content.rowconfigure(0, weight=1)

        left = tk.Frame(content, bg=self.BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(2, weight=1)

        right = tk.Frame(content, bg=self.BG)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        right.rowconfigure(3, weight=1)

        cards_row = tk.Frame(left, bg=self.BG)
        cards_row.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        for index in range(3):
            cards_row.columnconfigure(index, weight=1)
        for index in range(2):
            cards_row.rowconfigure(index, weight=1)

        status_card = self._create_card(cards_row, self.PANEL, padx=20, pady=18)
        status_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=(0, 10))
        status_inner = status_card.winfo_children()[0]
        status_inner.columnconfigure(0, weight=1)

        tk.Label(
            status_inner,
            text="Состояние VPN",
            bg=self.PANEL,
            fg=self.MUTED,
            font=("Segoe UI", 10),
        ).grid(row=0, column=0, sticky="w")

        self.status_badge = tk.Label(
            status_inner,
            text="НЕИЗВЕСТНО",
            bg=self.WARN_SOFT,
            fg=self.WARN,
            font=("Bahnschrift SemiBold", 18),
            padx=14,
            pady=8,
        )
        self.status_badge.grid(row=1, column=0, sticky="w", pady=(10, 8))

        self.status_hint = tk.Label(
            status_inner,
            text="Ожидаем данные от роутера",
            bg=self.PANEL,
            fg=self.MUTED,
            font=("Segoe UI", 9),
            wraplength=190,
            justify="left",
        )
        self.status_hint.grid(row=2, column=0, sticky="w")

        self.uptime_value, self.uptime_hint = self._build_metric_card(cards_row, 0, 1, "Аптайм", padx=(0, 10), pady=(0, 10), wraplength=220)
        self.load_value, self.load_hint = self._build_metric_card(cards_row, 0, 2, "Средняя нагрузка", pady=(0, 10), wraplength=220)
        self.cpu_value, self.cpu_hint = self._build_metric_card(cards_row, 1, 0, "Нагрузка xray", padx=(0, 10), wraplength=220)
        self.memory_value, self.memory_hint = self._build_metric_card(cards_row, 1, 1, "RAM", columnspan=2, wraplength=460)

        actions_card = self._create_card(left, self.PANEL, padx=20, pady=18)
        actions_card.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        actions_inner = actions_card.winfo_children()[0]
        for index in range(3):
            actions_inner.columnconfigure(index, weight=1)

        tk.Label(
            actions_inner,
            text="Быстрые действия",
            bg=self.PANEL,
            fg=self.INK,
            font=("Bahnschrift SemiBold", 14),
        ).grid(row=0, column=0, columnspan=3, sticky="w")

        tk.Label(
            actions_inner,
            text="Запуск, остановка и мягкий рестарт сервиса на роутере",
            bg=self.PANEL,
            fg=self.MUTED,
            font=("Segoe UI", 10),
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(3, 14))

        self.btn_vpn_on = ttk.Button(actions_inner, text="Включить VPN", command=self.vpn_on_async, style="Primary.TButton")
        self.btn_vpn_on.grid(row=2, column=0, sticky="ew", padx=(0, 8))

        self.btn_vpn_off = ttk.Button(actions_inner, text="Выключить VPN", command=self.vpn_off_async, style="Secondary.TButton")
        self.btn_vpn_off.grid(row=2, column=1, sticky="ew", padx=4)

        self.btn_vpn_restart = ttk.Button(actions_inner, text="Перезапустить", command=self.vpn_restart_async, style="Secondary.TButton")
        self.btn_vpn_restart.grid(row=2, column=2, sticky="ew", padx=(8, 0))

        console_card = self._create_card(left, self.PANEL, padx=0, pady=0)
        console_card.grid(row=2, column=0, sticky="nsew")
        console_inner = console_card.winfo_children()[0]
        console_inner.columnconfigure(0, weight=1)
        console_inner.rowconfigure(1, weight=1)

        console_head = tk.Frame(console_inner, bg=self.PANEL, padx=20, pady=16)
        console_head.grid(row=0, column=0, sticky="ew")
        console_head.columnconfigure(0, weight=1)

        tk.Label(
            console_head,
            text="Диагностика роутера",
            bg=self.PANEL,
            fg=self.INK,
            font=("Bahnschrift SemiBold", 14),
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            console_head,
            text="Аптайм, нагрузка xray и оперативная память",
            bg=self.PANEL,
            fg=self.MUTED,
            font=("Segoe UI", 10),
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))

        text_wrap = tk.Frame(console_inner, bg=self.MONO_BG, padx=18, pady=18)
        text_wrap.grid(row=1, column=0, sticky="nsew")
        text_wrap.columnconfigure(0, weight=1)
        text_wrap.rowconfigure(0, weight=1)

        self.text = tk.Text(
            text_wrap,
            wrap="none",
            bg=self.MONO_BG,
            fg=self.MONO_FG,
            insertbackground=self.MONO_FG,
            relief="flat",
            bd=0,
            highlightthickness=0,
            font=("Consolas", 11),
            padx=4,
            pady=4,
        )
        self.text.grid(row=0, column=0, sticky="nsew")

        yscroll = ttk.Scrollbar(text_wrap, orient="vertical", command=self.text.yview)
        yscroll.grid(row=0, column=1, sticky="ns")
        self.text.configure(yscrollcommand=yscroll.set)

        checks_card = self._create_card(right, self.PANEL, padx=20, pady=18)
        checks_card.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        checks_inner = checks_card.winfo_children()[0]
        checks_inner.columnconfigure(0, weight=1)

        tk.Label(
            checks_inner,
            text="Маршруты и доступность",
            bg=self.PANEL,
            fg=self.INK,
            font=("Bahnschrift SemiBold", 14),
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            checks_inner,
            text="Проверяем прямой трафик, RU-маршрут и NL-маршрут",
            bg=self.PANEL,
            fg=self.MUTED,
            font=("Segoe UI", 10),
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        self.checks_frame = tk.Frame(checks_inner, bg=self.PANEL)
        self.checks_frame.grid(row=2, column=0, sticky="ew", pady=(16, 0))
        self.checks_frame.columnconfigure(0, weight=1)

        configs_card = self._create_card(right, self.PANEL, padx=0, pady=0)
        configs_card.grid(row=1, column=0, sticky="nsew")
        configs_inner = configs_card.winfo_children()[0]
        configs_inner.columnconfigure(0, weight=1)
        configs_inner.rowconfigure(2, weight=1)

        configs_head = tk.Frame(configs_inner, bg=self.PANEL, padx=20, pady=16)
        configs_head.grid(row=0, column=0, sticky="ew")
        configs_head.columnconfigure(0, weight=1)

        tk.Label(
            configs_head,
            text="XRAY configs",
            bg=self.PANEL,
            fg=self.INK,
            font=("Bahnschrift SemiBold", 14),
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            configs_head,
            text="Файлы из каталога `/opt/etc/xray/configs` через SMB",
            bg=self.PANEL,
            fg=self.MUTED,
            font=("Segoe UI", 10),
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))

        self.btn_reload_cfg = ttk.Button(configs_head, text="Обновить список", command=self.reload_configs, style="Ghost.TButton")
        self.btn_reload_cfg.grid(row=0, column=1, rowspan=2, sticky="e")

        list_wrap = tk.Frame(configs_inner, bg=self.PANEL, padx=20, pady=0)
        list_wrap.grid(row=2, column=0, sticky="nsew", pady=(0, 16))
        list_wrap.columnconfigure(0, weight=1)
        list_wrap.rowconfigure(0, weight=1)

        self.cfg_list = tk.Listbox(
            list_wrap,
            bg="#fffdfa",
            fg=self.INK,
            selectbackground=self.ACCENT,
            selectforeground="white",
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=self.BORDER,
            font=("Segoe UI", 11),
            activestyle="none",
        )
        self.cfg_list.grid(row=0, column=0, sticky="nsew")
        self.cfg_list.bind("<Double-Button-1>", lambda _event: self.open_selected_config())

        cfg_scroll = ttk.Scrollbar(list_wrap, orient="vertical", command=self.cfg_list.yview)
        cfg_scroll.grid(row=0, column=1, sticky="ns")
        self.cfg_list.configure(yscrollcommand=cfg_scroll.set)

        cfg_btns = tk.Frame(configs_inner, bg=self.PANEL, padx=20, pady=0)
        cfg_btns.grid(row=3, column=0, sticky="ew", pady=(0, 20))
        cfg_btns.columnconfigure(0, weight=1)
        cfg_btns.columnconfigure(1, weight=1)

        self.btn_open_cfg = ttk.Button(cfg_btns, text="Открыть в Notepad++", command=self.open_selected_config, style="Primary.TButton")
        self.btn_open_cfg.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self.btn_open_folder = ttk.Button(cfg_btns, text="Открыть папку", command=self.open_config_folder, style="Secondary.TButton")
        self.btn_open_folder.grid(row=0, column=1, sticky="ew", padx=(8, 0))

    def _update_editor_info(self) -> None:
        editor_path = self.app.get_notepadpp_path()
        if editor_path:
            editor_name = "Notepad++"
        else:
            editor_name = "Системный редактор"
        self.root.title(f"Управление xkeen [{editor_name}]")

    def _build_metric_card(
        self,
        parent: tk.Widget,
        row: int,
        column: int,
        title: str,
        padx: tuple[int, int] = (0, 0),
        pady: tuple[int, int] = (0, 0),
        columnspan: int = 1,
        wraplength: int = 180,
    ) -> tuple[tk.Label, tk.Label]:
        card = self._create_card(parent, self.PANEL, padx=18, pady=18)
        card.grid(row=row, column=column, columnspan=columnspan, sticky="nsew", padx=padx, pady=pady)
        inner = card.winfo_children()[0]

        tk.Label(
            inner,
            text=title,
            bg=self.PANEL,
            fg=self.MUTED,
            font=("Segoe UI", 10),
        ).pack(anchor="w")
        value = tk.Label(
            inner,
            text="...",
            bg=self.PANEL,
            fg=self.INK,
            font=("Bahnschrift SemiBold", 14),
            justify="left",
            wraplength=wraplength,
        )
        value.pack(anchor="w", pady=(10, 6))
        hint = tk.Label(
            inner,
            text="Ожидание данных",
            bg=self.PANEL,
            fg=self.MUTED,
            font=("Segoe UI", 9),
            justify="left",
            wraplength=wraplength,
        )
        hint.pack(anchor="w")
        return value, hint

    def update_stats_cards(self, stats: RouterStats) -> None:
        self.uptime_value.config(text=stats.uptime)
        self.uptime_hint.config(text="Время работы")

        self.load_value.config(text=stats.load_average)
        self.load_hint.config(text="Средняя нагрузка")

        self.cpu_value.config(text=stats.xray_cpu)
        self.cpu_hint.config(text="CPU процесса")

        self.memory_value.config(text=stats.memory)
        self.memory_hint.config(text="использовано / всего / свободно")

    def _add_check_card(self, parent: tk.Widget, check: ConnectivityCheck) -> None:
        if check.ok:
            tone_bg = self.SUCCESS_SOFT
            tone_fg = self.SUCCESS
            state_text = "OK"
            if check.status_code is not None:
                state_text += f" [{check.status_code}]"
            if check.latency_ms is not None:
                state_text += f"  {check.latency_ms} ms"
        else:
            tone_bg = self.DANGER_SOFT
            tone_fg = self.DANGER
            state_text = check.error or "Нет доступа"

        row = tk.Frame(parent, bg=self.PANEL)
        row.pack(fill="x", pady=(0, 10))
        row.columnconfigure(0, weight=1)
        row.columnconfigure(1, weight=0)

        info = tk.Frame(row, bg=self.PANEL)
        info.grid(row=0, column=0, sticky="w")

        tk.Label(
            info,
            text=check.name,
            bg=self.PANEL,
            fg=self.INK,
            font=("Bahnschrift SemiBold", 12),
        ).pack(anchor="w")
        tk.Label(
            info,
            text=f"{format_host(check.url)}  |  {check.expected}",
            bg=self.PANEL,
            fg=self.MUTED,
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(2, 0))

        tk.Label(
            row,
            text=state_text,
            bg=tone_bg,
            fg=tone_fg,
            font=("Bahnschrift SemiBold", 11),
            padx=12,
            pady=8,
        ).grid(row=0, column=1, sticky="e", padx=(12, 0))

    def show(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.start_auto_refresh()

    def hide(self) -> None:
        if self._auto_refresh_job:
            self.root.after_cancel(self._auto_refresh_job)
            self._auto_refresh_job = None
        self.root.withdraw()

    def set_connection_state(self, ok: bool) -> None:
        if ok:
            self.status_hint.config(text="Данные обновлены")
        else:
            self.status_hint.config(text="Ошибка SSH")

    def set_status_text(self, status: str) -> None:
        if status == "on":
            badge_text = "ВКЛЮЧЕН"
            badge_bg = self.SUCCESS_SOFT
            badge_fg = self.SUCCESS
            hint = "Маршруты активны"
        elif status == "off":
            badge_text = "ВЫКЛЮЧЕН"
            badge_bg = self.DANGER_SOFT
            badge_fg = self.DANGER
            hint = "xkeen остановлен"
        else:
            badge_text = "НЕИЗВЕСТНО"
            badge_bg = self.WARN_SOFT
            badge_fg = self.WARN
            hint = "Нет данных"

        self.status_badge.config(text=badge_text, bg=badge_bg, fg=badge_fg)
        self.status_hint.config(text=hint)

    def set_text(self, text: str) -> None:
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)

    def set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        for button in (
            self.btn_refresh,
            self.btn_vpn_on,
            self.btn_vpn_off,
            self.btn_vpn_restart,
            self.btn_settings,
            self.btn_reload_cfg,
            self.btn_open_cfg,
            self.btn_open_folder,
        ):
            button.config(state=state)

    def update_connectivity_checks(self, checks: list[ConnectivityCheck]) -> None:
        for child in self.checks_frame.winfo_children():
            child.destroy()

        if not checks:
            tk.Label(
                self.checks_frame,
                text="Нет данных по маршрутам",
                bg=self.PANEL,
                fg=self.MUTED,
                font=("Segoe UI", 10),
            ).pack(anchor="w")
            return

        for check in checks:
            self._add_check_card(self.checks_frame, check)

    def refresh_async(self) -> None:
        def worker() -> None:
            try:
                self.root.after(0, lambda: self.set_busy(True))
                stats = self.app.get_router_stats()
                status = self.app.get_status()
                checks = self.app.get_connectivity_checks()
                self.root.after(0, lambda: self.set_status_text(status))
                self.root.after(0, lambda: self.set_connection_state(True))
                self.root.after(0, lambda: self.update_stats_cards(stats))
                self.root.after(0, lambda: self.set_text(stats.text))
                self.root.after(0, lambda: self.update_connectivity_checks(checks))
            except Exception as e:
                self.root.after(0, lambda: self.set_connection_state(False))
                self.root.after(0, lambda: self.set_text(f"Ошибка обновления:\n{e}"))
            finally:
                self.root.after(0, lambda: self.set_busy(False))

        threading.Thread(target=worker, daemon=True).start()

    def _run_vpn_action(self, action, action_name: str) -> None:
        def worker() -> None:
            try:
                self.root.after(0, lambda: self.set_busy(True))
                action()
                status = self.app.get_status()
                self.app.update_icon_status(status)
                self.root.after(0, lambda: self.set_status_text(status))
                self.root.after(0, self.refresh_async)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Ошибка", f"{action_name} не выполнен:\n{e}"))
            finally:
                self.root.after(0, lambda: self.set_busy(False))

        threading.Thread(target=worker, daemon=True).start()

    def vpn_on_async(self) -> None:
        self._run_vpn_action(self.app.vpn_on, "Запуск VPN")

    def vpn_off_async(self) -> None:
        self._run_vpn_action(self.app.vpn_off, "Остановка VPN")

    def vpn_restart_async(self) -> None:
        self._run_vpn_action(self.app.vpn_restart, "Перезапуск VPN")

    def reload_configs(self) -> None:
        self.cfg_list.delete(0, "end")
        try:
            if not os.path.isdir(XRAY_CONFIG_DIR):
                self.cfg_list.insert("end", f"[нет доступа] {XRAY_CONFIG_DIR}")
                return

            files = [f for f in os.listdir(XRAY_CONFIG_DIR) if f.lower().endswith(".json")]
            files.sort(key=str.lower)
            for file_name in files:
                self.cfg_list.insert("end", file_name)

            if not files:
                self.cfg_list.insert("end", "[пусто]")
        except Exception as e:
            self.cfg_list.insert("end", f"[ошибка] {e}")

    def _get_selected_config_path(self) -> Optional[str]:
        selected = self.cfg_list.curselection()
        if not selected:
            return None
        name = self.cfg_list.get(selected[0])
        if name.startswith("["):
            return None
        return os.path.join(XRAY_CONFIG_DIR, name)

    def open_selected_config(self) -> None:
        path = self._get_selected_config_path()
        if not path:
            return

        try:
            self.app.run_config_editor(path)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось открыть файл:\n{e}")

    def open_config_folder(self) -> None:
        try:
            os.startfile(XRAY_CONFIG_DIR)
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def show_settings(self) -> None:
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.lift()
            self.settings_window.focus_force()
            return

        win = tk.Toplevel(self.root)
        win.title("Настройки")
        win.geometry("500x280")
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()
        win.configure(bg=self.BG)
        self.settings_window = win

        card = self._create_card(win, self.PANEL, padx=20, pady=18)
        card.pack(fill="both", expand=True, padx=18, pady=18)
        frame = card.winfo_children()[0]

        tk.Label(
            frame,
            text="Настройки приложения",
            bg=self.PANEL,
            fg=self.INK,
            font=("Bahnschrift SemiBold", 16),
        ).pack(anchor="w")
        tk.Label(
            frame,
            text="Параметры запуска и текущий редактор конфигов",
            bg=self.PANEL,
            fg=self.MUTED,
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(4, 18))

        startup_enabled = self.app.is_startup_enabled()
        self.startup_var = tk.BooleanVar(value=startup_enabled)

        chk = tk.Checkbutton(
            frame,
            text="Запускать приложение вместе с Windows",
            variable=self.startup_var,
            bg=self.PANEL,
            fg=self.INK,
            activebackground=self.PANEL,
            activeforeground=self.INK,
            selectcolor=self.PANEL,
            font=("Segoe UI", 10),
        )
        chk.pack(anchor="w", pady=(0, 14))

        editor_path = self.app.get_notepadpp_path() or "Notepad++ не найден, будет использовано системное приложение"
        tk.Label(
            frame,
            text=f"Редактор: {editor_path}",
            bg=self.PANEL,
            fg=self.MUTED,
            wraplength=420,
            justify="left",
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(0, 18))

        btns = tk.Frame(frame, bg=self.PANEL)
        btns.pack(fill="x", side="bottom")
        btns.columnconfigure(0, weight=1)

        ttk.Button(btns, text="Отмена", command=win.destroy, style="Ghost.TButton").grid(row=0, column=1, padx=(0, 8))
        ttk.Button(btns, text="Сохранить", command=self.save_settings, style="Primary.TButton").grid(row=0, column=2)

    def save_settings(self) -> None:
        if self.startup_var is None:
            return

        try:
            self.app.set_startup_enabled(bool(self.startup_var.get()))
            messagebox.showinfo("Настройки", "Сохранено.")
            if self.settings_window and self.settings_window.winfo_exists():
                self.settings_window.destroy()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить настройки:\n{e}")
