[app]

# App metadata
title = COC AutoFarmer
package.name = cocfarmer
package.domain = com.rex

# Source
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json

# Version
version = 1.0.0

# Application requirements
requirements = python3==3.11.5,hostpython3==3.11.5,kivy==2.3.0,pillow,numpy,pyjnius,android,plyer

# Android-specific
android.permissions = INTERNET,SYSTEM_ALERT_WINDOW,FOREGROUND_SERVICE,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,RECEIVE_BOOT_COMPLETED,WAKE_LOCK
android.api = 33
android.minapi = 26
android.ndk_api = 26
android.sdk = 33
android.ndk = 25b

# Android arch
android.archs = arm64-v8a,x86_64

# Gradle dependencies (OpenCV for image processing)
android.gradle_dependencies = org.opencv:opencv:4.8.0

# Java source files
android.add_src = java_src

# Services
services = ForegroundService:com.cocfarmer.ForegroundService

# Activity configuration
android.manifest.intent_filters =
android.manifest.launch_mode = singleTask

# Presplash and icon
presplash.filename = %(source.dir)s/assets/presplash.png
icon.filename = %(source.dir)s/assets/icon.png

# Orientation
orientation = landscape

# Fullscreen
fullscreen = 1

# Android meta-data for foreground service type
android.meta_data = com.cocfarmer.FOREGROUND_SERVICE_TYPE=mediaProjection

# Allow backup
android.allow_backup = False

# Release settings
android.release_artifact = apk

# Python optimization
android.enable_androidx = True

# Logcat tag
log_level = 2

# Build mode
android.debug = False
android.release = True

# Gradle options
android.accept_sdk_license = True

# Keep Java classes
android.whitelist = com.cocfarmer.*

[buildozer]
log_level = 2
warn_on_root = 0
