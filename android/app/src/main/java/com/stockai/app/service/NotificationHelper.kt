package com.stockai.app.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat
import com.stockai.app.MainActivity
import com.stockai.app.R
import com.stockai.app.network.RecommendationDto

object NotificationHelper {
    const val CHANNEL_ID = "recommendations"
    const val SERVICE_NOTIFICATION_ID = 1001
    private const val DEBUG_NOTIFICATION_ID = 1002

    fun ensureChannel(context: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val channel = NotificationChannel(
            CHANNEL_ID,
            context.getString(R.string.notifications_channel),
            NotificationManager.IMPORTANCE_DEFAULT
        )
        manager.createNotificationChannel(channel)
    }

    fun buildServiceNotification(context: Context): Notification {
        return NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_notify_sync)
            .setContentTitle(context.getString(R.string.foreground_service_title))
            .setContentText(context.getString(R.string.foreground_service_content))
            .setOngoing(true)
            .build()
    }

    fun showRecommendation(context: Context, item: RecommendationDto, useChinese: Boolean) {
        ensureChannel(context)
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val intent = Intent(context, MainActivity::class.java).apply {
            putExtra("recommendation_id", item.id)
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val pending = PendingIntent.getActivity(
            context,
            item.id,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val titleAction = when (item.action) {
            "buy" -> if (useChinese) "买入" else "BUY"
            "sell" -> if (useChinese) "卖出" else "SELL"
            else -> if (useChinese) "观望" else "HOLD"
        }
        val summary = if (useChinese) item.summaryZh else item.summaryEn
        val notification = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_notify_more)
            .setContentTitle("[$titleAction] ${item.symbol}")
            .setContentText(summary)
            .setStyle(NotificationCompat.BigTextStyle().bigText(summary))
            .setAutoCancel(true)
            .setContentIntent(pending)
            .build()
        manager.notify(item.id, notification)
    }

    fun showDebug(context: Context, summary: String) {
        ensureChannel(context)
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val intent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val pending = PendingIntent.getActivity(
            context,
            DEBUG_NOTIFICATION_ID,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val notification = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_notify_sync)
            .setContentTitle(context.getString(R.string.debug_result_title))
            .setContentText(summary)
            .setStyle(NotificationCompat.BigTextStyle().bigText(summary))
            .setAutoCancel(true)
            .setContentIntent(pending)
            .build()
        manager.notify(DEBUG_NOTIFICATION_ID, notification)
    }
}
