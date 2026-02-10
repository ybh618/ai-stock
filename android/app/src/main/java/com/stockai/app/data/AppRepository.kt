package com.stockai.app.data

import android.content.Context
import com.stockai.app.network.ApiClient
import com.stockai.app.network.RecommendationDto
import com.stockai.app.network.SyncPreferences
import com.stockai.app.network.SyncWatchItem
import com.stockai.app.network.WsConnectionState
import com.stockai.app.network.WsConnectionStatus
import com.stockai.app.network.WsClient
import com.stockai.app.service.NotificationHelper
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.serialization.json.Json
import java.time.LocalTime

class AppRepository private constructor(
    private val context: Context,
    private val preferences: AppPreferences,
    private val database: AppDatabase,
) {
    private val dao = database.dao()
    private val apiClient = ApiClient()
    private val json = Json { ignoreUnknownKeys = true }
    private val _wsConnectionState = MutableStateFlow(WsConnectionState(WsConnectionStatus.DISCONNECTED))
    private var wsClient: WsClient? = null

    fun observePreferences(): Flow<PreferenceState> = preferences.state
    fun observeWsConnectionState(): StateFlow<WsConnectionState> = _wsConnectionState.asStateFlow()

    suspend fun ensureClientId(): String = preferences.ensureClientId()

    suspend fun markDisclaimerAccepted() = preferences.setDisclaimerAccepted(true)

    suspend fun setLocale(locale: String) {
        preferences.setLocale(locale)
        pushSyncState()
    }

    suspend fun setNotificationsEnabled(enabled: Boolean) {
        preferences.setNotificationsEnabled(enabled)
        pushSyncState()
    }

    suspend fun setRiskProfile(profile: String) {
        preferences.setRiskProfile(profile)
        pushSyncState()
    }

    suspend fun setBackendBaseUrl(url: String) {
        val normalized = normalizeBaseUrl(url)
        if (normalized.isBlank()) return
        preferences.setBackendBaseUrl(normalized)
        stopWs()
        startWs()
    }

    suspend fun setQuietHours(startHour: Int, endHour: Int) {
        preferences.setQuietHours(startHour, endHour)
        pushSyncState()
    }

    fun observeRecommendations(clientId: String): Flow<List<RecommendationEntity>> = dao.observeRecommendations(clientId)

    fun observeWatchlist(clientId: String): Flow<List<WatchlistEntity>> = dao.observeWatchlist(clientId)

    suspend fun addWatch(symbol: String, name: String, group: String = "default") {
        val state = preferences.state.first()
        dao.upsertWatchlistItem(
            WatchlistEntity(
                clientId = state.clientId,
                symbol = symbol,
                name = name,
                groupName = group,
                sortIndex = 0
            )
        )
        pushSyncState()
    }

    suspend fun removeWatch(symbol: String) {
        val state = preferences.state.first()
        dao.deleteWatchlistItem(state.clientId, symbol)
        pushSyncState()
    }

    suspend fun startWs() {
        val state = preferences.state.first()
        if (state.clientId.isBlank()) return
        val watchlist = loadWatchlistForSync(state.clientId)
        val syncPrefs = state.toSyncPreferences()
        if (wsClient == null) {
            wsClient = WsClient(
                onRecommendation = { recommendation ->
                    onRecommendation(recommendation)
                },
                onDebugResult = { summary ->
                    onDebugResult(summary)
                },
                onConnectionStateChanged = { state ->
                    _wsConnectionState.value = state
                    NotificationHelper.updateServiceConnectionState(context, state)
                },
            )
        }
        wsClient?.start(
            baseUrl = state.backendBaseUrl,
            clientId = state.clientId,
            prefs = syncPrefs,
            watchlist = watchlist,
        )
        syncRecommendations()
    }

    fun stopWs() {
        wsClient?.stop()
        val disconnected = WsConnectionState(WsConnectionStatus.DISCONNECTED, "manual_stop")
        _wsConnectionState.value = disconnected
        NotificationHelper.updateServiceConnectionState(context, disconnected)
    }

    suspend fun syncRecommendations(limit: Int = 200) {
        val state = preferences.state.first()
        if (state.clientId.isBlank()) return
        val items = apiClient.fetchRecommendations(state.backendBaseUrl, state.clientId, limit)
        items.forEach { persistRecommendation(it) }
        dao.trimRecommendations(state.clientId, 1000)
    }

    suspend fun submitFeedback(recommendationId: Int, helpful: Boolean, reason: String?) {
        val state = preferences.state.first()
        if (state.clientId.isBlank()) return
        apiClient.submitFeedback(
            baseUrl = state.backendBaseUrl,
            clientId = state.clientId,
            recommendationId = recommendationId,
            helpful = helpful,
            reason = reason,
        )
    }

    private suspend fun onRecommendation(item: RecommendationDto) {
        persistRecommendation(item)
        val state = preferences.state.first()
        if (!state.notificationsEnabled) return
        if (isWithinQuietHours(state.quietStartHour, state.quietEndHour)) return
        val useChinese = state.locale != "en"
        NotificationHelper.showRecommendation(context, item, useChinese)
    }

    private suspend fun onDebugResult(summary: String) {
        val state = preferences.state.first()
        if (!state.notificationsEnabled) return
        if (isWithinQuietHours(state.quietStartHour, state.quietEndHour)) return
        NotificationHelper.showDebug(context, summary)
    }

    private suspend fun persistRecommendation(item: RecommendationDto) {
        dao.upsertRecommendation(
            RecommendationEntity(
                id = item.id,
                clientId = item.clientId,
                symbol = item.symbol,
                createdAt = item.createdAt,
                action = item.action,
                targetPositionPct = item.targetPositionPct,
                summaryZh = item.summaryZh,
                summaryEn = item.summaryEn,
                confidence = item.confidence,
                riskJson = json.encodeToString(item.risk),
                evidenceJson = json.encodeToString(item.evidence),
            )
        )
    }

    private suspend fun pushSyncState() {
        val state = preferences.state.first()
        if (state.clientId.isBlank()) return
        val watchlist = loadWatchlistForSync(state.clientId)
        wsClient?.updateSyncState(state.toSyncPreferences(), watchlist)
    }

    private suspend fun loadWatchlistForSync(clientId: String): List<SyncWatchItem> {
        return dao.observeWatchlist(clientId).first().map {
            SyncWatchItem(
                symbol = it.symbol,
                name = it.name,
                group = it.groupName,
                sortIndex = it.sortIndex,
            )
        }
    }

    private fun PreferenceState.toSyncPreferences(): SyncPreferences {
        return SyncPreferences(
            locale = locale,
            riskProfile = riskProfile,
            notificationsEnabled = notificationsEnabled,
            quietStartHour = quietStartHour,
            quietEndHour = quietEndHour,
        )
    }

    private fun isWithinQuietHours(startHour: Int, endHour: Int): Boolean {
        val now = LocalTime.now().hour
        return if (startHour == endHour) {
            false
        } else if (startHour < endHour) {
            now in startHour until endHour
        } else {
            now >= startHour || now < endHour
        }
    }

    private fun normalizeBaseUrl(url: String): String {
        val trimmed = url.trim()
        if (trimmed.isBlank()) return ""
        val withScheme = if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
            trimmed
        } else {
            "http://$trimmed"
        }
        return withScheme.trimEnd('/')
    }

    companion object {
        @Volatile
        private var instance: AppRepository? = null

        fun get(context: Context): AppRepository {
            return instance ?: synchronized(this) {
                instance ?: AppRepository(
                    context = context.applicationContext,
                    preferences = AppPreferences(context.applicationContext),
                    database = AppDatabase.get(context.applicationContext),
                ).also { instance = it }
            }
        }
    }
}
