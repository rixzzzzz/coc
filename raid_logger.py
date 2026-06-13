"""
COC AutoFarmer — Raid Logger Module
Logs every raid with detailed metrics, calculates efficiency,
and exports session summaries.
"""

import os
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger('RaidLogger')


@dataclass
class RaidEntry:
    raid_number: int = 0
    timestamp: str = ''
    gold_gained: int = 0
    elixir_gained: int = 0
    de_gained: int = 0
    troop_cost: int = 0
    net_gain: int = 0
    army_used: str = ''
    destruction_pct: float = 0.0
    attack_duration: int = 0
    base_th_level: int = 0
    collector_bias: float = 0.0
    entry_side: str = ''
    efficiency_ratio: float = 0.0
    is_negative: bool = False
    skips_before: int = 0


class RaidLogger:
    """
    Comprehensive raid logging with per-raid metrics,
    session aggregation, and export capabilities.
    """

    def __init__(self, log_dir: str = 'logs'):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self._raids: List[RaidEntry] = []
        self._session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        self._session_start = time.time()
        self._total_skips = 0

    def log_raid(self, data: Dict) -> RaidEntry:
        """
        Log a completed raid with all metrics.
        Automatically calculates efficiency and flags issues.
        """
        entry = RaidEntry(
            raid_number=len(self._raids) + 1,
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            gold_gained=data.get('gold', 0),
            elixir_gained=data.get('elixir', 0),
            de_gained=data.get('de', 0),
            troop_cost=data.get('troop_cost', 0),
            net_gain=data.get('net_gain', 0),
            army_used=data.get('army', 'Unknown'),
            destruction_pct=data.get('destruction_pct', 0.0),
            attack_duration=data.get('attack_duration', 0),
            base_th_level=data.get('base_th', 0),
            collector_bias=data.get('collector_bias', 0.0),
            entry_side=data.get('entry_side', ''),
            skips_before=data.get('skips_before', 0),
        )

        # Calculate efficiency
        total_loot = entry.gold_gained + entry.elixir_gained
        if entry.troop_cost > 0:
            entry.efficiency_ratio = total_loot / entry.troop_cost
        else:
            entry.efficiency_ratio = 0.0

        entry.is_negative = entry.net_gain < 0

        self._raids.append(entry)

        # Log to file
        self._write_raid_line(entry)

        if entry.is_negative:
            logger.warning(
                f'⚠️ Negative raid #{entry.raid_number}: '
                f'net={entry.net_gain:,} ratio={entry.efficiency_ratio:.2f}'
            )
        else:
            logger.info(
                f'✅ Raid #{entry.raid_number}: '
                f'G=+{entry.gold_gained:,} E=+{entry.elixir_gained:,} DE=+{entry.de_gained:,} '
                f'net=+{entry.net_gain:,} ratio={entry.efficiency_ratio:.2f}'
            )

        return entry

    def _write_raid_line(self, entry: RaidEntry):
        """Append raid entry to session log file."""
        log_path = os.path.join(self.log_dir, f'session_{self._session_id}.jsonl')
        try:
            with open(log_path, 'a') as f:
                f.write(json.dumps(asdict(entry)) + '\n')
        except Exception as e:
            logger.error(f'Failed to write raid log: {e}')

    def get_session_stats(self) -> Dict:
        """Calculate aggregate session statistics."""
        if not self._raids:
            return {
                'raids': 0, 'total_gold': 0, 'total_elixir': 0,
                'total_de': 0, 'avg_loot': 0, 'troop_cost': 0,
                'net_efficiency': '0:0', 'upgrades': [],
            }

        total_gold = sum(r.gold_gained for r in self._raids)
        total_elixir = sum(r.elixir_gained for r in self._raids)
        total_de = sum(r.de_gained for r in self._raids)
        total_cost = sum(r.troop_cost for r in self._raids)
        total_net = sum(r.net_gain for r in self._raids)
        avg_loot = (total_gold + total_elixir) // max(1, len(self._raids))

        if total_cost > 0:
            efficiency = (total_gold + total_elixir) / total_cost
        else:
            efficiency = 0.0

        negative_count = sum(1 for r in self._raids if r.is_negative)
        best_raid = max(self._raids, key=lambda r: r.net_gain)
        worst_raid = min(self._raids, key=lambda r: r.net_gain)

        elapsed = time.time() - self._session_start
        loot_per_hour = int((total_gold + total_elixir + total_de * 100) / max(1, elapsed / 3600))

        return {
            'session_id': self._session_id,
            'raids_completed': len(self._raids),
            'total_gold': total_gold,
            'total_elixir': total_elixir,
            'total_de': total_de,
            'total_troop_cost': total_cost,
            'total_net_gain': total_net,
            'avg_loot_per_raid': avg_loot,
            'avg_gold_per_raid': total_gold // max(1, len(self._raids)),
            'avg_elixir_per_raid': total_elixir // max(1, len(self._raids)),
            'avg_de_per_raid': total_de // max(1, len(self._raids)),
            'efficiency_ratio': f'{efficiency:.1f}:1',
            'negative_raids': negative_count,
            'best_raid': {
                'number': best_raid.raid_number,
                'net_gain': best_raid.net_gain,
                'army': best_raid.army_used,
            },
            'worst_raid': {
                'number': worst_raid.raid_number,
                'net_gain': worst_raid.net_gain,
                'army': worst_raid.army_used,
            },
            'total_skips': self._total_skips,
            'loot_per_hour': loot_per_hour,
            'session_duration_seconds': int(elapsed),
        }

    def get_recent_raids(self, count: int = 5) -> List[Dict]:
        """Get the most recent raid entries."""
        recent = self._raids[-count:]
        return [asdict(r) for r in recent]

    def get_performance_trend(self) -> Dict:
        """Analyze performance trend over recent raids."""
        if len(self._raids) < 5:
            return {'trend': 'insufficient_data'}

        recent_5 = self._raids[-5:]
        earlier_5 = self._raids[-10:-5] if len(self._raids) >= 10 else self._raids[:5]

        recent_avg = sum(r.net_gain for r in recent_5) / len(recent_5)
        earlier_avg = sum(r.net_gain for r in earlier_5) / len(earlier_5)

        if recent_avg > earlier_avg * 1.1:
            trend = 'improving'
        elif recent_avg < earlier_avg * 0.9:
            trend = 'declining'
        else:
            trend = 'stable'

        return {
            'trend': trend,
            'recent_avg_net': int(recent_avg),
            'earlier_avg_net': int(earlier_avg),
            'change_pct': ((recent_avg - earlier_avg) / max(1, abs(earlier_avg))) * 100,
        }

    def export_session(self, format: str = 'json') -> str:
        """Export full session data to file."""
        stats = self.get_session_stats()
        raids_data = [asdict(r) for r in self._raids]

        export_data = {
            'session_summary': stats,
            'raids': raids_data,
            'performance_trend': self.get_performance_trend(),
        }

        if format == 'json':
            export_path = os.path.join(self.log_dir, f'export_{self._session_id}.json')
            with open(export_path, 'w') as f:
                json.dump(export_data, f, indent=2)
        elif format == 'csv':
            export_path = os.path.join(self.log_dir, f'export_{self._session_id}.csv')
            if raids_data:
                import csv
                with open(export_path, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=raids_data[0].keys())
                    writer.writeheader()
                    writer.writerows(raids_data)
        else:
            export_path = os.path.join(self.log_dir, f'export_{self._session_id}.txt')
            with open(export_path, 'w') as f:
                f.write(self.format_session_report())

        logger.info(f'Session exported to: {export_path}')
        return export_path

    def format_session_report(self) -> str:
        """Format session stats as a readable report."""
        stats = self.get_session_stats()
        elapsed = stats.get('session_duration_seconds', 0)
        h = elapsed // 3600
        m = (elapsed % 3600) // 60
        s = elapsed % 60

        report = f"""
╔══════════════════════════════════════════════╗
║         COC AutoFarmer Session Report        ║
╠══════════════════════════════════════════════╣
║ Session ID    : {stats['session_id']:<28} ║
║ Duration      : {h:02d}:{m:02d}:{s:02d}                        ║
╠══════════════════════════════════════════════╣
║ Raids completed    : {stats['raids_completed']:<23} ║
║ Total Gold gained  : +{stats['total_gold']:>20,} ║
║ Total Elixir gained: +{stats['total_elixir']:>20,} ║
║ Total DE gained    : +{stats['total_de']:>20,} ║
║ Avg loot/raid      : {stats['avg_loot_per_raid']:>21,} ║
║ Troop cost total   : {stats['total_troop_cost']:>21,} ║
║ Net efficiency     : {stats['efficiency_ratio']:>21} ║
║ Loot/hour          : {stats['loot_per_hour']:>21,} ║
║ Negative raids     : {stats['negative_raids']:>21} ║
║ Total skips        : {stats['total_skips']:>21} ║
╠══════════════════════════════════════════════╣
║ Best raid  : #{stats['best_raid']['number']:<3} net +{stats['best_raid']['net_gain']:>13,} ║
║ Worst raid : #{stats['worst_raid']['number']:<3} net {stats['worst_raid']['net_gain']:>14,} ║
╚══════════════════════════════════════════════╝
"""
        return report

    def increment_skips(self, count: int = 1):
        """Track total skips."""
        self._total_skips += count

    def reset(self):
        """Reset logger for new session."""
        self._raids.clear()
        self._session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        self._session_start = time.time()
        self._total_skips = 0
