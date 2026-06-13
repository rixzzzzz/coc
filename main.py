"""
COC AutoFarmer v1.0 — Clash of Clans Autonomous Farming Bot
Main entry point: Kivy UI + Bot Engine orchestration
"""

import os
import sys
import json
import time
import threading
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Kivy config before import
os.environ['KIVY_LOG_LEVEL'] = 'info'

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.spinner import Spinner
from kivy.uix.slider import Slider
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.uix.switch import Switch
from kivy.uix.progressbar import ProgressBar
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle, RoundedRectangle, Line
from kivy.properties import (
    StringProperty, NumericProperty, BooleanProperty,
    ListProperty, ObjectProperty, DictProperty
)
from kivy.utils import get_color_from_hex
from kivy.metrics import dp, sp

# Internal modules
from bot_engine import BotEngine
from screen_analyzer import ScreenAnalyzer
from army_manager import ArmyManager
from resource_manager import ResourceManager
from raid_logger import RaidLogger
from config import BotConfig

# ═══════════════════════════════════════════════════════════
# LOGGING SETUP
# ═══════════════════════════════════════════════════════════
LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'coc_farmer.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('COCFarmer')


# ═══════════════════════════════════════════════════════════
# STATUS BAR WIDGET
# ═══════════════════════════════════════════════════════════
class StatusBar(BoxLayout):
    status_text = StringProperty("IDLE")
    gold_text = StringProperty("0")
    elixir_text = StringProperty("0")
    de_text = StringProperty("0")
    raids_text = StringProperty("0")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'horizontal'
        self.size_hint_y = None
        self.height = dp(50)
        self.padding = [dp(8), dp(4)]
        self.spacing = dp(6)

        with self.canvas.before:
            Color(0.12, 0.12, 0.15, 1)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(8)])
        self.bind(pos=self._update_bg, size=self._update_bg)

        # Status indicator
        self.status_label = Label(
            text='⬤ IDLE', font_size=sp(13), color=get_color_from_hex('#FF4444'),
            size_hint_x=0.25, halign='left', valign='middle'
        )
        self.status_label.bind(size=self.status_label.setter('text_size'))
        self.add_widget(self.status_label)

        # Resource displays
        for icon, prop, color in [
            ('🪙', 'gold_text', '#FFD700'),
            ('💧', 'elixir_text', '#FF69B4'),
            ('⚫', 'de_text', '#8B4513'),
            ('⚔️', 'raids_text', '#00FF88')
        ]:
            lbl = Label(
                text=f'{icon} 0', font_size=sp(12),
                color=get_color_from_hex(color),
                size_hint_x=0.1875
            )
            setattr(self, f'_{prop}_label', lbl)
            self.add_widget(lbl)

    def _update_bg(self, *args):
        self._bg.pos = self.pos
        self._bg.size = self.size

    def update_status(self, status, gold=None, elixir=None, de=None, raids=None):
        colors = {
            'FARMING': '#00FF88', 'SCOUTING': '#FFD700',
            'ATTACKING': '#FF4444', 'QUEUING': '#00BFFF',
            'IDLE': '#888888', 'PAUSED': '#FF8800',
            'WAITING': '#AA88FF', 'ERROR': '#FF0000'
        }
        color = colors.get(status, '#FFFFFF')
        self.status_label.text = f'⬤ {status}'
        self.status_label.color = get_color_from_hex(color)

        if gold is not None:
            self._gold_text_label.text = f'🪙 {self._format_num(gold)}'
        if elixir is not None:
            self._elixir_text_label.text = f'💧 {self._format_num(elixir)}'
        if de is not None:
            self._de_text_label.text = f'⚫ {self._format_num(de)}'
        if raids is not None:
            self._raids_text_label.text = f'⚔️ {raids}'

    @staticmethod
    def _format_num(n):
        if n >= 1_000_000:
            return f'{n / 1_000_000:.1f}M'
        elif n >= 1_000:
            return f'{n / 1_000:.0f}K'
        return str(n)


# ═══════════════════════════════════════════════════════════
# LOG PANEL WIDGET
# ═══════════════════════════════════════════════════════════
class LogPanel(ScrollView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint_y = 0.35
        self.do_scroll_x = False

        self._log_layout = BoxLayout(
            orientation='vertical', size_hint_y=None,
            padding=[dp(6), dp(4)], spacing=dp(2)
        )
        self._log_layout.bind(minimum_height=self._log_layout.setter('height'))
        self.add_widget(self._log_layout)
        self._max_lines = 200

    def add_log(self, msg, level='info'):
        colors = {
            'info': '#CCCCCC', 'success': '#00FF88',
            'warning': '#FFD700', 'error': '#FF4444',
            'loot': '#FF69B4', 'attack': '#FF8800'
        }
        timestamp = datetime.now().strftime('%H:%M:%S')
        color = colors.get(level, '#CCCCCC')

        lbl = Label(
            text=f'[color={color}][{timestamp}] {msg}[/color]',
            markup=True, font_size=sp(11),
            size_hint_y=None, height=dp(18),
            halign='left', valign='middle'
        )
        lbl.bind(size=lbl.setter('text_size'))
        self._log_layout.add_widget(lbl)

        # Trim old logs
        while len(self._log_layout.children) > self._max_lines:
            self._log_layout.remove_widget(self._log_layout.children[-1])

        # Auto-scroll to bottom
        self.scroll_y = 0


# ═══════════════════════════════════════════════════════════
# SETTINGS PANEL
# ═══════════════════════════════════════════════════════════
class SettingsPanel(BoxLayout):
    def __init__(self, config: BotConfig, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = [dp(10), dp(8)]
        self.spacing = dp(6)
        self.config = config

        with self.canvas.before:
            Color(0.1, 0.1, 0.13, 1)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(10)])
        self.bind(pos=self._update_bg, size=self._update_bg)

        title = Label(
            text='⚙️ SETTINGS', font_size=sp(16), bold=True,
            color=get_color_from_hex('#FFFFFF'),
            size_hint_y=None, height=dp(30)
        )
        self.add_widget(title)

        # TH Level selector
        th_row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        th_row.add_widget(Label(text='TH Level:', font_size=sp(13), size_hint_x=0.4,
                                color=get_color_from_hex('#AAAAAA')))
        self.th_spinner = Spinner(
            text=str(config.th_level),
            values=[str(i) for i in range(8, 17)],
            font_size=sp(13), size_hint_x=0.6
        )
        self.th_spinner.bind(text=self._on_th_change)
        th_row.add_widget(self.th_spinner)
        self.add_widget(th_row)

        # Min Gold threshold
        self._add_threshold_row('Min Gold:', config.min_gold, 'min_gold', 50000, 500000)
        # Min Elixir threshold
        self._add_threshold_row('Min Elixir:', config.min_elixir, 'min_elixir', 50000, 500000)
        # Min DE threshold
        self._add_threshold_row('Min DE:', config.min_de, 'min_de', 500, 5000)
        # Max skip count
        self._add_threshold_row('Max Skips:', config.max_consecutive_skips, 'max_consecutive_skips', 5, 50)
        # Loot ratio
        self._add_threshold_row('Min Ratio:', config.min_loot_ratio, 'min_loot_ratio', 1.0, 10.0)

        # Auto-upgrade toggle
        upgrade_row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        upgrade_row.add_widget(Label(text='Auto Upgrade:', font_size=sp(13), size_hint_x=0.5,
                                     color=get_color_from_hex('#AAAAAA')))
        self.upgrade_switch = Switch(active=config.auto_upgrade, size_hint_x=0.5)
        self.upgrade_switch.bind(active=self._on_upgrade_toggle)
        upgrade_row.add_widget(self.upgrade_switch)
        self.add_widget(upgrade_row)

        # Shield respect toggle
        shield_row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        shield_row.add_widget(Label(text='Respect Shield:', font_size=sp(13), size_hint_x=0.5,
                                    color=get_color_from_hex('#AAAAAA')))
        self.shield_switch = Switch(active=config.respect_shield, size_hint_x=0.5)
        self.shield_switch.bind(active=self._on_shield_toggle)
        shield_row.add_widget(self.shield_switch)
        self.add_widget(shield_row)

    def _add_threshold_row(self, label_text, value, attr, min_val, max_val):
        row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        row.add_widget(Label(text=label_text, font_size=sp(13), size_hint_x=0.35,
                             color=get_color_from_hex('#AAAAAA')))
        val_label = Label(text=str(int(value)) if isinstance(value, float) and value == int(value) else str(value),
                          font_size=sp(13), size_hint_x=0.2,
                          color=get_color_from_hex('#00FF88'))
        slider = Slider(min=min_val, max=max_val, value=value, size_hint_x=0.45,
                        step=1 if max_val > 100 else 0.5)

        def on_change(instance, val, lbl=val_label, a=attr):
            display = int(val) if val == int(val) else round(val, 1)
            lbl.text = str(display)
            setattr(self.config, a, val)

        slider.bind(value=on_change)
        row.add_widget(val_label)
        row.add_widget(slider)
        self.add_widget(row)

    def _on_th_change(self, spinner, text):
        self.config.th_level = int(text)

    def _on_upgrade_toggle(self, switch, active):
        self.config.auto_upgrade = active

    def _on_shield_toggle(self, switch, active):
        self.config.respect_shield = active

    def _update_bg(self, *args):
        self._bg.pos = self.pos
        self._bg.size = self.size


# ═══════════════════════════════════════════════════════════
# STATS PANEL
# ═══════════════════════════════════════════════════════════
class StatsPanel(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = [dp(10), dp(8)]
        self.spacing = dp(4)

        with self.canvas.before:
            Color(0.1, 0.1, 0.13, 1)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(10)])
        self.bind(pos=self._update_bg, size=self._update_bg)

        title = Label(text='📊 SESSION STATS', font_size=sp(16), bold=True,
                      color=get_color_from_hex('#FFFFFF'),
                      size_hint_y=None, height=dp(30))
        self.add_widget(title)

        self.stat_labels = {}
        stats = [
            ('raids', '⚔️ Raids Completed', '0'),
            ('gold', '🪙 Total Gold', '0'),
            ('elixir', '💧 Total Elixir', '0'),
            ('de', '⚫ Total DE', '0'),
            ('avg_loot', '📈 Avg Loot/Raid', '0'),
            ('troop_cost', '💰 Troop Cost', '0'),
            ('net_ratio', '📊 Net Efficiency', '0:0'),
            ('upgrades', '🔨 Upgrades', '0'),
            ('skips', '⏭️ Total Skips', '0'),
            ('session_time', '⏱️ Session Time', '00:00:00'),
        ]

        for key, label_text, default in stats:
            row = BoxLayout(size_hint_y=None, height=dp(24), spacing=dp(4))
            row.add_widget(Label(
                text=label_text, font_size=sp(12), size_hint_x=0.55,
                halign='left', valign='middle',
                color=get_color_from_hex('#AAAAAA')
            ))
            val_lbl = Label(
                text=default, font_size=sp(12), size_hint_x=0.45,
                halign='right', valign='middle',
                color=get_color_from_hex('#00FF88')
            )
            val_lbl.bind(size=val_lbl.setter('text_size'))
            row.add_widget(val_lbl)
            self.stat_labels[key] = val_lbl
            self.add_widget(row)

    def update_stats(self, stats_dict):
        for key, value in stats_dict.items():
            if key in self.stat_labels:
                if isinstance(value, (int, float)):
                    if value >= 1_000_000:
                        display = f'{value / 1_000_000:.2f}M'
                    elif value >= 1_000:
                        display = f'{value / 1_000:.1f}K'
                    else:
                        display = str(int(value)) if isinstance(value, float) else str(value)
                else:
                    display = str(value)
                self.stat_labels[key].text = display

    def _update_bg(self, *args):
        self._bg.pos = self.pos
        self._bg.size = self.size


# ═══════════════════════════════════════════════════════════
# MAIN SCREEN
# ═══════════════════════════════════════════════════════════
class MainScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.config = BotConfig()
        self.bot_engine = None
        self._bot_thread = None
        self._session_start = None
        self._is_running = False

        # Root layout
        root = BoxLayout(orientation='vertical', padding=[dp(6), dp(4)], spacing=dp(4))

        with root.canvas.before:
            Color(0.08, 0.08, 0.1, 1)
            self._root_bg = Rectangle(pos=root.pos, size=root.size)
        root.bind(pos=self._update_root_bg, size=self._update_root_bg)

        # Header
        header = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8), padding=[dp(6), 0])
        header.add_widget(Label(
            text='💀 COC AutoFarmer', font_size=sp(18), bold=True,
            color=get_color_from_hex('#FF4444'), size_hint_x=0.5,
            halign='left', valign='middle'
        ))
        header.add_widget(Label(
            text='v1.0', font_size=sp(11),
            color=get_color_from_hex('#666666'), size_hint_x=0.15
        ))

        # Control buttons
        self.start_btn = Button(
            text='▶ START', font_size=sp(13), bold=True,
            size_hint_x=0.175,
            background_color=get_color_from_hex('#00CC66'),
            color=get_color_from_hex('#FFFFFF')
        )
        self.start_btn.bind(on_press=self._on_start)

        self.stop_btn = Button(
            text='⏹ STOP', font_size=sp(13), bold=True,
            size_hint_x=0.175, disabled=True,
            background_color=get_color_from_hex('#CC3333'),
            color=get_color_from_hex('#FFFFFF')
        )
        self.stop_btn.bind(on_press=self._on_stop)

        header.add_widget(self.start_btn)
        header.add_widget(self.stop_btn)
        root.add_widget(header)

        # Status bar
        self.status_bar = StatusBar()
        root.add_widget(self.status_bar)

        # Middle section: stats + settings side by side on tablets, stacked on phone
        mid_section = BoxLayout(
            orientation='horizontal', size_hint_y=0.45,
            spacing=dp(6), padding=[0, dp(4)]
        )

        self.stats_panel = StatsPanel(size_hint_x=0.5)
        self.settings_panel = SettingsPanel(config=self.config, size_hint_x=0.5)
        mid_section.add_widget(self.stats_panel)
        mid_section.add_widget(self.settings_panel)
        root.add_widget(mid_section)

        # Log panel
        self.log_panel = LogPanel()
        root.add_widget(self.log_panel)

        # Bottom button row
        bottom = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(6), padding=[dp(4), 0])

        export_btn = Button(
            text='📤 Export Log', font_size=sp(12),
            background_color=get_color_from_hex('#335577')
        )
        export_btn.bind(on_press=self._export_log)

        clear_btn = Button(
            text='🗑️ Clear Log', font_size=sp(12),
            background_color=get_color_from_hex('#553333')
        )
        clear_btn.bind(on_press=self._clear_log)

        reset_btn = Button(
            text='🔄 Reset Stats', font_size=sp(12),
            background_color=get_color_from_hex('#555533')
        )
        reset_btn.bind(on_press=self._reset_stats)

        perms_btn = Button(
            text='🔑 Permissions', font_size=sp(12),
            background_color=get_color_from_hex('#553355')
        )
        perms_btn.bind(on_press=self._check_permissions)

        bottom.add_widget(export_btn)
        bottom.add_widget(clear_btn)
        bottom.add_widget(reset_btn)
        bottom.add_widget(perms_btn)
        root.add_widget(bottom)

        self.add_widget(root)

        # Schedule periodic UI updates
        Clock.schedule_interval(self._update_ui, 1.0)

    def _update_root_bg(self, *args):
        pass

    def _on_start(self, btn):
        if self._is_running:
            return

        self._is_running = True
        self._session_start = time.time()
        self.start_btn.disabled = True
        self.stop_btn.disabled = False
        self.log_panel.add_log('🚀 Bot engine starting...', 'success')
        self.status_bar.update_status('FARMING')

        # Initialize bot engine
        self.bot_engine = BotEngine(
            config=self.config,
            screen_analyzer=ScreenAnalyzer(self.config),
            army_manager=ArmyManager(self.config),
            resource_manager=ResourceManager(self.config),
            raid_logger=RaidLogger(),
            log_callback=self._bot_log
        )

        # Start bot thread
        self._bot_thread = threading.Thread(target=self._run_bot, daemon=True)
        self._bot_thread.start()
        self.log_panel.add_log('✅ Bot engine started — farming loop active', 'success')

    def _on_stop(self, btn):
        if not self._is_running:
            return

        self._is_running = False
        self.start_btn.disabled = False
        self.stop_btn.disabled = True
        self.status_bar.update_status('IDLE')

        if self.bot_engine:
            self.bot_engine.stop()
            self.log_panel.add_log('⏹ Bot engine stopped', 'warning')

            # Print session summary
            summary = self.bot_engine.get_session_summary()
            self.log_panel.add_log('═══ SESSION SUMMARY ═══', 'success')
            for key, val in summary.items():
                self.log_panel.add_log(f'  {key}: {val}', 'info')

    def _run_bot(self):
        try:
            self.bot_engine.run()
        except Exception as e:
            Clock.schedule_once(lambda dt: self._bot_log(f'❌ Bot error: {e}', 'error'))
            Clock.schedule_once(lambda dt: self._on_stop(None))

    def _bot_log(self, msg, level='info'):
        Clock.schedule_once(lambda dt: self.log_panel.add_log(msg, level))

    def _update_ui(self, dt):
        if not self._is_running or not self.bot_engine:
            return

        stats = self.bot_engine.get_stats()
        self.stats_panel.update_stats(stats)
        self.status_bar.update_status(
            stats.get('status', 'FARMING'),
            gold=stats.get('gold', 0),
            elixir=stats.get('elixir', 0),
            de=stats.get('de', 0),
            raids=stats.get('raids', 0)
        )

        if self._session_start:
            elapsed = int(time.time() - self._session_start)
            h, m, s = elapsed // 3600, (elapsed % 3600) // 60, elapsed % 60
            self.stats_panel.update_stats({'session_time': f'{h:02d}:{m:02d}:{s:02d}'})

    def _export_log(self, btn):
        if self.bot_engine:
            path = self.bot_engine.raid_logger.export_session()
            self.log_panel.add_log(f'📤 Log exported: {path}', 'success')
        else:
            self.log_panel.add_log('⚠️ No active session to export', 'warning')

    def _clear_log(self, btn):
        self.log_panel._log_layout.clear_widgets()
        self.log_panel.add_log('🗑️ Log cleared', 'info')

    def _reset_stats(self, btn):
        if self.bot_engine:
            self.bot_engine.reset_stats()
            self.log_panel.add_log('🔄 Stats reset', 'info')

    def _check_permissions(self, btn):
        self.log_panel.add_log('🔑 Checking permissions...', 'info')
        try:
            from permissions_manager import PermissionsManager
            pm = PermissionsManager()
            status = pm.check_all()
            for perm, granted in status.items():
                icon = '✅' if granted else '❌'
                self.log_panel.add_log(f'  {icon} {perm}', 'success' if granted else 'error')
        except Exception as e:
            self.log_panel.add_log(f'⚠️ Permission check failed: {e}', 'warning')


# ═══════════════════════════════════════════════════════════
# APP CLASS
# ═══════════════════════════════════════════════════════════
class COCAutoFarmerApp(App):
    title = 'COC AutoFarmer'

    def build(self):
        Window.clearcolor = get_color_from_hex('#141418')
        sm = ScreenManager()
        sm.add_widget(MainScreen(name='main'))
        return sm

    def on_start(self):
        logger.info('COC AutoFarmer app started')

    def on_stop(self):
        logger.info('COC AutoFarmer app stopped')

    def on_pause(self):
        return True

    def on_resume(self):
        pass


# ═══════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════
if __name__ == '__main__':
    COCAutoFarmerApp().run()
