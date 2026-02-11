package com.stockai.app.network

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject

@Serializable
data class WsEnvelope(
    val type: String,
    val payload: JsonObject = JsonObject(emptyMap()),
)

@Serializable
data class RecommendationPayload(
    val recommendation: RecommendationDto
)

@Serializable
data class RecommendationDto(
    val id: Int,
    @SerialName("client_id") val clientId: String,
    val symbol: String,
    @SerialName("created_at") val createdAt: String,
    val action: String,
    @SerialName("target_position_pct") val targetPositionPct: Double,
    @SerialName("summary_zh") val summaryZh: String,
    @SerialName("summary_en") val summaryEn: String,
    val confidence: Double,
    val risk: JsonElement,
    val evidence: JsonElement,
)

@Serializable
data class RecommendationListResponse(
    val items: List<RecommendationDto>
)

@Serializable
data class NewsItemDto(
    val source: String,
    val url: String,
    val title: String,
    val snippet: String,
    @SerialName("published_at") val publishedAt: String,
    val symbol: String,
    val name: String,
    @SerialName("sentiment_hint") val sentimentHint: String = "neutral",
)

@Serializable
data class NewsListResponse(
    val items: List<NewsItemDto>
)

@Serializable
data class TriggerRecommendationResponse(
    val ok: Boolean = false,
    @SerialName("client_id") val clientId: String = "",
    val state: String = "",
    val message: String = "",
)

@Serializable
data class DebugResultPayload(
    val summary: String,
    val result: JsonElement,
)

@Serializable
data class RecommendationStatusDto(
    @SerialName("client_id") val clientId: String = "",
    val state: String = "idle",
    val step: String = "idle",
    val progress: Int = 0,
    val message: String = "",
    @SerialName("total_watchlist") val totalWatchlist: Int = 0,
    @SerialName("total_candidates") val totalCandidates: Int = 0,
    @SerialName("processed_candidates") val processedCandidates: Int = 0,
    @SerialName("created_recommendations") val createdRecommendations: Int = 0,
    @SerialName("started_at") val startedAt: String? = null,
    @SerialName("updated_at") val updatedAt: String? = null,
    @SerialName("finished_at") val finishedAt: String? = null,
    val error: String? = null,
)

@Serializable
data class DiscoverStockDto(
    val symbol: String,
    val name: String,
    val action: String,
    val score: Double = 0.0,
    val confidence: Double = 0.0,
    @SerialName("summary_zh") val summaryZh: String,
    @SerialName("summary_en") val summaryEn: String,
    val reasons: List<String> = emptyList(),
    @SerialName("news_count") val newsCount: Int = 0,
    @SerialName("target_position_pct") val targetPositionPct: Double = 0.0,
)

@Serializable
data class DiscoverStockListResponse(
    val items: List<DiscoverStockDto>
)
