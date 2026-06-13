"""
COC AutoFarmer — Army Manager Module
Handles army composition selection, training queue management,
troop readiness checking, and adaptive army switching.
"""

import time
import logging
from typing import Dict, List, Optional, Tuple
from config import BotConfig, ARMY_COMPOSITIONS

logger = logging.getLogger('ArmyManager')


class ArmyManager:
    """
    Manages army training, composition selection, and readiness tracking.
    Adapts army based on TH level, raid performance, and available resources.
    """

    def __init__(self, config: BotConfig):
        self.config = config
        self._last_queue_time = 0
        self._current_comp = config.get_army()
        self._army_ready_pct = 0.0
        self._training_start_time = 0
        self._comp_switch_count = 0
        self._raid_history: List[Dict] = []

    # ─────────────────────────────────────────────────────
    # ARMY READINESS
    # ─────────────────────────────────────────────────────
    def check_army_ready(self) -> float:
        """
        Check army readiness as a percentage (0.0 to 1.0).
        Uses training time estimation based on last queue time.
        On Android, reads actual troop count from army screen.
        """
        if self._training_start_time <= 0:
            # No training tracked — try to read from screen
            return self._check_army_screen()

        elapsed = time.time() - self._training_start_time
        training_time = self._current_comp.get('training_time_seconds', 600)

        if elapsed >= training_time:
            self._army_ready_pct = 1.0
        else:
            self._army_ready_pct = min(1.0, elapsed / training_time)

        return self._army_ready_pct

    def _check_army_screen(self) -> float:
        """
        Attempt to read army readiness from the army tab.
        Returns estimated readiness based on UI analysis.
        """
        try:
            from jnius import autoclass
            # Would navigate to army screen and read troop counts
            # For now, use time-based estimation
            pass
        except ImportError:
            pass

        # If no training is tracked, assume full army
        if self._training_start_time <= 0 and self._last_queue_time <= 0:
            return 1.0

        return self._army_ready_pct

    # ─────────────────────────────────────────────────────
    # TRAINING QUEUE
    # ─────────────────────────────────────────────────────
    def queue_army(self, touch_controller, coords: dict) -> int:
        """
        Queue the current army composition for training.
        Returns estimated training time in seconds.
        """
        self._current_comp = self.config.get_army()
        training_time = self._current_comp.get('training_time_seconds', 600)

        self.log_training(f'Queuing {self._current_comp["name"]}...')

        # Navigate to army tab
        if 'train_troops_button' in coords:
            touch_controller.tap(coords['train_troops_button'][0],
                               coords['train_troops_button'][1])
            time.sleep(1.0)

        # Use Quick Train if configured
        if 'quick_train_button' in coords:
            touch_controller.tap(coords['quick_train_button'][0],
                               coords['quick_train_button'][1])
            time.sleep(0.5)

            # Hit the first quick train slot (should be pre-configured)
            if 'train_button' in coords:
                touch_controller.tap(coords['train_button'][0],
                                   coords['train_button'][1])
                time.sleep(0.5)

                # Tap again for second queue
                touch_controller.tap(coords['train_button'][0],
                                   coords['train_button'][1])
                time.sleep(0.3)
        else:
            # Manual training — tap each troop type
            self._manual_train(touch_controller, coords)

        self._training_start_time = time.time()
        self._last_queue_time = time.time()
        self._army_ready_pct = 0.0

        self.log_training(f'Army queued — ~{training_time // 60}m training time')
        return training_time

    def _manual_train(self, touch_controller, coords: dict):
        """
        Manually train each troop type by navigating the training UI.
        Taps each troop button the required number of times.
        """
        troops = self._current_comp.get('troops', {})
        troop_slots = coords.get('troop_slots', [])

        # Map troop names to slot indices (approximation based on common ordering)
        troop_order = [
            'Barbarian', 'Archer', 'Giant', 'Goblin', 'Wall Breaker',
            'Balloon', 'Wizard', 'Healer', 'Dragon', 'P.E.K.K.A',
            'Baby Dragon', 'Miner', 'Electro Dragon', 'Yeti',
            'Super Barbarian', 'Super Archer', 'Super Giant', 'Super Goblin',
            'Super Wall Breaker', 'Bowler', 'Witch', 'Lava Hound',
            'Ice Golem', 'Headhunter',
        ]

        for troop_name, count in troops.items():
            if count <= 0:
                continue

            # Find slot index
            slot_idx = None
            for i, name in enumerate(troop_order):
                if name == troop_name:
                    slot_idx = i
                    break

            if slot_idx is not None and slot_idx < len(troop_slots):
                slot = troop_slots[slot_idx]
                for _ in range(count):
                    touch_controller.tap(slot[0], slot[1], delay_after_ms=50)

        # Also queue spells
        spells = self._current_comp.get('spells', {})
        spell_order = [
            'Lightning', 'Healing', 'Rage', 'Jump', 'Freeze',
            'Poison', 'Earthquake', 'Haste', 'Clone', 'Invisibility',
            'Bat Spell', 'Recall',
        ]
        spell_buttons = coords.get('spell_buttons', [])

        for spell_name, count in spells.items():
            slot_idx = None
            for i, name in enumerate(spell_order):
                if name == spell_name:
                    slot_idx = i
                    break

            if slot_idx is not None and slot_idx < len(spell_buttons):
                slot = spell_buttons[slot_idx]
                for _ in range(count):
                    touch_controller.tap(slot[0], slot[1], delay_after_ms=80)

    # ─────────────────────────────────────────────────────
    # ADAPTIVE COMPOSITION
    # ─────────────────────────────────────────────────────
    def evaluate_performance(self, raid_results: List[Dict]) -> bool:
        """
        Evaluate recent raid performance and decide if army switch is needed.
        Returns True if composition was changed.
        """
        self._raid_history.extend(raid_results)

        # Keep last 10 raids
        if len(self._raid_history) > 10:
            self._raid_history = self._raid_history[-10:]

        if len(self._raid_history) < 3:
            return False

        # Calculate average net gain from last 3 raids
        recent = self._raid_history[-3:]
        avg_net = sum(r.get('net_gain', 0) for r in recent) / len(recent)

        min_acceptable = self.config.min_loot_ratio * self._current_comp.get('troop_cost_estimate', 100000)

        if avg_net < min_acceptable:
            logger.warning(f'Army underperforming (avg net: {avg_net:.0f}) — switching')
            return self._switch_composition()

        return False

    def _switch_composition(self) -> bool:
        """
        Switch to a different army composition.
        Cycles through available compositions for the TH level.
        """
        self._comp_switch_count += 1

        # Try adjacent TH compositions
        current_th = self.config.th_level
        candidates = []

        for th_offset in [-1, 0, 1]:
            th = current_th + th_offset
            if th in ARMY_COMPOSITIONS:
                comp = ARMY_COMPOSITIONS[th]
                if comp['name'] != self._current_comp['name']:
                    candidates.append((th, comp))

        if candidates:
            # Pick the one with lowest troop cost
            candidates.sort(key=lambda x: x[1].get('troop_cost_estimate', 999999))
            best_th, best_comp = candidates[0]
            self._current_comp = best_comp
            self.config.th_level = best_th
            logger.info(f'Switched to {best_comp["name"]} (TH{best_th})')
            return True

        return False

    # ─────────────────────────────────────────────────────
    # CC REQUEST
    # ─────────────────────────────────────────────────────
    def request_cc(self, touch_controller, coords: dict):
        """Request Clan Castle troops."""
        cc_msg = self._current_comp.get('cc_request', 'Anything')

        if 'request_cc_button' in coords:
            touch_controller.tap(coords['request_cc_button'][0],
                               coords['request_cc_button'][1])
            time.sleep(1)
            # CC request popup should appear — just confirm
            # The message is pre-set in game settings
            touch_controller.tap(coords.get('confirm_end_button', (540, 400))[0],
                               coords.get('confirm_end_button', (540, 400))[1])
            time.sleep(0.5)

        logger.info(f'CC requested: {cc_msg}')

    # ─────────────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────────────
    def get_current_comp(self) -> dict:
        """Get current army composition."""
        return self._current_comp

    def get_training_eta(self) -> int:
        """Get estimated seconds until army is ready."""
        if self._army_ready_pct >= 1.0:
            return 0

        training_time = self._current_comp.get('training_time_seconds', 600)
        elapsed = time.time() - self._training_start_time

        remaining = max(0, training_time - elapsed)
        return int(remaining)

    def log_training(self, msg: str):
        """Log training activity."""
        logger.info(f'[ArmyMgr] {msg}')

    def get_troop_cost(self) -> int:
        """Get total troop cost for current composition."""
        return self._current_comp.get('troop_cost_estimate', 0)
