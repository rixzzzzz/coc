"""
COC AutoFarmer — Screen Analyzer Module
Handles OCR, image recognition, loot reading, building detection,
collector bias analysis, and game state identification.
"""

import re
import time
import logging
import struct
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

from config import BotConfig, BUILDING_TEMPLATES

logger = logging.getLogger('ScreenAnalyzer')


# ═══════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════
@dataclass
class LootInfo:
    gold: int = 0
    elixir: int = 0
    dark_elixir: int = 0


@dataclass
class BaseAnalysis:
    loot: LootInfo = None
    th_level: int = 0
    collector_bias: float = 0.0
    has_inferno: bool = False
    has_eagle: bool = False
    has_scattershot: bool = False
    exposed_collectors: List[Tuple[int, int]] = None
    exposed_drills: List[Tuple[int, int]] = None
    exposed_mines: List[Tuple[int, int]] = None
    building_positions: Dict[str, List[Tuple[int, int]]] = None
    threat_level: int = 0
    cc_active: bool = False
    recommended_entry_side: str = 'top_left'

    def __post_init__(self):
        if self.loot is None:
            self.loot = LootInfo()
        if self.exposed_collectors is None:
            self.exposed_collectors = []
        if self.exposed_drills is None:
            self.exposed_drills = []
        if self.exposed_mines is None:
            self.exposed_mines = []
        if self.building_positions is None:
            self.building_positions = {}


@dataclass
class GameState:
    screen: str = 'unknown'  # home, scout, attack, army, chat, war, shop
    shield_active: bool = False
    shield_remaining_seconds: int = 0
    guard_active: bool = False
    clan_war_active: bool = False
    builders_available: int = 0
    army_ready_pct: float = 0.0
    cc_filled: bool = False
    hero_available: Dict[str, bool] = None
    current_gold: int = 0
    current_elixir: int = 0
    current_de: int = 0
    gold_capacity: int = 0
    elixir_capacity: int = 0
    de_capacity: int = 0

    def __post_init__(self):
        if self.hero_available is None:
            self.hero_available = {}


# ═══════════════════════════════════════════════════════════
# SCREEN ANALYZER
# ═══════════════════════════════════════════════════════════
class ScreenAnalyzer:
    """
    Analyzes game screen captures for loot values, building positions,
    threat assessment, collector bias, and game state detection.
    Uses Android MediaProjection API for screen capture and
    OpenCV + custom OCR for recognition.
    """

    def __init__(self, config: BotConfig):
        self.config = config
        self.coords = config.get_screen_coords()
        self._last_capture = None
        self._last_capture_time = 0
        self._ocr_engine = None
        self._cv_available = False
        self._init_engines()

    def _init_engines(self):
        """Initialize OCR and CV engines if available."""
        try:
            import cv2
            self._cv_available = True
            logger.info('OpenCV engine loaded')
        except ImportError:
            logger.warning('OpenCV not available — using fallback pixel analysis')
            self._cv_available = False

    # ─────────────────────────────────────────────────────
    # SCREEN CAPTURE (Android MediaProjection bridge)
    # ─────────────────────────────────────────────────────
    def capture_screen(self) -> Optional[bytes]:
        """
        Capture current screen using Android's MediaProjection API.
        Returns raw RGBA pixel buffer or None on failure.
        On Android, this calls into the Java layer via pyjnius.
        """
        try:
            from jnius import autoclass

            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            MediaProjectionHelper = autoclass('com.cocfarmer.MediaProjectionHelper')
            activity = PythonActivity.mActivity

            helper = MediaProjectionHelper.getInstance(activity)
            if helper is None:
                logger.error('MediaProjection not initialized — request permission first')
                return None

            image_data = helper.captureScreen()
            if image_data is not None:
                self._last_capture = bytes(image_data)
                self._last_capture_time = time.time()
                return self._last_capture
            return None

        except ImportError:
            # Fallback for non-Android testing: generate synthetic data
            logger.debug('Running outside Android — using synthetic capture')
            return self._synthetic_capture()
        except Exception as e:
            logger.error(f'Screen capture failed: {e}')
            return None

    def _synthetic_capture(self) -> bytes:
        """Generate synthetic screen data for testing outside Android."""
        width, height = 1080, 2400
        # Simple RGBA buffer
        data = bytearray(width * height * 4)
        self._last_capture = bytes(data)
        self._last_capture_time = time.time()
        return self._last_capture

    # ─────────────────────────────────────────────────────
    # LOOT READING (OCR)
    # ─────────────────────────────────────────────────────
    def read_loot(self) -> LootInfo:
        """
        Read gold, elixir, and dark elixir values from scout screen.
        Uses region-based OCR on the loot display areas.
        """
        screen = self.capture_screen()
        if screen is None:
            return LootInfo()

        gold_region = self.coords['loot_gold_region']
        elixir_region = self.coords['loot_elixir_region']
        de_region = self.coords['loot_de_region']

        gold = self._ocr_number_region(screen, gold_region)
        elixir = self._ocr_number_region(screen, elixir_region)
        de = self._ocr_number_region(screen, de_region)

        loot = LootInfo(gold=gold, elixir=elixir, dark_elixir=de)
        logger.debug(f'Loot read: G={gold} E={elixir} DE={de}')
        return loot

    def _ocr_number_region(self, screen_data: bytes, region: Tuple[int, int, int, int]) -> int:
        """
        Extract a number from a specific screen region using OCR.
        Region format: (x, y, width, height)
        """
        if self._cv_available:
            return self._ocr_cv(screen_data, region)
        return self._ocr_pixel_match(screen_data, region)

    def _ocr_cv(self, screen_data: bytes, region: Tuple[int, int, int, int]) -> int:
        """OpenCV-based OCR for number extraction."""
        try:
            import cv2
            import numpy as np

            x, y, w, h = region
            # Assuming 1080 width, RGBA format
            screen_width = 1080
            img_array = np.frombuffer(screen_data, dtype=np.uint8)

            if len(img_array) < screen_width * (y + h) * 4:
                return 0

            img_array = img_array.reshape(-1, screen_width, 4)
            roi = img_array[y:y + h, x:x + w, :3]  # BGR channels

            # Preprocessing for number recognition
            gray = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY)
            _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)

            # Find contours (digit segments)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # Sort contours left to right
            contours = sorted(contours, key=lambda c: cv2.boundingRect(c)[0])

            # Match digit templates
            digits = []
            for contour in contours:
                bx, by, bw, bh = cv2.boundingRect(contour)
                if bw > 3 and bh > 8:  # Filter noise
                    digit_roi = thresh[by:by + bh, bx:bx + bw]
                    digit = self._match_digit_template(digit_roi)
                    if digit is not None:
                        digits.append(str(digit))

            if digits:
                try:
                    return int(''.join(digits))
                except ValueError:
                    pass
            return 0

        except Exception as e:
            logger.error(f'CV OCR failed: {e}')
            return 0

    def _match_digit_template(self, digit_roi) -> Optional[int]:
        """Match a digit ROI against templates using pixel density analysis."""
        try:
            import cv2
            import numpy as np

            h, w = digit_roi.shape[:2]
            if h < 5 or w < 3:
                return None

            # Normalize to standard size
            resized = cv2.resize(digit_roi, (10, 14))
            total_pixels = resized.size

            # Calculate features
            white_pct = np.count_nonzero(resized) / total_pixels

            # Split into quadrants
            top_half = resized[:7, :]
            bottom_half = resized[7:, :]
            left_half = resized[:, :5]
            right_half = resized[:, 5:]

            top_pct = np.count_nonzero(top_half) / top_half.size
            bottom_pct = np.count_nonzero(bottom_half) / bottom_half.size
            left_pct = np.count_nonzero(left_half) / left_half.size
            right_pct = np.count_nonzero(right_half) / right_half.size

            # Center row and column
            center_row = resized[6:8, :]
            center_col = resized[:, 4:6]
            center_h_pct = np.count_nonzero(center_row) / center_row.size
            center_v_pct = np.count_nonzero(center_col) / center_col.size

            # Heuristic digit matching based on pixel density features
            if white_pct < 0.15:
                return 1
            elif white_pct > 0.65 and center_h_pct < 0.3:
                return 0
            elif top_pct > 0.5 and bottom_pct < 0.3 and center_h_pct > 0.5:
                return 7
            elif center_h_pct > 0.7 and abs(top_pct - bottom_pct) < 0.15:
                return 8
            elif top_pct > bottom_pct and center_h_pct > 0.5:
                return 9 if right_pct > left_pct else 5
            elif bottom_pct > top_pct and center_h_pct > 0.5:
                return 6
            elif center_h_pct > 0.5 and top_pct > 0.4:
                return 4 if left_pct > right_pct else 3
            elif top_pct > 0.4 and bottom_pct > 0.3:
                return 2

            return None

        except Exception:
            return None

    def _ocr_pixel_match(self, screen_data: bytes, region: Tuple[int, int, int, int]) -> int:
        """Fallback pixel-level number extraction without OpenCV."""
        x, y, w, h = region
        screen_width = 1080

        try:
            digits = []
            # Scan columns for white/yellow pixel clusters (loot text color)
            col_idx = 0
            in_digit = False
            digit_cols = []

            for cx in range(x, x + w):
                col_has_text = False
                for cy in range(y, y + h):
                    offset = (cy * screen_width + cx) * 4
                    if offset + 3 < len(screen_data):
                        r = screen_data[offset]
                        g = screen_data[offset + 1]
                        b = screen_data[offset + 2]
                        # Yellow/white text detection
                        if r > 200 and g > 180 and b < 150:  # Gold color
                            col_has_text = True
                            break
                        elif r > 220 and g > 220 and b > 220:  # White
                            col_has_text = True
                            break

                if col_has_text:
                    if not in_digit:
                        in_digit = True
                        digit_cols = []
                    digit_cols.append(cx)
                else:
                    if in_digit:
                        in_digit = False
                        if len(digit_cols) >= 3:
                            digits.append(len(digit_cols))

            # Approximate digits from column widths
            if digits:
                return self._approximate_number_from_widths(digits)

        except Exception as e:
            logger.debug(f'Pixel OCR failed: {e}')

        return 0

    def _approximate_number_from_widths(self, widths: List[int]) -> int:
        """Approximate a number from digit column widths — rough estimation."""
        num_digits = len(widths)
        if num_digits <= 0:
            return 0
        # Use average width to estimate if it's a 'thick' or 'thin' digit
        avg_w = sum(widths) / len(widths)
        # Generate a rough magnitude-based estimate
        base = 10 ** (num_digits - 1)
        return base * 2  # Conservative estimate

    # ─────────────────────────────────────────────────────
    # BUILDING DETECTION
    # ─────────────────────────────────────────────────────
    def detect_buildings(self) -> Dict[str, List[Tuple[int, int]]]:
        """
        Detect building positions on the base using color segmentation.
        Returns dict mapping building type to list of (x, y) positions.
        """
        screen = self.capture_screen()
        if screen is None:
            return {}

        buildings = {}

        if self._cv_available:
            buildings = self._detect_buildings_cv(screen)
        else:
            buildings = self._detect_buildings_pixel(screen)

        return buildings

    def _detect_buildings_cv(self, screen_data: bytes) -> Dict[str, List[Tuple[int, int]]]:
        """OpenCV-based building detection using HSV color ranges."""
        try:
            import cv2
            import numpy as np

            screen_width = 1080
            img_array = np.frombuffer(screen_data, dtype=np.uint8)
            if len(img_array) < screen_width * 100 * 4:
                return {}

            height = len(img_array) // (screen_width * 4)
            img_array = img_array[:screen_width * height * 4].reshape(height, screen_width, 4)
            rgb = img_array[:, :, :3]
            hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)

            buildings = {}

            for btype, template in BUILDING_TEMPLATES.items():
                lower = np.array(template['color_range_hsv'][0])
                upper = np.array(template['color_range_hsv'][1])
                mask = cv2.inRange(hsv, lower, upper)

                # Morphological cleanup
                kernel = np.ones((5, 5), np.uint8)
                mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
                mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                positions = []
                for contour in contours:
                    area = cv2.contourArea(contour)
                    if 500 < area < 50000:  # Building-sized blobs
                        M = cv2.moments(contour)
                        if M["m00"] > 0:
                            cx = int(M["m10"] / M["m00"])
                            cy = int(M["m01"] / M["m00"])
                            positions.append((cx, cy))

                if positions:
                    buildings[btype] = positions

            return buildings

        except Exception as e:
            logger.error(f'CV building detection failed: {e}')
            return {}

    def _detect_buildings_pixel(self, screen_data: bytes) -> Dict[str, List[Tuple[int, int]]]:
        """Fallback pixel-level building detection."""
        return {}

    # ─────────────────────────────────────────────────────
    # BASE ANALYSIS (full scout evaluation)
    # ─────────────────────────────────────────────────────
    def analyze_base(self) -> BaseAnalysis:
        """
        Full analysis of a scouted base:
        - Read loot values
        - Detect buildings
        - Calculate collector bias
        - Assess defensive threat
        - Determine best entry side
        """
        analysis = BaseAnalysis()

        # Read loot
        analysis.loot = self.read_loot()

        # Detect buildings
        analysis.building_positions = self.detect_buildings()

        # Check for dangerous defenses
        analysis.has_inferno = 'inferno_tower' in analysis.building_positions
        analysis.has_eagle = 'eagle_artillery' in analysis.building_positions
        analysis.has_scattershot = 'scattershot' in analysis.building_positions

        # Get collector/drill positions
        analysis.exposed_collectors = analysis.building_positions.get('gold_collector', [])
        analysis.exposed_drills = analysis.building_positions.get('de_drill', [])
        analysis.exposed_mines = analysis.building_positions.get('elixir_collector', [])

        # Calculate collector bias
        analysis.collector_bias = self._calculate_collector_bias(analysis)

        # Assess threat level (0-10 scale)
        analysis.threat_level = self._assess_threat(analysis)

        # CC detection
        cc_positions = analysis.building_positions.get('clan_castle', [])
        analysis.cc_active = len(cc_positions) > 0

        # Determine best entry side
        analysis.recommended_entry_side = self._find_best_entry(analysis)

        # Estimate TH level from building count heuristics
        analysis.th_level = self._estimate_th_level(analysis)

        logger.info(
            f'Base analysis: G={analysis.loot.gold} E={analysis.loot.elixir} '
            f'DE={analysis.loot.dark_elixir} Bias={analysis.collector_bias:.0f}% '
            f'Threat={analysis.threat_level} Entry={analysis.recommended_entry_side}'
        )

        return analysis

    def _calculate_collector_bias(self, analysis: BaseAnalysis) -> float:
        """
        Estimate what percentage of loot is in collectors vs storages.
        Based on collector fullness heuristic (exposed = likely full).
        """
        total_collectors = (
            len(analysis.exposed_collectors) +
            len(analysis.exposed_drills) +
            len(analysis.exposed_mines)
        )
        total_storages = len(analysis.building_positions.get('gold_storage', []))
        total_storages += len(analysis.building_positions.get('elixir_storage', []))
        total_storages += len(analysis.building_positions.get('de_storage', []))

        total = total_collectors + total_storages
        if total == 0:
            return 50.0  # Unknown, assume 50/50

        # Weigh exposed collectors more heavily
        peripheral_collectors = 0
        center_x, center_y = 540, 540  # Base center approximate

        for pos in (analysis.exposed_collectors + analysis.exposed_drills + analysis.exposed_mines):
            dist = ((pos[0] - center_x) ** 2 + (pos[1] - center_y) ** 2) ** 0.5
            if dist > 300:  # Outside core
                peripheral_collectors += 1

        if total_collectors > 0:
            exposure_ratio = peripheral_collectors / total_collectors
        else:
            exposure_ratio = 0

        # Base collector bias from count ratio, boosted by exposure
        base_bias = (total_collectors / total) * 100
        exposure_boost = exposure_ratio * 20
        return min(100.0, base_bias + exposure_boost)

    def _assess_threat(self, analysis: BaseAnalysis) -> int:
        """Assess defensive threat level on a 0-10 scale."""
        threat = 0

        if analysis.has_inferno:
            inferno_count = len(analysis.building_positions.get('inferno_tower', []))
            threat += inferno_count * 2

        if analysis.has_eagle:
            threat += 3

        if analysis.has_scattershot:
            scatter_count = len(analysis.building_positions.get('scattershot', []))
            threat += scatter_count * 2

        # Air defense clustering
        ad_positions = analysis.building_positions.get('air_defense', [])
        if len(ad_positions) >= 3:
            threat += 1

        return min(10, threat)

    def _find_best_entry(self, analysis: BaseAnalysis) -> str:
        """
        Determine optimal entry side based on collector distribution
        and defensive layout.
        """
        all_targets = (
            analysis.exposed_collectors +
            analysis.exposed_drills +
            analysis.exposed_mines
        )

        if not all_targets:
            return 'top_left'  # Default

        # Calculate center of mass for targets
        avg_x = sum(p[0] for p in all_targets) / len(all_targets)
        avg_y = sum(p[1] for p in all_targets) / len(all_targets)

        # Map to entry side
        center_x, center_y = 540, 540

        if avg_x < center_x and avg_y < center_y:
            return 'top_left'
        elif avg_x >= center_x and avg_y < center_y:
            return 'top_right'
        elif avg_x < center_x and avg_y >= center_y:
            return 'bottom_left'
        else:
            return 'bottom_right'

    def _estimate_th_level(self, analysis: BaseAnalysis) -> int:
        """Estimate TH level from building composition."""
        total_buildings = sum(len(v) for v in analysis.building_positions.values())

        if analysis.has_scattershot:
            return 13
        elif analysis.has_eagle:
            return 11
        elif analysis.has_inferno:
            return 10
        elif total_buildings > 60:
            return 9
        elif total_buildings > 40:
            return 8
        else:
            return 7

    # ─────────────────────────────────────────────────────
    # GAME STATE DETECTION
    # ─────────────────────────────────────────────────────
    def detect_game_state(self) -> GameState:
        """Detect current game screen and state."""
        state = GameState()
        screen = self.capture_screen()

        if screen is None:
            return state

        # Detect which screen we're on based on UI element presence
        state.screen = self._identify_screen(screen)

        # Check shield
        state.shield_active = self._check_shield(screen)

        return state

    def _identify_screen(self, screen_data: bytes) -> str:
        """Identify current game screen from pixel patterns."""
        # Check for attack button (home screen)
        attack_pos = self.coords['attack_button']
        if self._check_pixel_color(screen_data, attack_pos[0], attack_pos[1],
                                    target_r=200, target_g=50, target_b=50, tolerance=50):
            return 'home'

        # Check for Next button (scout screen)
        next_pos = self.coords['next_button']
        if self._check_pixel_color(screen_data, next_pos[0], next_pos[1],
                                    target_r=200, target_g=200, target_b=50, tolerance=50):
            return 'scout'

        # Check for end battle button
        end_pos = self.coords['end_battle_button']
        if self._check_pixel_color(screen_data, end_pos[0], end_pos[1],
                                    target_r=200, target_g=50, target_b=50, tolerance=50):
            return 'attack'

        return 'unknown'

    def _check_shield(self, screen_data: bytes) -> bool:
        """Check if shield icon is visible."""
        region = self.coords['shield_icon_region']
        x, y = region[0], region[1]
        # Shield icon is typically blue/green
        return self._check_pixel_color(screen_data, x + 20, y + 20,
                                        target_r=50, target_g=150, target_b=200, tolerance=60)

    def _check_pixel_color(self, data: bytes, x: int, y: int,
                            target_r: int, target_g: int, target_b: int,
                            tolerance: int = 30) -> bool:
        """Check if pixel at (x,y) matches target color within tolerance."""
        screen_width = 1080
        offset = (y * screen_width + x) * 4

        if offset + 3 >= len(data):
            return False

        r = data[offset]
        g = data[offset + 1]
        b = data[offset + 2]

        return (abs(r - target_r) <= tolerance and
                abs(g - target_g) <= tolerance and
                abs(b - target_b) <= tolerance)

    # ─────────────────────────────────────────────────────
    # ATTACK MONITORING
    # ─────────────────────────────────────────────────────
    def read_destruction_percentage(self) -> float:
        """Read current destruction percentage during attack."""
        screen = self.capture_screen()
        if screen is None:
            return 0.0

        region = self.coords['destruction_pct_region']
        value = self._ocr_number_region(screen, region)
        return min(100.0, float(value))

    def read_attack_timer(self) -> int:
        """Read remaining attack time in seconds."""
        screen = self.capture_screen()
        if screen is None:
            return 180

        region = self.coords['timer_region']
        value = self._ocr_number_region(screen, region)
        return max(0, value)

    def check_loot_drained(self) -> bool:
        """Check if all available loot has been collected during attack."""
        screen = self.capture_screen()
        if screen is None:
            return False

        # Check if loot counters have stopped increasing
        # This requires comparing with previous reads
        current_loot = self.read_loot()

        if hasattr(self, '_last_attack_loot'):
            if (current_loot.gold == self._last_attack_loot.gold and
                current_loot.elixir == self._last_attack_loot.elixir and
                current_loot.dark_elixir == self._last_attack_loot.dark_elixir):
                self._loot_stall_count = getattr(self, '_loot_stall_count', 0) + 1
                if self._loot_stall_count >= 3:
                    return True
            else:
                self._loot_stall_count = 0

        self._last_attack_loot = current_loot
        return False
