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
)

@Serializable
data class DebugResultPayload(
    val summary: String,
    val result: JsonElement,
)
