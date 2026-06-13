#!/bin/bash
# ═══════════════════════════════════════════════════════════
# COC AutoFarmer — APK Build Script
# ═══════════════════════════════════════════════════════════
#
# Prerequisites:
#   - Python 3.8+
#   - Buildozer: pip install buildozer
#   - Cython: pip install cython
#   - Android SDK/NDK (auto-downloaded by buildozer)
#   - Java JDK 17+
#   - Linux (Ubuntu/Debian recommended) or WSL
#
# Usage:
#   chmod +x build.sh
#   ./build.sh [debug|release]
#
# First build will take 20-40 minutes (downloads SDK/NDK).
# Subsequent builds: 2-5 minutes.
# ═══════════════════════════════════════════════════════════

set -e

MODE="${1:-debug}"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "╔══════════════════════════════════════╗"
echo "║    COC AutoFarmer APK Builder        ║"
echo "║    Mode: $MODE                       ║"
echo "╚══════════════════════════════════════╝"

# Check dependencies
echo "[1/5] Checking dependencies..."

if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 not found. Install it first."
    exit 1
fi

if ! command -v buildozer &> /dev/null; then
    echo "📦 Installing buildozer..."
    pip install buildozer cython
fi

if ! command -v java &> /dev/null; then
    echo "⚠️  Java not found. Buildozer will try to use its own."
    echo "    For best results: sudo apt install openjdk-17-jdk"
fi

# Install system dependencies (Ubuntu/Debian)
echo "[2/5] Installing system dependencies..."
if command -v apt-get &> /dev/null; then
    sudo apt-get install -y -qq \
        build-essential \
        git \
        zip \
        unzip \
        openjdk-17-jdk \
        autoconf \
        libtool \
        pkg-config \
        zlib1g-dev \
        libncurses5-dev \
        libncursesw5-dev \
        libtinfo5 \
        cmake \
        libffi-dev \
        libssl-dev \
        2>/dev/null || true
fi

# Clean previous builds (optional)
echo "[3/5] Preparing build environment..."
cd "$PROJECT_DIR"

if [ "$MODE" = "clean" ]; then
    echo "🧹 Cleaning build artifacts..."
    rm -rf .buildozer bin
    echo "✅ Clean complete"
    exit 0
fi

# Build
echo "[4/5] Building APK ($MODE)..."
echo "    This may take 20-40 minutes on first run."
echo "    SDK and NDK will be downloaded automatically."
echo ""

if [ "$MODE" = "release" ]; then
    buildozer android release 2>&1 | tee build.log
else
    buildozer android debug 2>&1 | tee build.log
fi

# Check result
echo "[5/5] Checking build result..."

APK_PATH=$(find bin/ -name "*.apk" -type f 2>/dev/null | head -1)

if [ -n "$APK_PATH" ]; then
    APK_SIZE=$(du -h "$APK_PATH" | cut -f1)
    echo ""
    echo "╔══════════════════════════════════════════════╗"
    echo "║           ✅ BUILD SUCCESSFUL!               ║"
    echo "╠══════════════════════════════════════════════╣"
    echo "║ APK: $APK_PATH"
    echo "║ Size: $APK_SIZE"
    echo "╠══════════════════════════════════════════════╣"
    echo "║ Install: adb install $APK_PATH"
    echo "║    or transfer APK to your Android device.   ║"
    echo "╚══════════════════════════════════════════════╝"
else
    echo ""
    echo "╔══════════════════════════════════════════════╗"
    echo "║           ❌ BUILD FAILED                    ║"
    echo "╠══════════════════════════════════════════════╣"
    echo "║ Check build.log for errors.                  ║"
    echo "║ Common fixes:                                ║"
    echo "║   - Install JDK 17: sudo apt install         ║"
    echo "║     openjdk-17-jdk                           ║"
    echo "║   - Accept SDK licenses:                     ║"
    echo "║     buildozer android update                 ║"
    echo "║   - Clear cache: ./build.sh clean            ║"
    echo "╚══════════════════════════════════════════════╝"
    exit 1
fi
