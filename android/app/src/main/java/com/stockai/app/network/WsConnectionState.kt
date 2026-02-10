package com.stockai.app.network

enum class WsConnectionStatus {
    DISCONNECTED,
    CONNECTING,
    CONNECTED,
    RECONNECTING,
    FAILED,
}

data class WsConnectionState(
    val status: WsConnectionStatus,
    val detail: String = "",
)
