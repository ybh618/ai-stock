package com.stockai.app.data

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "recommendations")
data class RecommendationEntity(
    @PrimaryKey val id: Int,
    val clientId: String,
    val symbol: String,
    val createdAt: String,
    val action: String,
    val targetPositionPct: Double,
    val summaryZh: String,
    val summaryEn: String,
    val confidence: Double,
    val riskJson: String,
    val evidenceJson: String,
)
