package com.stockai.app.service

import android.app.Service
import android.content.Intent
import android.os.IBinder

class WsForegroundService : Service() {
    override fun onCreate() {
        super.onCreate()
        runCatching {
            NotificationHelper.ensureChannel(this)
            startForeground(
                NotificationHelper.SERVICE_NOTIFICATION_ID,
                NotificationHelper.buildServiceNotification(this)
            )
        }.onFailure {
            stopSelf()
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null
}
