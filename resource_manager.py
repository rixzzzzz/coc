"""
COC AutoFarmer — Resource Manager Module
Handles resource tracking, auto-upgrade logic for walls/heroes/troops,
builder management, and storage monitoring.
"""

import time
import logging
from typing import Dict, List, Optional, Tuple
from config import BotConfig

logger = logging.getLogger('ResourceManager')


# ═══════════════════════════════════════════════════════════
# UPGRADE COST TABLES (approximate per TH level)
# ═══════════════════════════════════════════════════════════
WALL_COSTS = {
    8: {'gold': 500000, 'elixir': 500000},
    9: {'gold': 1000000, 'elixir': 1000000},
    10: {'gold': 2000000, 'elixir': 2000000},
    11: {'gold': 3000000, 'elixir': 3000000},
    12: {'gold': 4000000, 'elixir': 4000000},
    13: {'gold': 5000000, 'elixir': 5000000},
    14: {'gold': 6000000, 'elixir': 6000000},
    15: {'gold': 7000000, 'elixir': 7000000},
    16: {'gold': 8000000, 'elixir': 8000000},
}

HERO_COSTS = {
    'Barbarian King': {
        'resource': 'dark_elixir',
        'costs_by_level': {i: 10000 + (i * 5000) for i in range(1, 91)},
        'upgrade_time_hours': {i: min(168, 24 + i * 2) for i in range(1, 91)},
    },
    'Archer Queen': {
        'resource': 'dark_elixir',
        'costs_by_level': {i: 12000 + (i * 5500) for i in range(1, 91)},
        'upgrade_time_hours': {i: min(168, 24 + i * 2) for i in range(1, 91)},
    },
    'Grand Warden': {
        'resource': 'elixir',
        'costs_by_level': {i: 3000000 + (i * 1000000) for i in range(1, 71)},
        'upgrade_time_hours': {i: min(168, 24 + i * 2) for i in range(1, 71)},
    },
    'Royal Champion': {
        'resource': 'dark_elixir',
        'costs_by_level': {i: 80000 + (i * 10000) for i in range(1, 41)},
        'upgrade_time_hours': {i: min(168, 24 + i * 3) for i in range(1, 41)},
    },
}


class ResourceManager:
    """
    Manages resource allocation, auto-upgrades, and builder scheduling.
    Implements the priority system: DE Hero > Elixir Troops > Gold Walls.
    """

    def __init__(self, config: BotConfig):
        self.config = config
        self._current_gold = 0
        self._current_elixir = 0
        self._current_de = 0
        self._gold_capacity = 0
        self._elixir_capacity = 0
        self._de_capacity = 0
        self._builders_available = 0
        self._builders_total = 5
        self._hero_levels: Dict[str, int] = {
            'Barbarian King': 1,
            'Archer Queen': 1,
            'Grand Warden': 1,
            'Royal Champion': 1,
        }
        self._hero_upgrading: Dict[str, bool] = {
            'Barbarian King': False,
            'Archer Queen': False,
            'Grand Warden': False,
            'Royal Champion': False,
        }
        self._walls_upgraded = 0
        self._troops_upgraded = 0
        self._upgrades_log: List[str] = []

    # ─────────────────────────────────────────────────────
    # RESOURCE TRACKING
    # ─────────────────────────────────────────────────────
    def update_resources(self, gold: int, elixir: int, de: int):
        """Update current resource levels."""
        self._current_gold = gold
        self._current_elixir = elixir
        self._current_de = de

    def update_capacity(self, gold_cap: int, elixir_cap: int, de_cap: int):
        """Update storage capacities."""
        self._gold_capacity = gold_cap
        self._elixir_capacity = elixir_cap
        self._de_capacity = de_cap

    def is_storage_full(self, resource: str) -> bool:
        """Check if a resource storage is >90% full."""
        if resource == 'gold' and self._gold_capacity > 0:
            return self._current_gold / self._gold_capacity >= self.config.storage_full_pct
        elif resource == 'elixir' and self._elixir_capacity > 0:
            return self._current_elixir / self._elixir_capacity >= self.config.storage_full_pct
        elif resource == 'dark_elixir' and self._de_capacity > 0:
            return self._current_de / self._de_capacity >= self.config.storage_full_pct
        return False

    def get_overflow_resources(self) -> List[str]:
        """Get list of resources that are near capacity."""
        overflow = []
        if self.is_storage_full('gold'):
            overflow.append('gold')
        if self.is_storage_full('elixir'):
            overflow.append('elixir')
        if self.is_storage_full('dark_elixir'):
            overflow.append('dark_elixir')
        return overflow

    # ─────────────────────────────────────────────────────
    # HERO UPGRADES
    # ─────────────────────────────────────────────────────
    def can_upgrade_hero(self, hero_name: str) -> bool:
        """Check if a hero can be upgraded."""
        if hero_name not in HERO_COSTS:
            return False

        if self._hero_upgrading.get(hero_name, False):
            return False

        if self._builders_available <= 0:
            return False

        hero_info = HERO_COSTS[hero_name]
        current_level = self._hero_levels.get(hero_name, 1)
        cost = hero_info['costs_by_level'].get(current_level, 999999999)

        resource_type = hero_info['resource']
        if resource_type == 'dark_elixir':
            return self._current_de >= cost
        elif resource_type == 'elixir':
            return self._current_elixir >= cost
        elif resource_type == 'gold':
            return self._current_gold >= cost

        return False

    def upgrade_hero(self, hero_name: str, touch_controller, coords: dict) -> bool:
        """
        Execute hero upgrade through UI interaction.
        Navigates to hero altar, taps upgrade, confirms.
        """
        if not self.can_upgrade_hero(hero_name):
            return False

        current_level = self._hero_levels.get(hero_name, 1)
        cost = HERO_COSTS[hero_name]['costs_by_level'].get(current_level, 0)

        logger.info(f'Upgrading {hero_name} to level {current_level + 1} (cost: {cost})')

        # In practice, this would:
        # 1. Find hero altar on screen
        # 2. Tap it
        # 3. Tap upgrade button
        # 4. Confirm

        # Simulate the interaction
        # Tap approximate hero altar position (center of base)
        touch_controller.tap(400, 400, delay_after_ms=500)
        time.sleep(0.5)

        # Tap upgrade button
        if 'upgrade_button' in coords:
            touch_controller.tap(coords['upgrade_button'][0],
                               coords['upgrade_button'][1])
            time.sleep(0.5)

        # Confirm
        if 'confirm_end_button' in coords:
            touch_controller.tap(coords['confirm_end_button'][0],
                               coords['confirm_end_button'][1])
            time.sleep(0.5)

        # Update internal state
        self._hero_upgrading[hero_name] = True
        self._hero_levels[hero_name] = current_level + 1
        self._builders_available = max(0, self._builders_available - 1)
        self._upgrades_log.append(f'{hero_name} → Lv{current_level + 1}')

        # Deduct cost
        resource_type = HERO_COSTS[hero_name]['resource']
        if resource_type == 'dark_elixir':
            self._current_de -= cost
        elif resource_type == 'elixir':
            self._current_elixir -= cost
        elif resource_type == 'gold':
            self._current_gold -= cost

        return True

    # ─────────────────────────────────────────────────────
    # WALL UPGRADES
    # ─────────────────────────────────────────────────────
    def upgrade_wall(self, touch_controller, coords: dict) -> bool:
        """
        Find and upgrade a wall segment.
        Uses gold or elixir depending on availability.
        """
        if self._builders_available <= 0:
            # Walls can be upgraded without builders in newer TH levels
            pass

        th = self.config.th_level
        wall_cost = WALL_COSTS.get(th, {'gold': 5000000, 'elixir': 5000000})

        can_gold = self._current_gold >= wall_cost['gold']
        can_elixir = self._current_elixir >= wall_cost['elixir']

        if not (can_gold or can_elixir):
            return False

        # Use whichever resource is more abundant
        use_gold = can_gold and (
            not can_elixir or self._current_gold > self._current_elixir
        )

        cost = wall_cost['gold'] if use_gold else wall_cost['elixir']
        resource_name = 'Gold' if use_gold else 'Elixir'

        logger.info(f'Upgrading wall with {resource_name} (cost: {cost})')

        # Navigate to a wall segment
        # Walls are typically on the periphery of the base
        # Tap around edges to find one
        wall_positions = [
            (300, 300), (600, 300), (300, 600), (600, 600),
            (450, 250), (450, 650), (250, 450), (650, 450),
        ]

        for wx, wy in wall_positions:
            touch_controller.tap(wx, wy, delay_after_ms=300)
            time.sleep(0.3)

            # Check if wall selected (upgrade button appears)
            if 'upgrade_button' in coords:
                touch_controller.tap(coords['upgrade_button'][0],
                                   coords['upgrade_button'][1])
                time.sleep(0.3)
                break

        # Deduct cost
        if use_gold:
            self._current_gold -= cost
        else:
            self._current_elixir -= cost

        self._walls_upgraded += 1
        self._upgrades_log.append(f'Wall (x{self._walls_upgraded})')
        return True

    # ─────────────────────────────────────────────────────
    # TROOP/SPELL UPGRADES
    # ─────────────────────────────────────────────────────
    def upgrade_troop(self, touch_controller, coords: dict) -> bool:
        """
        Find cheapest available troop or spell upgrade in the lab.
        """
        if self._builders_available <= 0:
            return False

        if self._current_elixir < self.config.elixir_upgrade_threshold:
            return False

        logger.info('Checking lab for available upgrades...')

        # Navigate to lab
        # Lab is typically near the center-right of the base
        touch_controller.tap(700, 400, delay_after_ms=500)
        time.sleep(1)

        # Check for available upgrade
        if 'upgrade_button' in coords:
            touch_controller.tap(coords['upgrade_button'][0],
                               coords['upgrade_button'][1])
            time.sleep(0.5)

            # Confirm
            if 'confirm_end_button' in coords:
                touch_controller.tap(coords['confirm_end_button'][0],
                                   coords['confirm_end_button'][1])
                time.sleep(0.5)

        self._troops_upgraded += 1
        self._upgrades_log.append(f'Troop/Spell #{self._troops_upgraded}')
        self._builders_available = max(0, self._builders_available - 1)

        return True

    # ─────────────────────────────────────────────────────
    # RESOURCE ALLOCATION STRATEGY
    # ─────────────────────────────────────────────────────
    def decide_upgrades(self) -> List[str]:
        """
        Decide which upgrades to perform based on current resources.
        Returns list of upgrade actions to execute.
        """
        actions = []

        # Priority 1: DE → Heroes
        if self._current_de > self.config.de_hero_upgrade_threshold:
            for hero in self.config.hero_priority:
                if self.can_upgrade_hero(hero):
                    actions.append(f'hero:{hero}')
                    break

        # Priority 2: Gold → Walls (if gold is high)
        if self._current_gold > self.config.gold_upgrade_threshold:
            actions.append('wall:gold')

        # Priority 3: Elixir → Troops/Spells
        if self._current_elixir > self.config.elixir_upgrade_threshold:
            actions.append('troop:elixir')

        # Priority 4: Storage overflow — dump into walls
        overflow = self.get_overflow_resources()
        if 'gold' in overflow and 'wall:gold' not in actions:
            actions.append('wall:overflow_gold')
        if 'elixir' in overflow:
            actions.append('wall:overflow_elixir')

        return actions

    # ─────────────────────────────────────────────────────
    # GETTERS
    # ─────────────────────────────────────────────────────
    def get_upgrades_log(self) -> List[str]:
        """Get list of all upgrades performed this session."""
        return self._upgrades_log.copy()

    def get_resource_summary(self) -> Dict:
        """Get current resource summary."""
        return {
            'gold': self._current_gold,
            'elixir': self._current_elixir,
            'de': self._current_de,
            'gold_pct': (self._current_gold / max(1, self._gold_capacity)) * 100,
            'elixir_pct': (self._current_elixir / max(1, self._elixir_capacity)) * 100,
            'de_pct': (self._current_de / max(1, self._de_capacity)) * 100,
            'builders_free': self._builders_available,
            'builders_total': self._builders_total,
        }
