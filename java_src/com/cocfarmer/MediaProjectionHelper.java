package com.cocfarmer;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.PixelFormat;
import android.hardware.display.DisplayManager;
import android.hardware.display.VirtualDisplay;
import android.media.Image;
import android.media.ImageReader;
import android.media.projection.MediaProjection;
import android.media.projection.MediaProjectionManager;
import android.os.Handler;
import android.os.HandlerThread;
import android.util.DisplayMetrics;
import android.util.Log;

import java.nio.ByteBuffer;

/**
 * MediaProjectionHelper — Bridges Android's MediaProjection API to Python.
 * Captures screenshots for the bot's screen analysis pipeline.
 */
public class MediaProjectionHelper {

    private static final String TAG = "COCFarmer_MPHelper";
    private static final int VIRTUAL_DISPLAY_FLAGS = DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR;

    private static MediaProjectionHelper sInstance;

    private Activity mActivity;
    private MediaProjection mMediaProjection;
    private MediaProjectionManager mProjectionManager;
    private VirtualDisplay mVirtualDisplay;
    private ImageReader mImageReader;
    private Handler mHandler;
    private HandlerThread mHandlerThread;

    private int mScreenWidth;
    private int mScreenHeight;
    private int mScreenDensity;

    private byte[] mLastCapture;
    private final Object mCaptureLock = new Object();

    private MediaProjectionHelper(Activity activity) {
        mActivity = activity;
        mProjectionManager = (MediaProjectionManager) activity.getSystemService(
                Context.MEDIA_PROJECTION_SERVICE);

        DisplayMetrics metrics = new DisplayMetrics();
        activity.getWindowManager().getDefaultDisplay().getMetrics(metrics);
        mScreenWidth = metrics.widthPixels;
        mScreenHeight = metrics.heightPixels;
        mScreenDensity = metrics.densityDpi;

        // Background handler thread for image capture
        mHandlerThread = new HandlerThread("ScreenCapture");
        mHandlerThread.start();
        mHandler = new Handler(mHandlerThread.getLooper());

        Log.i(TAG, "MediaProjectionHelper initialized: " +
                mScreenWidth + "x" + mScreenHeight + " @" + mScreenDensity + "dpi");
    }

    public static MediaProjectionHelper getInstance(Activity activity) {
        if (sInstance == null) {
            sInstance = new MediaProjectionHelper(activity);
        }
        return sInstance;
    }

    /**
     * Initialize MediaProjection with result from permission request.
     */
    public void initProjection(int resultCode, Intent data) {
        if (mMediaProjection != null) {
            mMediaProjection.stop();
        }

        mMediaProjection = mProjectionManager.getMediaProjection(resultCode, data);

        if (mMediaProjection == null) {
            Log.e(TAG, "Failed to obtain MediaProjection");
            return;
        }

        // Setup ImageReader
        mImageReader = ImageReader.newInstance(
                mScreenWidth, mScreenHeight,
                PixelFormat.RGBA_8888, 2
        );

        mImageReader.setOnImageAvailableListener(new ImageReader.OnImageAvailableListener() {
            @Override
            public void onImageAvailable(ImageReader reader) {
                Image image = null;
                try {
                    image = reader.acquireLatestImage();
                    if (image != null) {
                        Image.Plane[] planes = image.getPlanes();
                        ByteBuffer buffer = planes[0].getBuffer();
                        int pixelStride = planes[0].getPixelStride();
                        int rowStride = planes[0].getRowStride();
                        int rowPadding = rowStride - pixelStride * mScreenWidth;

                        // Create bitmap from buffer
                        byte[] data = new byte[buffer.remaining()];
                        buffer.get(data);

                        synchronized (mCaptureLock) {
                            mLastCapture = data;
                        }
                    }
                } catch (Exception e) {
                    Log.e(TAG, "Image capture error: " + e.getMessage());
                } finally {
                    if (image != null) {
                        image.close();
                    }
                }
            }
        }, mHandler);

        // Create virtual display
        mVirtualDisplay = mMediaProjection.createVirtualDisplay(
                "COCFarmerCapture",
                mScreenWidth, mScreenHeight, mScreenDensity,
                VIRTUAL_DISPLAY_FLAGS,
                mImageReader.getSurface(),
                null, mHandler
        );

        Log.i(TAG, "MediaProjection started successfully");
    }

    /**
     * Capture current screen as RGBA byte array.
     * Returns null if no capture is available.
     */
    public byte[] captureScreen() {
        synchronized (mCaptureLock) {
            if (mLastCapture != null) {
                byte[] copy = new byte[mLastCapture.length];
                System.arraycopy(mLastCapture, 0, copy, 0, mLastCapture.length);
                return copy;
            }
        }
        return null;
    }

    /**
     * Get screen width.
     */
    public int getScreenWidth() {
        return mScreenWidth;
    }

    /**
     * Get screen height.
     */
    public int getScreenHeight() {
        return mScreenHeight;
    }

    /**
     * Stop projection and release resources.
     */
    public void stop() {
        if (mVirtualDisplay != null) {
            mVirtualDisplay.release();
            mVirtualDisplay = null;
        }
        if (mImageReader != null) {
            mImageReader.close();
            mImageReader = null;
        }
        if (mMediaProjection != null) {
            mMediaProjection.stop();
            mMediaProjection = null;
        }
        if (mHandlerThread != null) {
            mHandlerThread.quitSafely();
        }
        Log.i(TAG, "MediaProjection stopped");
    }

    /**
     * Create intent for requesting screen capture permission.
     */
    public Intent createCaptureIntent() {
        return mProjectionManager.createScreenCaptureIntent();
    }

    /**
     * Check if projection is active.
     */
    public boolean isActive() {
        return mMediaProjection != null && mVirtualDisplay != null;
    }
}
