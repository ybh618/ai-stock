package com.stockai.app.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.stockai.app.data.AppRepository
import com.stockai.app.data.PreferenceState
import com.stockai.app.data.RecommendationEntity
import com.stockai.app.data.WatchlistEntity
import com.stockai.app.network.WsConnectionState
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
            ),
        )

    private val _recommendations = MutableStateFlow<List<RecommendationEntity>>(emptyList())
    private val _watchlist = MutableStateFlow<List<WatchlistEntity>>(emptyList())

    val recommendations: StateFlow<List<RecommendationEntity>> = _recommendations.asStateFlow()
    val watchlist: StateFlow<List<WatchlistEntity>> = _watchlist.asStateFlow()
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
}
