package com.stockai.app.network

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import java.net.URLEncoder
import java.nio.charset.StandardCharsets

class ApiClient {
    private val json = Json { ignoreUnknownKeys = true }
    private val client = OkHttpClient()
    private val jsonMediaType = "application/json; charset=utf-8".toMediaType()

    suspend fun fetchRecommendations(baseUrl: String, clientId: String, limit: Int = 200): List<RecommendationDto> {
        return withContext(Dispatchers.IO) {
            val encodedClientId = URLEncoder.encode(clientId, StandardCharsets.UTF_8)
            val url = "${baseUrl.trimEnd('/')}/v1/recommendations?client_id=$encodedClientId&limit=$limit"
            val request = Request.Builder().url(url).get().build()
            runCatching {
                client.newCall(request).execute().use { response ->
                    if (!response.isSuccessful) return@use emptyList()
                    val body = response.body?.string().orEmpty()
                    if (body.isBlank()) return@use emptyList()
                    val parsed = json.decodeFromString<RecommendationListResponse>(body)
                    parsed.items
                }
            }.getOrDefault(emptyList())
        }
    }

    suspend fun submitFeedback(
        baseUrl: String,
        clientId: String,
        recommendationId: Int,
        helpful: Boolean,
        reason: String?,
    ): Boolean {
        return withContext(Dispatchers.IO) {
            val payload = json.encodeToString(
                FeedbackRequest(
                    clientId = clientId,
                    recommendationId = recommendationId,
                    helpful = helpful,
                    reason = reason,
                )
            )
            val request = Request.Builder()
                .url("${baseUrl.trimEnd('/')}/v1/feedback")
                .post(payload.toRequestBody(jsonMediaType))
                .build()
            runCatching {
                client.newCall(request).execute().use { it.isSuccessful }
            }.getOrDefault(false)
        }
    }

    suspend fun fetchLatestNews(
        baseUrl: String,
        clientId: String,
        hours: Int = 24,
        limit: Int = 50,
        watchlist: List<SyncWatchItem> = emptyList(),
    ): List<NewsItemDto> {
        return withContext(Dispatchers.IO) {
            val url = buildNewsUrl(baseUrl, clientId, hours, limit, watchlist)
                ?: return@withContext emptyList()
            val request = Request.Builder().url(url).get().build()
            runCatching {
                client.newCall(request).execute().use { response ->
                    if (!response.isSuccessful) return@use emptyList()
                    val body = response.body?.string().orEmpty()
                    if (body.isBlank()) return@use emptyList()
                    val parsed = json.decodeFromString<NewsListResponse>(body)
                    parsed.items
                }
            }.getOrDefault(emptyList())
        }
    }

    suspend fun triggerAiRecommendation(
        baseUrl: String,
        clientId: String,
    ): TriggerRecommendationResponse {
        return withContext(Dispatchers.IO) {
            val payload = json.encodeToString(TriggerRecommendationRequest(clientId = clientId))
            val request = Request.Builder()
                .url("${baseUrl.trimEnd('/')}/v1/recommendations/trigger")
                .post(payload.toRequestBody(jsonMediaType))
                .build()
            runCatching {
                client.newCall(request).execute().use { response ->
                    if (!response.isSuccessful) return@use TriggerRecommendationResponse(ok = false)
                    val body = response.body?.string().orEmpty()
                    if (body.isBlank()) return@use TriggerRecommendationResponse(ok = false)
                    json.decodeFromString<TriggerRecommendationResponse>(body)
                }
            }.getOrDefault(TriggerRecommendationResponse(ok = false))
        }
    }

    suspend fun fetchAiRecommendationStatus(
        baseUrl: String,
        clientId: String,
    ): RecommendationStatusDto? {
        return withContext(Dispatchers.IO) {
            val encodedClientId = URLEncoder.encode(clientId, StandardCharsets.UTF_8)
            val url = "${baseUrl.trimEnd('/')}/v1/recommendations/status?client_id=$encodedClientId"
            val request = Request.Builder().url(url).get().build()
            runCatching {
                client.newCall(request).execute().use { response ->
                    if (!response.isSuccessful) return@use null
                    val body = response.body?.string().orEmpty()
                    if (body.isBlank()) return@use null
                    json.decodeFromString<RecommendationStatusDto>(body)
                }
            }.getOrNull()
        }
    }

    private fun buildNewsUrl(
        baseUrl: String,
        clientId: String,
        hours: Int,
        limit: Int,
        watchlist: List<SyncWatchItem>,
    ): String? {
        val base = "${baseUrl.trimEnd('/')}/v1/news".toHttpUrlOrNull() ?: return null
        return base.newBuilder()
            .addQueryParameter("client_id", clientId)
            .addQueryParameter("hours", hours.toString())
            .addQueryParameter("limit", limit.toString())
            .apply {
                watchlist.forEach { item ->
                    addQueryParameter("symbols", item.symbol)
                    addQueryParameter("names", item.name)
                }
            }
            .build()
            .toString()
    }

    @kotlinx.serialization.Serializable
    private data class FeedbackRequest(
        @kotlinx.serialization.SerialName("client_id")
        val clientId: String,
        @kotlinx.serialization.SerialName("recommendation_id")
        val recommendationId: Int,
        val helpful: Boolean,
        val reason: String?,
    )

    @kotlinx.serialization.Serializable
    private data class TriggerRecommendationRequest(
        @kotlinx.serialization.SerialName("client_id")
        val clientId: String,
    )
}
