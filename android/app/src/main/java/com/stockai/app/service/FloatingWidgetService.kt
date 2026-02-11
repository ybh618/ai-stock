package com.stockai.app.service

import android.app.Service
import android.graphics.PixelFormat
import android.os.IBinder
import android.view.Gravity
import android.view.View
import android.view.WindowManager

class FloatingWidgetService : Service() {
    private var windowManager: WindowManager? = null
    private var keepAliveView: View? = null

    override fun onCreate() {
        super.onCreate()
        if (!ServiceLauncher.canDrawOverlays(this)) {
            stopSelf()
            return
        }
        windowManager = getSystemService(WINDOW_SERVICE) as WindowManager
        keepAliveView = View(this).apply {
            alpha = 0f
        }
        runCatching {
            windowManager?.addView(keepAliveView, createWindowLayoutParams())
        }.onFailure {
            stopSelf()
        }
    }

    override fun onStartCommand(intent: android.content.Intent?, flags: Int, startId: Int): Int = START_STICKY

    override fun onDestroy() {
        keepAliveView?.let { view ->
            runCatching { windowManager?.removeView(view) }
        }
        keepAliveView = null
        super.onDestroy()
    }

    override fun onBind(intent: android.content.Intent?): IBinder? = null

    private fun createWindowLayoutParams(): WindowManager.LayoutParams {
        return WindowManager.LayoutParams(
            1,
            1,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE or
                WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
            PixelFormat.TRANSLUCENT,
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = 0
            y = 0
        }
    }
}
