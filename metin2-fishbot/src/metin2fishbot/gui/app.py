"""Main CustomTkinter application window with tabbed UI.

Tabs: Balık (run control) · Balıklar (fish keep/burn) · Sohbet AI · Ayarlar ·
Kalibrasyon · Log. Wires the GUI to the FishingBot and ChatWatcher and routes
EventBus log/state events into the UI.
"""
from __future__ import annotations

import customtkinter as ctk

from ..bot.fishing_bot import FishingBot
from ..core.capture import create_capture
from ..core.config import Config, save_profile
from ..core.events import Event, EventBus
from ..core.input_controller import InputController
from ..fish.catalog import FishCatalog
from ..fish.disposer import FishDisposer
from ..fish.manager import FishManager
from ..fish.recognizer import FishRecognizer
from .calibration import CalibrationTab
from .chat_panel import ChatPanelTab
from .fish_picker import FishPickerTab
from .widgets import LabeledEntry, LogView

SYSTEMS = ["auto", "old", "new"]


class App(ctk.CTk):
    def __init__(self, config: Config):
        super().__init__()
        self.config_obj = config
        self.bus = EventBus()
        self.bot: FishingBot | None = None
        self.chat_watcher = None

        self.title("Metin2 Balık Botu")
        self.geometry("680x560")
        ctk.set_appearance_mode("dark")

        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill="both", expand=True, padx=8, pady=8)
        for name in ["Balık", "Balıklar", "Sohbet AI", "Ayarlar",
                     "Kalibrasyon", "Log"]:
            self.tabs.add(name)

        self._build_run_tab(self.tabs.tab("Balık"))
        self.fish_tab = FishPickerTab(self.tabs.tab("Balıklar"),
                                      config, self._log_ui)
        self.fish_tab.pack(fill="both", expand=True)
        self.chat_tab = ChatPanelTab(self.tabs.tab("Sohbet AI"),
                                     config, self._log_ui)
        self.chat_tab.pack(fill="both", expand=True)
        self._build_settings_tab(self.tabs.tab("Ayarlar"))
        self.calib_tab = CalibrationTab(
            self.tabs.tab("Kalibrasyon"), config, self._make_capture,
            self._log_ui)
        self.calib_tab.pack(fill="both", expand=True)
        self._build_log_tab(self.tabs.tab("Log"))

        # Route bus events into the UI (thread-safe via tk .after).
        self.bus.subscribe(self._on_event)

    # -- tab builders -------------------------------------------------------
    def _build_run_tab(self, parent):
        ctk.CTkLabel(parent, text="Çalıştırma",
                     font=("", 16, "bold")).pack(anchor="w", padx=12, pady=8)

        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(row, text="Sistem", width=120, anchor="w").pack(side="left")
        self.system_var = ctk.StringVar(
            value=self.config_obj.get("fishing.system", "auto"))
        ctk.CTkOptionMenu(row, values=SYSTEMS, variable=self.system_var).pack(
            side="left")

        self.dry_var = ctk.BooleanVar(
            value=self.config_obj.get("runtime.dry_run", True))
        ctk.CTkSwitch(parent, text="Kuru çalışma (girdi gönderme)",
                      variable=self.dry_var).pack(anchor="w", padx=12, pady=4)
        self.fish_enable = ctk.BooleanVar(
            value=self.config_obj.get("fish.enabled", False))
        ctk.CTkSwitch(parent, text="Balık yaktırma etkin",
                      variable=self.fish_enable).pack(anchor="w", padx=12, pady=4)

        btns = ctk.CTkFrame(parent, fg_color="transparent")
        btns.pack(fill="x", padx=12, pady=10)
        self.start_btn = ctk.CTkButton(btns, text="Başlat", command=self.start)
        self.start_btn.pack(side="left", padx=4)
        self.stop_btn = ctk.CTkButton(btns, text="Durdur", command=self.stop,
                                      state="disabled")
        self.stop_btn.pack(side="left", padx=4)

        self.status_label = ctk.CTkLabel(parent, text="durum: hazır",
                                         font=("", 13))
        self.status_label.pack(anchor="w", padx=12, pady=8)
        ctk.CTkLabel(parent, text="Acil durdurma: F6",
                     text_color="gray").pack(anchor="w", padx=12)

    def _build_settings_tab(self, parent):
        ctk.CTkLabel(parent, text="Ayarlar",
                     font=("", 16, "bold")).pack(anchor="w", padx=12, pady=8)
        self.setting_entries = {}
        fields = [
            ("fishing.bait_hotkey", "Yem tuşu"),
            ("fishing.cast_hotkey", "Atış tuşu"),
            ("fishing.bait_time", "Yem bekleme (s)"),
            ("fishing.throw_time", "Atış bekleme (s)"),
            ("fishing.match_threshold", "Eşleşme eşiği"),
            ("safety.click_cooldown", "Tık aralığı (s)"),
            ("safety.max_runtime_minutes", "Maks süre (dk)"),
            ("window.title", "Pencere başlığı"),
        ]
        for path, label in fields:
            w = LabeledEntry(parent, label, self.config_obj.get(path, ""))
            w.pack(anchor="w", padx=12, pady=2)
            self.setting_entries[path] = w

        save_row = ctk.CTkFrame(parent, fg_color="transparent")
        save_row.pack(fill="x", padx=12, pady=8)
        ctk.CTkButton(save_row, text="Uygula", command=self._apply_settings).pack(
            side="left", padx=4)
        self.profile_name = ctk.StringVar(value="my_profile")
        ctk.CTkEntry(save_row, textvariable=self.profile_name, width=140).pack(
            side="left", padx=4)
        ctk.CTkButton(save_row, text="Profili Kaydet",
                      command=self._save_profile).pack(side="left", padx=4)

    def _build_log_tab(self, parent):
        self.log_view = LogView(parent)
        self.log_view.pack(fill="both", expand=True, padx=8, pady=8)

    # -- actions ------------------------------------------------------------
    def _apply_settings(self):
        for path, widget in self.setting_entries.items():
            raw = widget.get()
            self.config_obj.set(path, _coerce(raw))
        self._log_ui("ayarlar uygulandı")

    def _save_profile(self):
        self._apply_settings()
        self.calib_tab.apply()
        path = save_profile(self.config_obj, self.profile_name.get())
        self._log_ui(f"profil kaydedildi -> {path}")

    def _make_capture(self):
        return create_capture(self.config_obj.get("window.backend", "auto"),
                              title=self.config_obj.get("window.title", "Metin2"))

    def _build_fish_manager(self, input_controller):
        catalog = FishCatalog.load(
            self.config_obj.get("fish.catalog_path",
                                "assets/templates/fish/fish_catalog.json"))
        templates = catalog.load_templates()
        recognizer = FishRecognizer(
            templates, threshold=self.config_obj.get("fish.match_threshold", 0.7))
        disposer = FishDisposer(
            action=self.config_obj.get("fish.dispose_action", "log"),
            npc_position=self.config_obj.get("fish.npc_position"),
            bus=self.bus, dry_run=self.config_obj.get("runtime.dry_run", True))
        return FishManager(catalog, recognizer, disposer, bus=self.bus,
                           input_controller=input_controller)

    def start(self):
        # Sync run-tab toggles into config before launch.
        self.config_obj.set("fishing.system", self.system_var.get())
        self.config_obj.set("runtime.dry_run", bool(self.dry_var.get()))
        self.config_obj.set("fish.enabled", bool(self.fish_enable.get()))
        self.chat_tab.apply()
        self.calib_tab.apply()

        input_controller = InputController(
            bus=self.bus, dry_run=self.config_obj.get("runtime.dry_run", True),
            delay_jitter=self.config_obj.get("safety.delay_jitter", 0.15),
            click_radius=self.config_obj.get("safety.click_radius", 4))

        fish_manager = (self._build_fish_manager(input_controller)
                        if self.config_obj.get("fish.enabled", False) else None)

        try:
            capture = self._make_capture()
        except Exception as exc:
            self._log_ui(f"pencere bulunamadı: {exc}")
            return

        self.bot = FishingBot(self.config_obj, bus=self.bus, capture=capture,
                              input_controller=input_controller,
                              fish_manager=fish_manager)
        self.bot.start()

        # Optional chat watcher.
        if self.config_obj.get("chat_ai.enabled", False):
            from ..chat.watcher import ChatWatcher

            self.chat_watcher = ChatWatcher(
                self.config_obj, capture, input_controller, bus=self.bus,
                api_key=self.chat_tab.get_api_key() or None)
            self.chat_watcher.start()

        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self._log_ui("bot başlatıldı")

    def stop(self):
        if self.chat_watcher:
            self.chat_watcher.stop()
            self.chat_watcher = None
        if self.bot:
            self.bot.stop()
            self.bot = None
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self._log_ui("bot durduruldu")

    # -- event routing ------------------------------------------------------
    def _on_event(self, event: Event):
        # Marshal onto the Tk main thread.
        self.after(0, lambda: self._handle_event(event))

    def _handle_event(self, event: Event):
        if event.type == "log":
            self.log_view.append(event.payload.get("message", ""))
        elif event.type == "state":
            self.status_label.configure(
                text=f"durum: {event.payload.get('state')}")

    def _log_ui(self, message: str):
        self.bus.log(message)


def _coerce(value: str):
    """Coerce a settings string to int/float/bool when it looks like one."""
    v = value.strip()
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    try:
        if "." in v:
            return float(v)
        return int(v)
    except ValueError:
        return v
