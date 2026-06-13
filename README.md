# 💀 COC AutoFarmer v1.0

Autonomous Clash of Clans farming bot for Android. Runs continuous raid loops with intelligent base selection, adaptive army composition, and automated resource management.

## ⚡ Features

- **Autonomous Farming Loop** — Scout → Analyze → Deploy → Collect → Queue → Repeat
- **Smart Base Selection** — OCR loot reading, collector bias analysis, threat assessment
- **Adaptive Army System** — TH8-TH16 compositions, auto-switches on poor performance
- **Resource Management** — Auto-upgrade heroes, walls, troops based on priority system
- **Session Logging** — Per-raid metrics, efficiency tracking, exportable reports
- **Shield Management** — Respects active shields, uses downtime for upgrades
- **Failure Recovery** — Auto-recovers from errors, connection drops, and bad streaks

## 🏗️ Architecture

```
main.py                  — Kivy UI (status bar, stats, settings, log panel)
bot_engine.py            — Core state machine & farming loop
screen_analyzer.py       — OCR, building detection, game state recognition
army_manager.py          — Army composition & training queue management
resource_manager.py      — Auto-upgrade logic (heroes, walls, troops)
raid_logger.py           — Per-raid logging & session summaries
permissions_manager.py   — Android permission handling
config.py                — All parameters, army tables, screen profiles
java_src/                — Native Android helpers (MediaProjection, ForegroundService)
```

## 📱 Requirements

- Android 8.0+ (API 26)
- Clash of Clans installed
- Permissions: Overlay, Accessibility, MediaProjection, Storage
- Screen resolution: 1080x1920 or 1080x2400 (auto-detected)

## 🔨 Build APK

### Prerequisites (Linux/WSL)
```bash
sudo apt install python3 python3-pip openjdk-17-jdk git zip unzip
pip install buildozer cython
```

### Build
```bash
# Debug build
chmod +x build.sh
./build.sh debug

# Release build
./build.sh release

# Clean
./build.sh clean
```

The first build downloads the Android SDK/NDK (~3GB) and takes 20-40 minutes.
Subsequent builds take 2-5 minutes.

### Install
```bash
# Via ADB
adb install bin/cocfarmer-1.0.0-debug.apk

# Or transfer the APK file to your phone and install manually
```

## ⚙️ Configuration

All parameters are configurable via the in-app Settings panel or `config.py`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| TH Level | 11 | Your Town Hall level (8-16) |
| Min Gold | 150,000 | Minimum gold to accept a base |
| Min Elixir | 150,000 | Minimum elixir to accept a base |
| Min DE | 1,500 | Minimum dark elixir to accept |
| Collector Bias | 40% | Min % of loot in collectors |
| Max Skips | 15 | Skip count before relaxing thresholds |
| Min Ratio | 3:1 | Minimum loot-to-cost ratio |
| Auto Upgrade | ON | Auto-upgrade heroes/walls/troops |
| Respect Shield | ON | Don't attack with active shield |

## 🎯 Army Compositions

| TH Level | Army Name | Strategy |
|----------|-----------|----------|
| TH8-9 | GiGoWB | Giants + Goblins — pure collector raid |
| TH10 | BoBat | Bowler + Witch + Bat Spells |
| TH11 | EDrag Spam | Electro Dragon air farm |
| TH12+ | Super GiGob | Super Goblins + Super Giants + Yeti |

## 📊 Session Reports

After each farming session, the bot outputs:
```
╔══════════════════════════════════════════════╗
║         COC AutoFarmer Session Report        ║
╠══════════════════════════════════════════════╣
║ Raids completed    : 47                      ║
║ Total Gold gained  : +18,500,000             ║
║ Total Elixir gained: +16,200,000             ║
║ Total DE gained    : +85,000                 ║
║ Avg loot/raid      : 738,000                 ║
║ Troop cost total   : 4,200,000               ║
║ Net efficiency     : 8.3:1                   ║
║ Loot/hour          : 4,200,000               ║
╚══════════════════════════════════════════════╝
```

## 🔧 Setup on Device

1. Install the APK
2. Open COC AutoFarmer
3. Tap **🔑 Permissions** → grant all permissions
4. Configure your TH level and thresholds
5. Open Clash of Clans on the same device
6. Switch back to COC AutoFarmer
7. Tap **▶ START**
8. The bot takes over — monitor via the overlay

## ⚠️ Notes

- Configure Quick Train in CoC with your preferred army before using
- Set your CC request message in CoC settings
- Keep device plugged in — farming uses screen capture continuously
- The bot uses ~5% CPU and ~150MB RAM
- Logs are saved to the app's `logs/` directory

## 📁 Project Structure

```
coc-autofarmer/
├── main.py                          # App entry + Kivy UI
├── bot_engine.py                    # State machine + farming loop
├── screen_analyzer.py               # OCR + building detection
├── army_manager.py                  # Army queue + composition
├── resource_manager.py              # Auto-upgrade engine
├── raid_logger.py                   # Raid metrics + export
├── permissions_manager.py           # Android permissions
├── config.py                        # All config + army tables
├── buildozer.spec                   # Android build config
├── build.sh                         # Build script
├── assets/
│   ├── icon.png                     # App icon
│   └── presplash.png                # Splash screen
├── java_src/
│   └── com/cocfarmer/
│       ├── MediaProjectionHelper.java  # Screen capture
│       └── ForegroundService.java      # Background service
└── logs/                            # Session logs
```
