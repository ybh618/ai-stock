package com.stockai.app.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.stockai.app.data.AppRepository
import com.stockai.app.data.PreferenceState
import com.stockai.app.data.RecommendationEntity
import com.stockai.app.data.WatchlistEntity
import com.stockai.app.network.DiscoverStockDto
import com.stockai.app.network.NewsItemDto
import com.stockai.app.network.RecommendationStatusDto
import com.stockai.app.network.WsConnectionState
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

class MainViewModel(application: Application) : AndroidViewModel(application) {
    private val repo = AppRepository.get(application)

    val prefs: StateFlow<PreferenceState> = repo.observePreferences()
        .stateIn(
            viewModelScope,
            SharingStarted.WhileSubscribed(5_000),
            PreferenceState(
                clientId = "",
                locale = "system",
                disclaimerAccepted = false,
                notificationsEnabled = true,
                riskProfile = "neutral",
                backendBaseUrl = "http://10.0.2.2:3005",
                quietStartHour = 22,
                quietEndHour = 8,
                autoStartEnabled = true,
                floatingWindowEnabled = false,
                discoverModeEnabled = false,
            ),
        )

    private val _recommendations = MutableStateFlow<List<RecommendationEntity>>(emptyList())
    private val _watchlist = MutableStateFlow<List<WatchlistEntity>>(emptyList())
    private val _news = MutableStateFlow<List<NewsItemDto>>(emptyList())
    private val _discoveries = MutableStateFlow<List<DiscoverStockDto>>(emptyList())
    private val _newsLoading = MutableStateFlow(false)
    private val _newsActionMessage = MutableStateFlow("")
    private var aiStatusJob: Job? = null

    val recommendations: StateFlow<List<RecommendationEntity>> = _recommendations.asStateFlow()
    val watchlist: StateFlow<List<WatchlistEntity>> = _watchlist.asStateFlow()
    val news: StateFlow<List<NewsItemDto>> = _news.asStateFlow()
    val discoveries: StateFlow<List<DiscoverStockDto>> = _discoveries.asStateFlow()
    val newsLoading: StateFlow<Boolean> = _newsLoading.asStateFlow()
    val newsActionMessage: StateFlow<String> = _newsActionMessage.asStateFlow()
    val wsConnectionState: StateFlow<WsConnectionState> = repo.observeWsConnectionState()

    init {
        viewModelScope.launch {
            val clientId = repo.ensureClientId()
            repo.observeRecommendations(clientId).collect { _recommendations.value = it }
        }
        viewModelScope.launch {
            val clientId = repo.ensureClientId()
            repo.observeWatchlist(clientId).collect { _watchlist.value = it }
        }
    }

    fun acceptDisclaimer() {
        viewModelScope.launch { repo.markDisclaimerAccepted() }
    }

    fun setLocale(locale: String) {
        viewModelScope.launch { repo.setLocale(locale) }
    }

    fun setNotificationsEnabled(enabled: Boolean) {
        viewModelScope.launch { repo.setNotificationsEnabled(enabled) }
    }

    fun setRiskProfile(profile: String) {
        viewModelScope.launch { repo.setRiskProfile(profile) }
    }

    fun setBackendBaseUrl(url: String) {
        viewModelScope.launch { repo.setBackendBaseUrl(url) }
    }

    fun setQuietHours(startHour: Int, endHour: Int) {
        viewModelScope.launch { repo.setQuietHours(startHour, endHour) }
    }

    fun setAutoStartEnabled(enabled: Boolean) {
        viewModelScope.launch { repo.setAutoStartEnabled(enabled) }
    }

    fun setFloatingWindowEnabled(enabled: Boolean) {
        viewModelScope.launch { repo.setFloatingWindowEnabled(enabled) }
    }

    fun setDiscoverModeEnabled(enabled: Boolean) {
        viewModelScope.launch { repo.setDiscoverModeEnabled(enabled) }
    }

    fun submitFeedback(recommendationId: Int, helpful: Boolean, reason: String?) {
        viewModelScope.launch { repo.submitFeedback(recommendationId, helpful, reason) }
    }

    fun syncRecommendations() {
        viewModelScope.launch { repo.syncRecommendations() }
    }

    fun addWatch(symbol: String, name: String) {
        viewModelScope.launch { repo.addWatch(symbol, name) }
    }

    fun removeWatch(symbol: String) {
        viewModelScope.launch { repo.removeWatch(symbol) }
    }

    fun startRealtime() {
        viewModelScope.launch { repo.startWs() }
    }

    fun stopRealtime() {
        repo.stopWs()
    }

    fun fetchLatestNews() {
        viewModelScope.launch {
            _newsLoading.value = true
            val recentItems = repo.fetchLatestNews(hours = 24)
            val items = if (recentItems.isEmpty()) {
                repo.fetchLatestNews(hours = 24 * 30)
            } else {
                recentItems
            }
            _news.value = items
            _newsLoading.value = false
            _newsActionMessage.value = if (items.isEmpty()) {
                "news_empty"
            } else {
                "news_loaded:${items.size}"
            }
        }
    }

    fun triggerAiStockRecommendation() {
        viewModelScope.launch {
            _newsLoading.value = true
            val trigger = repo.triggerAiRecommendation()
            _newsLoading.value = false
            if (!trigger.ok) {
                _newsActionMessage.value = "ai_trigger_failed"
                return@launch
            }
            val initialMessage = trigger.message.ifBlank {
                if (trigger.state == "already_running") {
                    "AI task is already running."
                } else {
                    "AI task started."
                }
            }
            _newsActionMessage.value = initialMessage
            startAiStatusPolling()
        }
    }

    fun discoverNewStocks() {
        viewModelScope.launch {
            _newsLoading.value = true
            val items = repo.fetchDiscoveredStocks(limit = 6, universeLimit = 100)
            _newsLoading.value = false
            _discoveries.value = items
            _newsActionMessage.value = if (items.isEmpty()) {
                "discover_empty"
            } else {
                "discover_loaded:${items.size}"
            }
        }
    }

    private fun startAiStatusPolling() {
        aiStatusJob?.cancel()
        aiStatusJob = viewModelScope.launch {
            repeat(120) {
                val status = repo.fetchAiRecommendationStatus()
                if (status != null) {
                    _newsActionMessage.value = buildAiStatusMessage(status)
                    when (status.state) {
                        "succeeded" -> {
                            repo.syncRecommendations()
                            return@launch
                        }
                        "failed" -> return@launch
                    }
                }
                delay(1_500)
            }
            _newsActionMessage.value = "AI status polling timed out. Please retry."
        }
    }

    private fun buildAiStatusMessage(status: RecommendationStatusDto): String {
        val detail = when (status.state) {
            "running" -> {
                val progressText = if (status.progress > 0) "${status.progress}%" else ""
                val suffix = if (progressText.isBlank()) "" else " ($progressText)"
                "${status.message}$suffix"
            }
            "succeeded" -> status.message.ifBlank { "AI selection completed." }
            "failed" -> status.error?.let { "AI selection failed: $it" } ?: "AI selection failed."
            else -> status.message.ifBlank { "AI selection is idle." }
        }
        return detail.ifBlank { "AI selection is running." }
    }

    fun clearNewsActionMessage() {
        _newsActionMessage.value = ""
    }
}
