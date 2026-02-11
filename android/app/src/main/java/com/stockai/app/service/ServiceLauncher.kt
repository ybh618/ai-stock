package com.stockai.app.service

import android.content.Context
import android.content.Intent
import android.os.Build
import android.provider.Settings
import androidx.core.content.ContextCompat

object ServiceLauncher {
    fun startWsForegroundService(context: Context) {
        val serviceIntent = Intent(context, WsForegroundService::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            ContextCompat.startForegroundService(context, serviceIntent)
        } else {
            context.startService(serviceIntent)
        }
    }

    fun startFloatingWidgetService(context: Context) {
        val serviceIntent = Intent(context, FloatingWidgetService::class.java)
        runCatching { context.startService(serviceIntent) }
    }

    fun stopFloatingWidgetService(context: Context) {
        context.stopService(Intent(context, FloatingWidgetService::class.java))
    }

    fun syncFloatingWidgetService(context: Context, enabled: Boolean) {
        if (enabled && canDrawOverlays(context)) {
            startFloatingWidgetService(context)
        } else {
            stopFloatingWidgetService(context)
        }
    }

    fun canDrawOverlays(context: Context): Boolean {
        return Build.VERSION.SDK_INT < Build.VERSION_CODES.M || Settings.canDrawOverlays(context)
    }
}
