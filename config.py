"""
COC AutoFarmer — Configuration Module
All bot parameters, thresholds, army compositions, and tuning constants.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Tuple, Optional


# ═══════════════════════════════════════════════════════════
# ARMY COMPOSITIONS PER TH LEVEL
# ═══════════════════════════════════════════════════════════
ARMY_COMPOSITIONS = {
    8: {
        'name': 'GiGoWB',
        'troops': {
            'Giant': 12,
            'Goblin': 80,
            'Wall Breaker': 8,
            'Wizard': 4,
            'Archer': 20,
        },
        'spells': {
            'Healing': 2,
            'Rage': 1,
        },
        'cc_request': 'Max Hog Riders or Valkyries',
        'troop_cost_estimate': 85000,
        'training_time_seconds': 600,
        'deploy_order': ['Giant', 'Wall Breaker', 'Wizard', 'Goblin', 'Archer'],
        'priority_targets': ['Collector', 'Drill', 'Mine', 'Storage'],
    },
    9: {
        'name': 'GiGoWB+',
        'troops': {
            'Giant': 14,
            'Goblin': 90,
            'Wall Breaker': 8,
            'Wizard': 6,
            'Archer': 16,
        },
        'spells': {
            'Healing': 2,
            'Rage': 1,
            'Earthquake': 1,
        },
        'cc_request': 'Max Valkyries or Bowlers',
        'troop_cost_estimate': 110000,
        'training_time_seconds': 660,
        'deploy_order': ['Giant', 'Wall Breaker', 'Wizard', 'Goblin', 'Archer'],
        'priority_targets': ['Collector', 'Drill', 'Mine', 'Storage'],
    },
    10: {
        'name': 'BoBat',
        'troops': {
            'Bowler': 14,
            'Witch': 6,
            'Healer': 4,
            'Ice Golem': 2,
            'Wall Breaker': 4,
        },
        'spells': {
            'Healing': 1,
            'Rage': 2,
            'Bat Spell': 3,
            'Freeze': 1,
        },
        'cc_request': 'Max Log Launcher with Yetis',
        'troop_cost_estimate': 185000,
        'training_time_seconds': 900,
        'deploy_order': ['Ice Golem', 'Bowler', 'Witch', 'Healer', 'Wall Breaker'],
        'priority_targets': ['Inferno Tower', 'Eagle Artillery', 'Storage', 'Town Hall'],
    },
    11: {
        'name': 'EDrag Spam',
        'troops': {
            'Electro Dragon': 8,
            'Balloon': 10,
            'Lava Hound': 2,
        },
        'spells': {
            'Rage': 3,
            'Freeze': 2,
            'Haste': 1,
        },
        'cc_request': 'Max Electro Dragon + Balloon',
        'troop_cost_estimate': 280000,
        'training_time_seconds': 1200,
        'deploy_order': ['Lava Hound', 'Electro Dragon', 'Balloon'],
        'priority_targets': ['Air Defense', 'Inferno Tower', 'Storage', 'Town Hall'],
    },
    12: {
        'name': 'Super GiGob',
        'troops': {
            'Super Goblin': 60,
            'Super Giant': 8,
            'Yeti': 4,
            'Wall Breaker': 6,
        },
        'spells': {
            'Jump': 2,
            'Haste': 4,
            'Invisibility': 2,
        },
        'cc_request': 'Max Yetis or Super Bowlers',
        'troop_cost_estimate': 310000,
        'training_time_seconds': 1020,
        'deploy_order': ['Super Giant', 'Yeti', 'Wall Breaker', 'Super Goblin'],
        'priority_targets': ['Dark Elixir Storage', 'DE Drill', 'Storage', 'Collector'],
    },
    13: {
        'name': 'Super GiGob+',
        'troops': {
            'Super Goblin': 70,
            'Super Giant': 10,
            'Yeti': 4,
            'Wall Breaker': 4,
        },
        'spells': {
            'Jump': 2,
            'Haste': 4,
            'Invisibility': 2,
            'Rage': 1,
        },
        'cc_request': 'Max Yetis or Log Launcher',
        'troop_cost_estimate': 350000,
        'training_time_seconds': 1020,
        'deploy_order': ['Super Giant', 'Yeti', 'Wall Breaker', 'Super Goblin'],
        'priority_targets': ['Dark Elixir Storage', 'DE Drill', 'Storage', 'Collector'],
    },
    14: {
        'name': 'Super GiGob Max',
        'troops': {
            'Super Goblin': 70,
            'Super Giant': 10,
            'Yeti': 6,
            'Wall Breaker': 4,
        },
        'spells': {
            'Jump': 2,
            'Haste': 4,
            'Invisibility': 2,
            'Rage': 1,
        },
        'cc_request': 'Max Yetis or Flame Flinger',
        'troop_cost_estimate': 380000,
        'training_time_seconds': 1080,
        'deploy_order': ['Super Giant', 'Yeti', 'Wall Breaker', 'Super Goblin'],
        'priority_targets': ['Dark Elixir Storage', 'DE Drill', 'Storage', 'Collector'],
    },
    15: {
        'name': 'Super GiGob Ultra',
        'troops': {
            'Super Goblin': 80,
            'Super Giant': 12,
            'Yeti': 6,
        },
        'spells': {
            'Jump': 2,
            'Haste': 4,
            'Invisibility': 3,
            'Rage': 1,
        },
        'cc_request': 'Max Yetis or Log Launcher',
        'troop_cost_estimate': 400000,
        'training_time_seconds': 1080,
        'deploy_order': ['Super Giant', 'Yeti', 'Super Goblin'],
        'priority_targets': ['Dark Elixir Storage', 'DE Drill', 'Storage', 'Collector'],
    },
    16: {
        'name': 'Super GiGob Apex',
        'troops': {
            'Super Goblin': 80,
            'Super Giant': 12,
            'Yeti': 8,
        },
        'spells': {
            'Jump': 2,
            'Haste': 5,
            'Invisibility': 3,
            'Rage': 1,
        },
        'cc_request': 'Max Yetis or Log Launcher',
        'troop_cost_estimate': 420000,
        'training_time_seconds': 1140,
        'deploy_order': ['Super Giant', 'Yeti', 'Super Goblin'],
        'priority_targets': ['Dark Elixir Storage', 'DE Drill', 'Storage', 'Collector'],
    },
}


# ═══════════════════════════════════════════════════════════
# SCREEN COORDINATE PROFILES (common device resolutions)
# ═══════════════════════════════════════════════════════════
SCREEN_PROFILES = {
    '1080x2400': {
        'loot_gold_region': (620, 290, 250, 40),
        'loot_elixir_region': (620, 335, 250, 40),
        'loot_de_region': (620, 380, 250, 40),
        'next_button': (980, 600),
        'attack_button': (60, 600),
        'find_match_button': (200, 500),
        'end_battle_button': (80, 640),
        'confirm_end_button': (540, 400),
        'return_home_button': (540, 700),
        'train_troops_button': (160, 640),
        'army_tab': (150, 100),
        'quick_train_button': (900, 100),
        'train_button': (540, 600),
        'request_cc_button': (870, 640),
        'deploy_zones': {
            'top': [(540, 80)],
            'bottom': [(540, 1080)],
            'left': [(80, 540)],
            'right': [(1000, 540)],
            'top_left': [(200, 200)],
            'top_right': [(880, 200)],
            'bottom_left': [(200, 900)],
            'bottom_right': [(880, 900)],
        },
        'hero_buttons': [(300, 640), (380, 640), (460, 640), (540, 640)],
        'spell_buttons': [(620, 640), (700, 640), (780, 640), (860, 640)],
        'troop_slots': [(i * 70 + 100, 640) for i in range(12)],
        'builder_collect_scan': (540, 400, 400, 300),
        'upgrade_button': (540, 500),
        'destruction_pct_region': (480, 30, 120, 35),
        'timer_region': (870, 30, 100, 35),
        'shield_icon_region': (50, 50, 60, 60),
        'clan_war_indicator': (50, 120, 60, 60),
    },
    '1080x1920': {
        'loot_gold_region': (620, 260, 250, 40),
        'loot_elixir_region': (620, 305, 250, 40),
        'loot_de_region': (620, 350, 250, 40),
        'next_button': (960, 540),
        'attack_button': (60, 540),
        'find_match_button': (200, 450),
        'end_battle_button': (80, 580),
        'confirm_end_button': (540, 370),
        'return_home_button': (540, 650),
        'train_troops_button': (160, 580),
        'army_tab': (150, 90),
        'quick_train_button': (880, 90),
        'train_button': (540, 550),
        'request_cc_button': (850, 580),
        'deploy_zones': {
            'top': [(540, 70)],
            'bottom': [(540, 960)],
            'left': [(70, 480)],
            'right': [(1010, 480)],
            'top_left': [(180, 180)],
            'top_right': [(900, 180)],
            'bottom_left': [(180, 800)],
            'bottom_right': [(900, 800)],
        },
        'hero_buttons': [(280, 580), (360, 580), (440, 580), (520, 580)],
        'spell_buttons': [(600, 580), (680, 580), (760, 580), (840, 580)],
        'troop_slots': [(i * 70 + 90, 580) for i in range(12)],
        'builder_collect_scan': (540, 370, 400, 280),
        'upgrade_button': (540, 460),
        'destruction_pct_region': (460, 25, 120, 35),
        'timer_region': (850, 25, 100, 35),
        'shield_icon_region': (45, 45, 55, 55),
        'clan_war_indicator': (45, 110, 55, 55),
    },
}


# ═══════════════════════════════════════════════════════════
# OCR / IMAGE RECOGNITION TEMPLATES
# ═══════════════════════════════════════════════════════════
BUILDING_TEMPLATES = {
    'gold_collector': {'color_range_hsv': [(20, 100, 100), (35, 255, 255)]},
    'elixir_collector': {'color_range_hsv': [(140, 50, 80), (170, 255, 255)]},
    'de_drill': {'color_range_hsv': [(0, 0, 0), (180, 255, 50)]},
    'gold_storage': {'color_range_hsv': [(20, 120, 120), (30, 255, 255)]},
    'elixir_storage': {'color_range_hsv': [(140, 80, 100), (160, 255, 255)]},
    'de_storage': {'color_range_hsv': [(0, 0, 0), (180, 255, 40)]},
    'town_hall': {'color_range_hsv': [(0, 0, 150), (180, 30, 255)]},
    'inferno_tower': {'color_range_hsv': [(0, 150, 150), (10, 255, 255)]},
    'eagle_artillery': {'color_range_hsv': [(100, 50, 100), (120, 255, 200)]},
    'scattershot': {'color_range_hsv': [(30, 50, 100), (50, 200, 200)]},
    'air_defense': {'color_range_hsv': [(0, 0, 100), (180, 50, 200)]},
    'clan_castle': {'color_range_hsv': [(0, 50, 80), (15, 200, 200)]},
}


# ═══════════════════════════════════════════════════════════
# BOT CONFIG DATACLASS
# ═══════════════════════════════════════════════════════════
@dataclass
class BotConfig:
    # Town Hall level
    th_level: int = 11

    # Loot thresholds
    min_gold: int = 150000
    min_elixir: int = 150000
    min_de: int = 1500

    # Collector bias threshold (%)
    min_collector_bias: float = 40.0

    # TH level matching range
    th_match_range: int = 1

    # Skip / relaxation
    max_consecutive_skips: int = 15
    skip_threshold_reduction: float = 0.20
    skip_relaxed_raids: int = 5

    # Efficiency
    min_loot_ratio: float = 3.0
    max_scout_time_ms: int = 8000
    min_army_pct: float = 0.80
    max_queue_wait_minutes: int = 35

    # Resource management thresholds
    gold_upgrade_threshold: int = 4_000_000
    elixir_upgrade_threshold: int = 4_000_000
    de_hero_upgrade_threshold: int = 50_000
    storage_full_pct: float = 0.90

    # Resource priority: DE > Elixir > Gold
    resource_priority: List[str] = field(default_factory=lambda: ['dark_elixir', 'elixir', 'gold'])

    # Hero upgrade priority
    hero_priority: List[str] = field(
        default_factory=lambda: ['Barbarian King', 'Archer Queen', 'Grand Warden', 'Royal Champion']
    )

    # Attack behavior
    min_destruction_pct: float = 0.70
    end_attack_time_remaining: int = 120
    giant_heal_threshold: float = 0.40
    max_attack_duration: int = 180

    # Shield management
    respect_shield: bool = True
    shield_minimum_remaining_seconds: int = 3600

    # Auto upgrade
    auto_upgrade: bool = True

    # Failure recovery
    max_negative_raids: int = 3

    # Screen profile
    screen_profile: str = '1080x2400'

    # Touch timing (ms)
    touch_delay_min: int = 50
    touch_delay_max: int = 180
    swipe_duration: int = 300

    # Deploy timing
    deploy_troop_interval_ms: int = 60
    deploy_spell_delay_ms: int = 200
    funnel_wait_ms: int = 2000
    hero_deploy_delay_ms: int = 3000

    # Scan intervals
    base_scan_interval_ms: int = 500
    loot_check_interval_ms: int = 1000
    destruction_check_interval_ms: int = 2000

    # Logging
    log_raids: bool = True
    log_dir: str = 'logs'

    def get_army(self) -> dict:
        th = max(8, min(16, self.th_level))
        return ARMY_COMPOSITIONS.get(th, ARMY_COMPOSITIONS[12])

    def get_screen_coords(self) -> dict:
        return SCREEN_PROFILES.get(self.screen_profile, SCREEN_PROFILES['1080x2400'])

    def get_relaxed_thresholds(self) -> Tuple[int, int, int]:
        factor = 1.0 - self.skip_threshold_reduction
        return (
            int(self.min_gold * factor),
            int(self.min_elixir * factor),
            int(self.min_de * factor)
        )

    def save(self, path: str = 'config.json'):
        with open(path, 'w') as f:
            json.dump(asdict(self), f, indent=2)

    @classmethod
    def load(cls, path: str = 'config.json') -> 'BotConfig':
        if os.path.exists(path):
            with open(path, 'r') as f:
                data = json.load(f)
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        return cls()
