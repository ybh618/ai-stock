package com.stockai.app.data

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import kotlinx.coroutines.flow.Flow

@Dao
interface AppDao {
    @Query("SELECT * FROM recommendations WHERE clientId = :clientId ORDER BY createdAt DESC LIMIT :limit")
    fun observeRecommendations(clientId: String, limit: Int = 1000): Flow<List<RecommendationEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertRecommendation(item: RecommendationEntity)

    @Query("DELETE FROM recommendations WHERE clientId = :clientId AND id NOT IN (SELECT id FROM recommendations WHERE clientId = :clientId ORDER BY createdAt DESC LIMIT :limit)")
    suspend fun trimRecommendations(clientId: String, limit: Int = 1000)

    @Query("SELECT * FROM watchlist_items WHERE clientId = :clientId ORDER BY groupName, sortIndex")
    fun observeWatchlist(clientId: String): Flow<List<WatchlistEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertWatchlistItem(item: WatchlistEntity)

    @Query("DELETE FROM watchlist_items WHERE clientId = :clientId AND symbol = :symbol")
    suspend fun deleteWatchlistItem(clientId: String, symbol: String)
}
