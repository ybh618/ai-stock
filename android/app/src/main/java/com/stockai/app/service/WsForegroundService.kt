package com.stockai.app.service

import android.app.Service
import android.content.Intent
import android.os.IBinder
import com.stockai.app.data.AppRepository
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch

class WsForegroundService : Service() {
    private val repo by lazy { AppRepository.get(applicationContext) }
    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

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
            return
        }
        serviceScope.launch {
            repo.ensureClientId()
            repo.startWs()
        }
        serviceScope.launch {
            repo.observePreferences().collectLatest { prefs ->
                ServiceLauncher.syncFloatingWidgetService(
                    context = this@WsForegroundService,
                    enabled = prefs.floatingWindowEnabled,
                )
            }
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        serviceScope.launch {
            repo.startWs()
        }
        return START_STICKY
    }

    override fun onDestroy() {
        serviceScope.cancel()
        repo.stopWs()
        ServiceLauncher.stopFloatingWidgetService(this)
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null
}
