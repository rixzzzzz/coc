"""
COC AutoFarmer — Permissions Manager
Handles Android permissions: Accessibility, MediaProjection,
Overlay, and Storage.
"""

import logging
from typing import Dict

logger = logging.getLogger('PermissionsManager')


class PermissionsManager:
    """
    Manages Android permissions required for the bot:
    - SYSTEM_ALERT_WINDOW (overlay)
    - MediaProjection (screen capture)
    - Accessibility Service (touch injection)
    - WRITE_EXTERNAL_STORAGE (logging)
    """

    def __init__(self):
        self._permissions_status: Dict[str, bool] = {
            'Overlay (SYSTEM_ALERT_WINDOW)': False,
            'Screen Capture (MediaProjection)': False,
            'Accessibility Service': False,
            'Storage (WRITE_EXTERNAL_STORAGE)': False,
            'Foreground Service': False,
        }
        self._android_available = False
        self._init_android()

    def _init_android(self):
        """Check if running on Android."""
        try:
            from jnius import autoclass
            self._android_available = True
            self._PythonActivity = autoclass('org.kivy.android.PythonActivity')
            self._Settings = autoclass('android.provider.Settings')
            self._Intent = autoclass('android.content.Intent')
            self._Build = autoclass('android.os.Build')
            self._Context = autoclass('android.content.Context')
        except ImportError:
            self._android_available = False
            logger.info('Not running on Android — permissions in mock mode')

    def check_all(self) -> Dict[str, bool]:
        """Check status of all required permissions."""
        if not self._android_available:
            # Mock mode — all granted for testing
            return {k: True for k in self._permissions_status}

        self._check_overlay()
        self._check_accessibility()
        self._check_storage()
        self._check_media_projection()
        self._check_foreground_service()

        return self._permissions_status.copy()

    def _check_overlay(self):
        """Check SYSTEM_ALERT_WINDOW permission."""
        try:
            activity = self._PythonActivity.mActivity
            can_draw = self._Settings.canDrawOverlays(activity)
            self._permissions_status['Overlay (SYSTEM_ALERT_WINDOW)'] = can_draw
        except Exception as e:
            logger.error(f'Overlay check failed: {e}')

    def _check_accessibility(self):
        """Check if our accessibility service is enabled."""
        try:
            activity = self._PythonActivity.mActivity
            ContentResolver = activity.getContentResolver()
            enabled = self._Settings.Secure.getString(
                ContentResolver,
                self._Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
            )
            if enabled and 'cocfarmer' in str(enabled).lower():
                self._permissions_status['Accessibility Service'] = True
            else:
                self._permissions_status['Accessibility Service'] = False
        except Exception as e:
            logger.error(f'Accessibility check failed: {e}')

    def _check_storage(self):
        """Check storage permission."""
        try:
            from android.permissions import check_permission, Permission
            has_storage = check_permission(Permission.WRITE_EXTERNAL_STORAGE)
            self._permissions_status['Storage (WRITE_EXTERNAL_STORAGE)'] = has_storage
        except Exception:
            # Newer Android doesn't need this
            self._permissions_status['Storage (WRITE_EXTERNAL_STORAGE)'] = True

    def _check_media_projection(self):
        """Check MediaProjection availability."""
        try:
            from jnius import autoclass
            MediaProjectionManager = autoclass('android.media.projection.MediaProjectionManager')
            activity = self._PythonActivity.mActivity
            mpm = activity.getSystemService(activity.MEDIA_PROJECTION_SERVICE)
            self._permissions_status['Screen Capture (MediaProjection)'] = mpm is not None
        except Exception as e:
            logger.error(f'MediaProjection check failed: {e}')

    def _check_foreground_service(self):
        """Check if foreground service is running."""
        self._permissions_status['Foreground Service'] = True  # Managed by app

    def request_overlay(self):
        """Open overlay permission settings."""
        if not self._android_available:
            return

        try:
            from jnius import autoclass
            Uri = autoclass('android.net.Uri')
            activity = self._PythonActivity.mActivity
            intent = self._Intent(
                self._Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                Uri.parse(f'package:{activity.getPackageName()}')
            )
            activity.startActivity(intent)
        except Exception as e:
            logger.error(f'Failed to open overlay settings: {e}')

    def request_accessibility(self):
        """Open accessibility settings."""
        if not self._android_available:
            return

        try:
            activity = self._PythonActivity.mActivity
            intent = self._Intent(self._Settings.ACTION_ACCESSIBILITY_SETTINGS)
            activity.startActivity(intent)
        except Exception as e:
            logger.error(f'Failed to open accessibility settings: {e}')

    def request_media_projection(self):
        """Request MediaProjection permission."""
        if not self._android_available:
            return

        try:
            from jnius import autoclass
            MediaProjectionManager = autoclass('android.media.projection.MediaProjectionManager')
            activity = self._PythonActivity.mActivity
            mpm = activity.getSystemService(activity.MEDIA_PROJECTION_SERVICE)
            intent = mpm.createScreenCaptureIntent()
            activity.startActivityForResult(intent, 1001)
        except Exception as e:
            logger.error(f'Failed to request MediaProjection: {e}')

    def request_all(self):
        """Request all missing permissions."""
        status = self.check_all()

        if not status.get('Overlay (SYSTEM_ALERT_WINDOW)', False):
            self.request_overlay()

        if not status.get('Accessibility Service', False):
            self.request_accessibility()

        if not status.get('Screen Capture (MediaProjection)', False):
            self.request_media_projection()
