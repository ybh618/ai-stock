package com.stockai.app.data

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "watchlist_items",
    indices = [Index(value = ["clientId", "symbol"], unique = true)]
)
data class WatchlistEntity(
    @PrimaryKey(autoGenerate = true) val id: Int = 0,
    val clientId: String,
    val symbol: String,
    val name: String,
    val groupName: String,
    val sortIndex: Int,
)
