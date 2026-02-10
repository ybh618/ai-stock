package com.stockai.app.data

import android.content.Context
import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStoreFile
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import java.util.UUID

class AppPreferences(private val context: Context) {
    private val dataStore = PreferenceDataStoreFactory.create(
        produceFile = { context.preferencesDataStoreFile("stock_ai_prefs") }
    )

    val state: Flow<PreferenceState> = dataStore.data.map { prefs ->
        PreferenceState(
            clientId = prefs[CLIENT_ID] ?: "",
            locale = prefs[LOCALE] ?: "system",
            disclaimerAccepted = prefs[DISCLAIMER_ACCEPTED] ?: false,
            notificationsEnabled = prefs[NOTIFICATIONS_ENABLED] ?: true,
            riskProfile = prefs[RISK_PROFILE] ?: "neutral",
            backendBaseUrl = prefs[BACKEND_BASE_URL] ?: "http://10.0.2.2:3005",
            quietStartHour = prefs[QUIET_START_HOUR] ?: 22,
            quietEndHour = prefs[QUIET_END_HOUR] ?: 8,
        )
    }

    suspend fun ensureClientId(): String {
        val value = dataStore.data.map { it[CLIENT_ID] ?: "" }.first()
        if (value.isNotBlank()) return value
        val generated = UUID.randomUUID().toString()
        dataStore.edit { it[CLIENT_ID] = generated }
        return generated
    }

    suspend fun setDisclaimerAccepted(value: Boolean) {
        dataStore.edit { it[DISCLAIMER_ACCEPTED] = value }
    }

    suspend fun setLocale(locale: String) {
        dataStore.edit { it[LOCALE] = locale }
    }

    suspend fun setNotificationsEnabled(enabled: Boolean) {
        dataStore.edit { it[NOTIFICATIONS_ENABLED] = enabled }
    }

    suspend fun setRiskProfile(profile: String) {
        dataStore.edit { it[RISK_PROFILE] = profile }
    }

    suspend fun setQuietHours(startHour: Int, endHour: Int) {
        val start = startHour.coerceIn(0, 23)
        val end = endHour.coerceIn(0, 23)
        dataStore.edit {
            it[QUIET_START_HOUR] = start
            it[QUIET_END_HOUR] = end
        }
    }

    suspend fun setBackendBaseUrl(url: String) {
        dataStore.edit { it[BACKEND_BASE_URL] = url }
    }

    companion object {
        val CLIENT_ID = stringPreferencesKey("client_id")
        private val LOCALE = stringPreferencesKey("locale")
        private val DISCLAIMER_ACCEPTED = booleanPreferencesKey("disclaimer_accepted")
        private val NOTIFICATIONS_ENABLED = booleanPreferencesKey("notifications_enabled")
        private val RISK_PROFILE = stringPreferencesKey("risk_profile")
        private val BACKEND_BASE_URL = stringPreferencesKey("backend_base_url")
        private val QUIET_START_HOUR = intPreferencesKey("quiet_start_hour")
        private val QUIET_END_HOUR = intPreferencesKey("quiet_end_hour")
    }
}

data class PreferenceState(
    val clientId: String,
    val locale: String,
    val disclaimerAccepted: Boolean,
    val notificationsEnabled: Boolean,
    val riskProfile: String,
    val backendBaseUrl: String,
    val quietStartHour: Int,
    val quietEndHour: Int,
)
