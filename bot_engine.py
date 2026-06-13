"""
COC AutoFarmer — Bot Engine Module
Core state machine: SCOUT → ANALYZE → DEPLOY → COLLECT → QUEUE → LOOP
Handles the full autonomous farming cycle.
"""

import time
import random
import logging
import threading
from enum import Enum, auto
from typing import Callable, Optional, Dict, List, Tuple
from dataclasses import dataclass, field

from config import BotConfig
from screen_analyzer import ScreenAnalyzer, BaseAnalysis, LootInfo, GameState
from army_manager import ArmyManager
from resource_manager import ResourceManager
from raid_logger import RaidLogger

logger = logging.getLogger('BotEngine')


# ═══════════════════════════════════════════════════════════
# BOT STATES
# ═══════════════════════════════════════════════════════════
class BotState(Enum):
    IDLE = auto()
    INIT = auto()
    CHECK_SHIELD = auto()
    CHECK_ARMY = auto()
    FIND_MATCH = auto()
    SCOUTING = auto()
    ANALYZING = auto()
    DEPLOYING = auto()
    MONITORING_ATTACK = auto()
    END_ATTACK = auto()
    COLLECTING = auto()
    QUEUING_ARMY = auto()
    UPGRADING = auto()
    WAITING_ARMY = auto()
    ERROR_RECOVERY = auto()
    STOPPED = auto()


# ═══════════════════════════════════════════════════════════
# SESSION STATS
# ═══════════════════════════════════════════════════════════
@dataclass
class SessionStats:
    raids_completed: int = 0
    total_gold: int = 0
    total_elixir: int = 0
    total_de: int = 0
    total_troop_cost: int = 0
    total_skips: int = 0
    upgrades_triggered: List[str] = field(default_factory=list)
    negative_raids: int = 0
    session_start: float = 0.0

    @property
    def avg_gold_per_raid(self) -> int:
        return self.total_gold // max(1, self.raids_completed)

    @property
    def avg_elixir_per_raid(self) -> int:
        return self.total_elixir // max(1, self.raids_completed)

    @property
    def avg_de_per_raid(self) -> int:
        return self.total_de // max(1, self.raids_completed)

    @property
    def net_gold(self) -> int:
        return self.total_gold - self.total_troop_cost

    @property
    def efficiency_ratio(self) -> float:
        if self.total_troop_cost <= 0:
            return 0.0
        return (self.total_gold + self.total_elixir) / max(1, self.total_troop_cost)


# ═══════════════════════════════════════════════════════════
# TOUCH CONTROLLER
# ═══════════════════════════════════════════════════════════
class TouchController:
    """
    Handles all touch input simulation via Android's InputManager.
    Supports tap, swipe, long-press, and multi-touch.
    """

    def __init__(self, config: BotConfig):
        self.config = config
        self._android_available = False
        self._init_android()

    def _init_android(self):
        """Initialize Android touch injection."""
        try:
            from jnius import autoclass
            self.Instrumentation = autoclass('android.app.Instrumentation')
            self.MotionEvent = autoclass('android.view.MotionEvent')
            self.SystemClock = autoclass('android.os.SystemClock')
            self._instrumentation = self.Instrumentation()
            self._android_available = True
            logger.info('Android touch controller initialized')
        except ImportError:
            logger.warning('Android not available — touch simulation in mock mode')
            self._android_available = False

    def tap(self, x: int, y: int, delay_after_ms: int = 0):
        """Simulate a single tap at (x, y)."""
        jitter_x = random.randint(-3, 3)
        jitter_y = random.randint(-3, 3)
        actual_x = x + jitter_x
        actual_y = y + jitter_y

        if self._android_available:
            self._android_tap(actual_x, actual_y)
        else:
            logger.debug(f'[MOCK TAP] ({actual_x}, {actual_y})')

        if delay_after_ms > 0:
            time.sleep(delay_after_ms / 1000.0)
        else:
            delay = random.randint(
                self.config.touch_delay_min,
                self.config.touch_delay_max
            )
            time.sleep(delay / 1000.0)

    def _android_tap(self, x: int, y: int):
        """Actual Android tap via Instrumentation."""
        try:
            down_time = self.SystemClock.uptimeMillis()
            event_down = self.MotionEvent.obtain(
                down_time, down_time,
                self.MotionEvent.ACTION_DOWN,
                float(x), float(y), 0
            )
            event_up = self.MotionEvent.obtain(
                down_time, down_time + 50,
                self.MotionEvent.ACTION_UP,
                float(x), float(y), 0
            )
            self._instrumentation.sendPointerSync(event_down)
            self._instrumentation.sendPointerSync(event_up)
            event_down.recycle()
            event_up.recycle()
        except Exception as e:
            logger.error(f'Android tap failed: {e}')

    def long_press(self, x: int, y: int, duration_ms: int = 500):
        """Simulate long press."""
        if self._android_available:
            try:
                down_time = self.SystemClock.uptimeMillis()
                event_down = self.MotionEvent.obtain(
                    down_time, down_time,
                    self.MotionEvent.ACTION_DOWN,
                    float(x), float(y), 0
                )
                self._instrumentation.sendPointerSync(event_down)
                time.sleep(duration_ms / 1000.0)
                event_up = self.MotionEvent.obtain(
                    down_time, down_time + duration_ms,
                    self.MotionEvent.ACTION_UP,
                    float(x), float(y), 0
                )
                self._instrumentation.sendPointerSync(event_up)
                event_down.recycle()
                event_up.recycle()
            except Exception as e:
                logger.error(f'Long press failed: {e}')
        else:
            logger.debug(f'[MOCK LONG_PRESS] ({x}, {y}) {duration_ms}ms')

    def swipe(self, x1: int, y1: int, x2: int, y2: int, steps: int = 20):
        """Simulate swipe gesture."""
        if self._android_available:
            try:
                down_time = self.SystemClock.uptimeMillis()
                event_down = self.MotionEvent.obtain(
                    down_time, down_time,
                    self.MotionEvent.ACTION_DOWN,
                    float(x1), float(y1), 0
                )
                self._instrumentation.sendPointerSync(event_down)
                event_down.recycle()

                step_time = self.config.swipe_duration // steps
                for i in range(1, steps + 1):
                    t = i / steps
                    cx = x1 + (x2 - x1) * t
                    cy = y1 + (y2 - y1) * t
                    move_time = down_time + step_time * i
                    event_move = self.MotionEvent.obtain(
                        down_time, move_time,
                        self.MotionEvent.ACTION_MOVE,
                        float(cx), float(cy), 0
                    )
                    self._instrumentation.sendPointerSync(event_move)
                    event_move.recycle()
                    time.sleep(step_time / 1000.0)

                event_up = self.MotionEvent.obtain(
                    down_time, down_time + self.config.swipe_duration,
                    self.MotionEvent.ACTION_UP,
                    float(x2), float(y2), 0
                )
                self._instrumentation.sendPointerSync(event_up)
                event_up.recycle()
            except Exception as e:
                logger.error(f'Swipe failed: {e}')
        else:
            logger.debug(f'[MOCK SWIPE] ({x1},{y1}) → ({x2},{y2})')

    def deploy_troop_line(self, positions: List[Tuple[int, int]], troop_slot: Tuple[int, int],
                          count: int):
        """Deploy troops along a line of positions."""
        # First select the troop slot
        self.tap(troop_slot[0], troop_slot[1])
        time.sleep(0.1)

        # Distribute deployments across positions
        per_pos = max(1, count // max(1, len(positions)))
        deployed = 0

        for pos in positions:
            for _ in range(min(per_pos, count - deployed)):
                self.tap(pos[0], pos[1], delay_after_ms=self.config.deploy_troop_interval_ms)
                deployed += 1
                if deployed >= count:
                    break
            if deployed >= count:
                break


# ═══════════════════════════════════════════════════════════
# BOT ENGINE
# ═══════════════════════════════════════════════════════════
class BotEngine:
    """
    Core autonomous farming engine. Runs continuous raid loops
    with intelligent base selection, attack execution, and
    resource management.
    """

    def __init__(self, config: BotConfig,
                 screen_analyzer: ScreenAnalyzer,
                 army_manager: ArmyManager,
                 resource_manager: ResourceManager,
                 raid_logger: RaidLogger,
                 log_callback: Callable = None):
        self.config = config
        self.analyzer = screen_analyzer
        self.army = army_manager
        self.resources = resource_manager
        self.raid_logger = raid_logger
        self.log = log_callback or (lambda msg, level='info': None)

        self.touch = TouchController(config)
        self.coords = config.get_screen_coords()

        self.state = BotState.IDLE
        self._running = False
        self._lock = threading.Lock()

        self.stats = SessionStats(session_start=time.time())
        self._consecutive_skips = 0
        self._consecutive_negative = 0
        self._relaxed_mode = False
        self._relaxed_raids_remaining = 0
        self._current_base: Optional[BaseAnalysis] = None
        self._pre_raid_loot: Optional[LootInfo] = None

    # ─────────────────────────────────────────────────────
    # PUBLIC API
    # ─────────────────────────────────────────────────────
    def run(self):
        """Start the farming loop."""
        self._running = True
        self.state = BotState.INIT
        self.stats.session_start = time.time()
        self.log('🚀 Farming engine engaged', 'success')

        while self._running:
            try:
                self._tick()
            except Exception as e:
                logger.error(f'Engine tick error: {e}', exc_info=True)
                self.log(f'❌ Error: {e}', 'error')
                self.state = BotState.ERROR_RECOVERY
                time.sleep(2)

    def stop(self):
        """Stop the farming loop."""
        self._running = False
        self.state = BotState.STOPPED
        self.log('⏹ Engine stopped', 'warning')

    def get_stats(self) -> Dict:
        """Get current session stats for UI."""
        return {
            'status': self.state.name,
            'raids': self.stats.raids_completed,
            'gold': self.stats.total_gold,
            'elixir': self.stats.total_elixir,
            'de': self.stats.total_de,
            'avg_loot': (self.stats.avg_gold_per_raid + self.stats.avg_elixir_per_raid) // 2,
            'troop_cost': self.stats.total_troop_cost,
            'net_ratio': f'{self.stats.efficiency_ratio:.1f}:1',
            'upgrades': len(self.stats.upgrades_triggered),
            'skips': self.stats.total_skips,
        }

    def get_session_summary(self) -> Dict:
        """Generate full session summary."""
        elapsed = time.time() - self.stats.session_start
        h, m, s = int(elapsed) // 3600, (int(elapsed) % 3600) // 60, int(elapsed) % 60
        return {
            'Raids completed': self.stats.raids_completed,
            'Total Gold gained': f'+{self.stats.total_gold:,}',
            'Total Elixir gained': f'+{self.stats.total_elixir:,}',
            'Total DE gained': f'+{self.stats.total_de:,}',
            'Avg loot/raid': f'{(self.stats.avg_gold_per_raid + self.stats.avg_elixir_per_raid) // 2:,}',
            'Troop cost total': f'{self.stats.total_troop_cost:,}',
            'Net efficiency': f'{self.stats.efficiency_ratio:.1f}:1',
            'Upgrades triggered': ', '.join(self.stats.upgrades_triggered) or 'None',
            'Session duration': f'{h:02d}:{m:02d}:{s:02d}',
        }

    def reset_stats(self):
        """Reset session statistics."""
        self.stats = SessionStats(session_start=time.time())
        self.log('🔄 Stats reset', 'info')

    # ─────────────────────────────────────────────────────
    # STATE MACHINE
    # ─────────────────────────────────────────────────────
    def _tick(self):
        """Execute one state machine tick."""
        handlers = {
            BotState.INIT: self._handle_init,
            BotState.CHECK_SHIELD: self._handle_check_shield,
            BotState.CHECK_ARMY: self._handle_check_army,
            BotState.FIND_MATCH: self._handle_find_match,
            BotState.SCOUTING: self._handle_scouting,
            BotState.ANALYZING: self._handle_analyzing,
            BotState.DEPLOYING: self._handle_deploying,
            BotState.MONITORING_ATTACK: self._handle_monitoring,
            BotState.END_ATTACK: self._handle_end_attack,
            BotState.COLLECTING: self._handle_collecting,
            BotState.QUEUING_ARMY: self._handle_queuing,
            BotState.UPGRADING: self._handle_upgrading,
            BotState.WAITING_ARMY: self._handle_waiting,
            BotState.ERROR_RECOVERY: self._handle_error_recovery,
        }

        handler = handlers.get(self.state)
        if handler:
            handler()
        else:
            time.sleep(1)

    # ─────────────────────────────────────────────────────
    # STATE HANDLERS
    # ─────────────────────────────────────────────────────
    def _handle_init(self):
        """Initialize — detect game state, ensure we're on home screen."""
        self.log('🔍 Detecting game state...', 'info')
        game_state = self.analyzer.detect_game_state()

        if game_state.screen == 'home':
            self.log('🏠 Home screen detected', 'info')
            self.state = BotState.CHECK_SHIELD
        elif game_state.screen == 'scout':
            self.log('👁️ Already in scout mode', 'info')
            self.state = BotState.SCOUTING
        elif game_state.screen == 'attack':
            self.log('⚔️ Already in attack', 'warning')
            self.state = BotState.MONITORING_ATTACK
        else:
            self.log('⚠️ Unknown screen — attempting home navigation', 'warning')
            # Try tapping return home
            self.touch.tap(self.coords['return_home_button'][0],
                          self.coords['return_home_button'][1])
            time.sleep(2)
            self.state = BotState.INIT  # Re-check

    def _handle_check_shield(self):
        """Check shield status before attacking."""
        if not self.config.respect_shield:
            self.state = BotState.CHECK_ARMY
            return

        game_state = self.analyzer.detect_game_state()

        if game_state.shield_active:
            remaining = game_state.shield_remaining_seconds
            if remaining > self.config.shield_minimum_remaining_seconds:
                self.log(
                    f'🛡️ Shield active ({remaining // 60}m remaining) — '
                    f'using time for upgrades/collection',
                    'warning'
                )
                self.state = BotState.COLLECTING
                return
            else:
                self.log(f'🛡️ Shield expiring soon ({remaining // 60}m) — proceeding', 'info')

        self.state = BotState.CHECK_ARMY

    def _handle_check_army(self):
        """Check if army is ready for raid."""
        army_comp = self.config.get_army()
        # Estimate readiness from training time
        army_ready = self.army.check_army_ready()

        if army_ready >= self.config.min_army_pct:
            self.log(f'💪 Army ready ({army_ready * 100:.0f}%) — searching for target', 'success')
            self.state = BotState.FIND_MATCH
        else:
            self.log(f'⏳ Army at {army_ready * 100:.0f}% — queuing and waiting', 'info')
            self.state = BotState.QUEUING_ARMY

    def _handle_find_match(self):
        """Navigate to multiplayer and find a match."""
        self.log('🔎 Finding match...', 'info')

        # Tap Attack button on home screen
        self.touch.tap(self.coords['attack_button'][0],
                      self.coords['attack_button'][1])
        time.sleep(1.5)

        # Tap Find a Match
        self.touch.tap(self.coords['find_match_button'][0],
                      self.coords['find_match_button'][1])
        time.sleep(3)  # Matchmaking loading time

        self._consecutive_skips = 0
        self.state = BotState.SCOUTING

    def _handle_scouting(self):
        """Scout current base — read loot and decide."""
        self.state = BotState.ANALYZING
        scout_start = time.time()

        # Read loot values
        analysis = self.analyzer.analyze_base()
        self._current_base = analysis

        scout_time_ms = (time.time() - scout_start) * 1000

        # Get thresholds (possibly relaxed)
        if self._relaxed_mode and self._relaxed_raids_remaining > 0:
            min_gold, min_elixir, min_de = self.config.get_relaxed_thresholds()
        else:
            min_gold = self.config.min_gold
            min_elixir = self.config.min_elixir
            min_de = self.config.min_de

        # ─── TARGET EVALUATION ───
        loot = analysis.loot
        accept = True
        reject_reason = ''

        # Loot check
        if loot.gold < min_gold and loot.elixir < min_elixir and loot.dark_elixir < min_de:
            accept = False
            reject_reason = f'Low loot (G:{loot.gold} E:{loot.elixir} DE:{loot.dark_elixir})'

        # Collector bias check
        elif analysis.collector_bias < self.config.min_collector_bias:
            accept = False
            reject_reason = f'Low collector bias ({analysis.collector_bias:.0f}%)'

        # TH level check
        elif abs(analysis.th_level - self.config.th_level) > self.config.th_match_range:
            accept = False
            reject_reason = f'TH mismatch (target: TH{analysis.th_level})'

        # Threat check — dangerous defenses
        elif analysis.threat_level >= 7:
            accept = False
            reject_reason = f'High threat level ({analysis.threat_level}/10)'

        if accept:
            self.log(
                f'✅ TARGET FOUND: G={loot.gold:,} E={loot.elixir:,} DE={loot.dark_elixir:,} '
                f'Bias={analysis.collector_bias:.0f}% TH{analysis.th_level} '
                f'Entry={analysis.recommended_entry_side}',
                'success'
            )
            self._pre_raid_loot = loot
            self.state = BotState.DEPLOYING
        else:
            self.stats.total_skips += 1
            self._consecutive_skips += 1

            # Skip relaxation logic
            if self._consecutive_skips >= self.config.max_consecutive_skips:
                if not self._relaxed_mode:
                    self._relaxed_mode = True
                    self._relaxed_raids_remaining = self.config.skip_relaxed_raids
                    self.log(
                        f'⚠️ {self._consecutive_skips} skips — '
                        f'relaxing thresholds by {self.config.skip_threshold_reduction * 100:.0f}%',
                        'warning'
                    )

            self.log(f'⏭️ SKIP ({self._consecutive_skips}): {reject_reason}', 'info')

            # Tap Next button
            self.touch.tap(self.coords['next_button'][0],
                          self.coords['next_button'][1])
            time.sleep(1.5)  # Loading next base
            self.state = BotState.SCOUTING

    def _handle_analyzing(self):
        """Detailed analysis before deployment — redundant safety check."""
        # Already handled in scouting, transition immediately
        self.state = BotState.DEPLOYING

    def _handle_deploying(self):
        """Execute attack deployment sequence."""
        if self._current_base is None:
            self.state = BotState.ERROR_RECOVERY
            return

        analysis = self._current_base
        army_comp = self.config.get_army()
        deploy_order = army_comp['deploy_order']
        entry_side = analysis.recommended_entry_side
        deploy_zones = self.coords['deploy_zones']

        self.log(f'⚔️ ATTACKING — {army_comp["name"]} via {entry_side}', 'attack')

        # Get deployment positions for entry side
        primary_zone = deploy_zones.get(entry_side, deploy_zones['top_left'])
        # Also deploy on adjacent sides for funneling
        adjacent_zones = self._get_adjacent_zones(entry_side, deploy_zones)

        troop_slots = self.coords['troop_slots']
        hero_buttons = self.coords['hero_buttons']
        spell_buttons = self.coords['spell_buttons']

        # ─── STEP 1: FUNNEL CHECK (handled by deployment pattern) ───
        self.log('  Step 1: Setting up funnel...', 'info')

        # ─── STEP 2: KILL SQUAD — Heroes + CC ───
        if hero_buttons:
            self.log('  Step 2: Deploying kill squad (heroes)...', 'attack')
            for i, hero_btn in enumerate(hero_buttons[:2]):  # First 2 heroes
                self.touch.tap(hero_btn[0], hero_btn[1])
                time.sleep(0.1)
                zone = primary_zone[0] if primary_zone else (540, 540)
                self.touch.tap(zone[0], zone[1])
                time.sleep(0.3)

        # CC deployment
        if self.coords.get('request_cc_button'):
            self.log('  Deploying CC troops...', 'attack')
            # CC is typically the last troop slot or a separate button
            cc_zone = primary_zone[0] if primary_zone else (540, 540)
            self.touch.tap(cc_zone[0], cc_zone[1])
            time.sleep(0.5)

        # ─── STEP 3: DEPLOY TANKS (Giants/Ice Golems/Super Giants) ───
        tank_names = {'Giant', 'Super Giant', 'Ice Golem', 'Lava Hound'}
        for slot_idx, troop_name in enumerate(deploy_order):
            if troop_name in tank_names and slot_idx < len(troop_slots):
                count = army_comp['troops'].get(troop_name, 0)
                if count > 0:
                    self.log(f'  Step 3: Deploying {count}x {troop_name}...', 'attack')
                    all_zones = primary_zone + [z[0] for z in adjacent_zones if z]
                    self.touch.deploy_troop_line(
                        all_zones[:3], troop_slots[slot_idx], count
                    )
                    time.sleep(self.config.funnel_wait_ms / 1000.0)

        # ─── STEP 4: DEPLOY DPS (Goblins/Bowlers/EDrags/etc) ───
        dps_names = {'Goblin', 'Super Goblin', 'Bowler', 'Witch', 'Electro Dragon',
                     'Yeti', 'Wizard', 'Archer', 'Balloon', 'Healer'}
        for slot_idx, troop_name in enumerate(deploy_order):
            if troop_name in dps_names and slot_idx < len(troop_slots):
                count = army_comp['troops'].get(troop_name, 0)
                if count > 0:
                    self.log(f'  Step 4: Flooding {count}x {troop_name}...', 'attack')
                    all_zones = primary_zone + [z[0] for z in adjacent_zones if z]
                    self.touch.deploy_troop_line(
                        all_zones, troop_slots[slot_idx], count
                    )
                    time.sleep(0.3)

        # ─── STEP 5: DEPLOY WALL BREAKERS ───
        if 'Wall Breaker' in army_comp['troops']:
            count = army_comp['troops']['Wall Breaker']
            for slot_idx, name in enumerate(deploy_order):
                if name == 'Wall Breaker' and slot_idx < len(troop_slots):
                    self.log(f'  Deploying {count}x Wall Breaker...', 'attack')
                    self.touch.deploy_troop_line(
                        primary_zone, troop_slots[slot_idx], count
                    )
                    break

        self.log('  ⚔️ All troops deployed — monitoring attack...', 'attack')
        self.state = BotState.MONITORING_ATTACK

    def _handle_monitoring(self):
        """Monitor ongoing attack — manage spells and hero abilities."""
        time.sleep(self.config.destruction_check_interval_ms / 1000.0)

        # Read destruction percentage
        destruction = self.analyzer.read_destruction_percentage()
        timer = self.analyzer.read_attack_timer()
        loot_drained = self.analyzer.check_loot_drained()

        self.log(
            f'  📊 Destruction: {destruction:.0f}% | Timer: {timer}s | Drained: {loot_drained}',
            'info'
        )

        # ─── SPELL MANAGEMENT ───
        # Drop spells based on conditions
        spell_buttons = self.coords['spell_buttons']
        army_comp = self.config.get_army()

        if 'Haste' in army_comp.get('spells', {}):
            # Drop haste if troops are stalling (low destruction progress)
            if destruction < 30 and timer < 150 and spell_buttons:
                self.log('  💨 Deploying Haste spell...', 'attack')
                self.touch.tap(spell_buttons[0][0], spell_buttons[0][1])
                time.sleep(0.1)
                self.touch.tap(540, 540)  # Center of action
                time.sleep(0.2)

        if 'Healing' in army_comp.get('spells', {}):
            # Drop healing if tanks are low
            if destruction > 20 and timer < 140 and len(spell_buttons) > 1:
                self.log('  💚 Deploying Healing spell...', 'attack')
                self.touch.tap(spell_buttons[1][0], spell_buttons[1][1])
                time.sleep(0.1)
                self.touch.tap(540, 540)
                time.sleep(0.2)

        if 'Rage' in army_comp.get('spells', {}):
            if destruction > 40 and destruction < 65 and len(spell_buttons) > 2:
                self.log('  🔴 Deploying Rage spell...', 'attack')
                self.touch.tap(spell_buttons[2][0], spell_buttons[2][1])
                time.sleep(0.1)
                self.touch.tap(540, 540)
                time.sleep(0.2)

        # ─── HERO ABILITY ACTIVATION ───
        hero_buttons = self.coords['hero_buttons']
        if destruction > 60 and hero_buttons:
            self.log('  👑 Activating hero abilities...', 'attack')
            for hb in hero_buttons[:3]:
                self.touch.tap(hb[0], hb[1])
                time.sleep(0.2)

        # ─── END CONDITIONS ───
        should_end = False

        # 70%+ destruction achieved
        if destruction >= self.config.min_destruction_pct * 100:
            should_end = True
            self.log(f'  ✅ Target destruction reached ({destruction:.0f}%)', 'success')

        # All loot drained
        elif loot_drained:
            should_end = True
            self.log('  ✅ All loot drained', 'success')

        # Time running low with decent loot
        elif timer <= self.config.end_attack_time_remaining and destruction > 40:
            should_end = True
            self.log(f'  ⏰ Time running low ({timer}s) — ending early', 'warning')

        # Attack naturally ending
        elif timer <= 5:
            should_end = True
            self.log('  ⏰ Attack time expired', 'info')

        if should_end:
            self.state = BotState.END_ATTACK

    def _handle_end_attack(self):
        """End the current attack and process results."""
        # Tap end battle button
        self.touch.tap(self.coords['end_battle_button'][0],
                      self.coords['end_battle_button'][1])
        time.sleep(1)

        # Confirm end
        self.touch.tap(self.coords['confirm_end_button'][0],
                      self.coords['confirm_end_button'][1])
        time.sleep(3)  # Wait for results screen

        # Read raid results
        loot_gained = self.analyzer.read_loot()
        army_comp = self.config.get_army()
        troop_cost = army_comp.get('troop_cost_estimate', 0)

        # Update stats
        self.stats.raids_completed += 1
        self.stats.total_gold += loot_gained.gold
        self.stats.total_elixir += loot_gained.elixir
        self.stats.total_de += loot_gained.dark_elixir
        self.stats.total_troop_cost += troop_cost

        # Check net gain
        net_gain = (loot_gained.gold + loot_gained.elixir) - troop_cost
        if net_gain < 100000:
            self.stats.negative_raids += 1
            self._consecutive_negative += 1
        else:
            self._consecutive_negative = 0

        # Log raid
        self.raid_logger.log_raid({
            'gold': loot_gained.gold,
            'elixir': loot_gained.elixir,
            'de': loot_gained.dark_elixir,
            'troop_cost': troop_cost,
            'net_gain': net_gain,
            'army': army_comp['name'],
        })

        self.log(
            f'🏆 RAID #{self.stats.raids_completed}: '
            f'G=+{loot_gained.gold:,} E=+{loot_gained.elixir:,} DE=+{loot_gained.dark_elixir:,} '
            f'Net={net_gain:,} ({self.stats.efficiency_ratio:.1f}:1)',
            'loot'
        )

        # Relaxed mode management
        if self._relaxed_mode:
            self._relaxed_raids_remaining -= 1
            if self._relaxed_raids_remaining <= 0:
                self._relaxed_mode = False
                self._consecutive_skips = 0
                self.log('📊 Threshold relaxation expired — restoring normal thresholds', 'info')

        # Failure recovery — switch army if too many bad raids
        if self._consecutive_negative >= self.config.max_negative_raids:
            self.log('⚠️ 3 consecutive low-yield raids — switching army composition', 'warning')
            self._consecutive_negative = 0
            # Bump TH level config to try different army
            next_th = self.config.th_level + 1
            if next_th > 16:
                next_th = 8
            self.config.th_level = next_th
            self.log(f'🔄 Switched to TH{next_th} army: {self.config.get_army()["name"]}', 'info')

        # Return home
        self.touch.tap(self.coords['return_home_button'][0],
                      self.coords['return_home_button'][1])
        time.sleep(3)

        self.state = BotState.COLLECTING

    def _handle_collecting(self):
        """Collect from builders, mines, etc."""
        self.log('🏗️ Collecting resources...', 'info')

        # Scan screen for collection indicators and tap them
        scan_region = self.coords['builder_collect_scan']
        cx, cy = scan_region[0], scan_region[1]

        # Tap around the base to collect from mines/collectors/drills
        collect_points = [
            (cx - 200, cy - 150), (cx, cy - 150), (cx + 200, cy - 150),
            (cx - 200, cy), (cx, cy), (cx + 200, cy),
            (cx - 200, cy + 150), (cx, cy + 150), (cx + 200, cy + 150),
        ]

        for point in collect_points:
            self.touch.tap(point[0], point[1], delay_after_ms=100)

        time.sleep(1)
        self.log('✅ Resources collected', 'info')

        if self.config.auto_upgrade:
            self.state = BotState.UPGRADING
        else:
            self.state = BotState.QUEUING_ARMY

    def _handle_upgrading(self):
        """Auto-upgrade walls, troops, heroes based on resource levels."""
        game_state = self.analyzer.detect_game_state()

        # Check resource levels
        gold = game_state.current_gold
        elixir = game_state.current_elixir
        de = game_state.current_de

        upgrades = []

        # DE Hero upgrades (priority)
        if de > self.config.de_hero_upgrade_threshold:
            for hero in self.config.hero_priority:
                if self.resources.can_upgrade_hero(hero):
                    self.resources.upgrade_hero(hero, self.touch, self.coords)
                    upgrades.append(f'Hero: {hero}')
                    self.log(f'🔨 Upgrading {hero}', 'success')
                    break

        # Gold → Walls
        if gold > self.config.gold_upgrade_threshold:
            if self.resources.upgrade_wall(self.touch, self.coords):
                upgrades.append('Wall segment')
                self.log('🧱 Upgrading wall segment', 'success')

        # Elixir → Troops/Spells
        if elixir > self.config.elixir_upgrade_threshold:
            if self.resources.upgrade_troop(self.touch, self.coords):
                upgrades.append('Troop/Spell')
                self.log('⬆️ Upgrading troop/spell', 'success')

        self.stats.upgrades_triggered.extend(upgrades)
        self.state = BotState.QUEUING_ARMY

    def _handle_queuing(self):
        """Queue next army immediately after raid."""
        self.log('🔄 Queuing army...', 'info')

        army_comp = self.config.get_army()
        training_time = army_comp.get('training_time_seconds', 600)

        # Navigate to army tab
        self.touch.tap(self.coords['train_troops_button'][0],
                      self.coords['train_troops_button'][1])
        time.sleep(1)

        # Quick train
        if self.coords.get('quick_train_button'):
            self.touch.tap(self.coords['quick_train_button'][0],
                          self.coords['quick_train_button'][1])
            time.sleep(0.5)
            self.touch.tap(self.coords['train_button'][0],
                          self.coords['train_button'][1])
            time.sleep(0.5)

        # Request CC
        if self.coords.get('request_cc_button'):
            self.touch.tap(self.coords['request_cc_button'][0],
                          self.coords['request_cc_button'][1])
            time.sleep(0.5)
            self.log(f'📨 CC requested: {army_comp.get("cc_request", "any")}', 'info')

        self.log(
            f'✅ Army queued: {army_comp["name"]} '
            f'(~{training_time // 60}m training time)',
            'success'
        )

        # Close army screen — tap outside or back
        self.touch.tap(50, 50)
        time.sleep(1)

        # Check if training time exceeds threshold
        if training_time > self.config.max_queue_wait_minutes * 60:
            self.log(
                f'⏳ Queue time ({training_time // 60}m) exceeds threshold '
                f'({self.config.max_queue_wait_minutes}m) — waiting',
                'warning'
            )
            self.state = BotState.WAITING_ARMY
        else:
            # Short enough, go collect and re-check
            self.state = BotState.CHECK_SHIELD

    def _handle_waiting(self):
        """Wait for army to be ready, periodically collecting resources."""
        self.log('⏳ Waiting for army...', 'info')

        # Collect resources while waiting
        self._handle_collecting()

        # Wait in chunks, checking army readiness
        check_interval = 30  # seconds
        for _ in range(check_interval):
            if not self._running:
                return
            time.sleep(1)

        # Check army readiness
        army_ready = self.army.check_army_ready()
        if army_ready >= self.config.min_army_pct:
            self.log(f'💪 Army ready ({army_ready * 100:.0f}%)!', 'success')
            self.state = BotState.CHECK_SHIELD
        else:
            self.log(f'⏳ Army at {army_ready * 100:.0f}% — still waiting...', 'info')
            # Stay in WAITING_ARMY state

    def _handle_error_recovery(self):
        """Recover from errors — try to get back to home screen."""
        self.log('🔧 Attempting error recovery...', 'warning')
        time.sleep(3)

        # Try return home
        self.touch.tap(self.coords['return_home_button'][0],
                      self.coords['return_home_button'][1])
        time.sleep(3)

        # Check state
        game_state = self.analyzer.detect_game_state()
        if game_state.screen == 'home':
            self.log('✅ Recovery successful — back on home screen', 'success')
            self.state = BotState.CHECK_SHIELD
        else:
            self.log('⚠️ Recovery failed — retrying in 5s', 'error')
            time.sleep(5)

    # ─────────────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────────────
    def _get_adjacent_zones(self, side: str, zones: dict) -> list:
        """Get adjacent deployment zones for funneling."""
        adjacency = {
            'top_left': ['top', 'left'],
            'top_right': ['top', 'right'],
            'bottom_left': ['bottom', 'left'],
            'bottom_right': ['bottom', 'right'],
            'top': ['top_left', 'top_right'],
            'bottom': ['bottom_left', 'bottom_right'],
            'left': ['top_left', 'bottom_left'],
            'right': ['top_right', 'bottom_right'],
        }
        adjacent_names = adjacency.get(side, [])
        return [zones.get(name, []) for name in adjacent_names]
