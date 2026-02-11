package com.stockai.app.network

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.decodeFromJsonElement
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonArray
import kotlinx.serialization.json.putJsonObject
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger

data class SyncWatchItem(
    val symbol: String,
    val name: String,
    val group: String = "default",
    val sortIndex: Int = 0,
)

data class SyncPreferences(
    val locale: String,
    val riskProfile: String,
    val notificationsEnabled: Boolean,
    val quietStartHour: Int,
    val quietEndHour: Int,
)

class WsClient(
    private val onRecommendation: suspend (RecommendationDto) -> Unit,
    private val onDebugResult: suspend (String) -> Unit = {},
    private val onConnectionStateChanged: (WsConnectionState) -> Unit = {},
) {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val json = Json { ignoreUnknownKeys = true }
    private val client = OkHttpClient.Builder()
        .pingInterval(20, TimeUnit.SECONDS)
        .build()

    @Volatile
    private var ws: WebSocket? = null
    @Volatile
    private var connectionInfo: ConnectionInfo? = null
    private val shouldRun = AtomicBoolean(false)
    private val reconnectAttempts = AtomicInteger(0)
    private val connectionSerial = AtomicInteger(0)
    private var reconnectJob: Job? = null
    private var heartbeatJob: Job? = null

    fun start(
        baseUrl: String,
        clientId: String,
        prefs: SyncPreferences,
        watchlist: List<SyncWatchItem>,
        appVersion: String = "0.1.0",
    ) {
        connectionInfo = ConnectionInfo(baseUrl, clientId, prefs, watchlist, appVersion)
        shouldRun.set(true)
        reconnectAttempts.set(0)
        reconnectJob?.cancel()
        reconnectJob = null
        connectNow(detail = "starting")
    }

    fun updateSyncState(prefs: SyncPreferences, watchlist: List<SyncWatchItem>) {
        val old = connectionInfo ?: return
        val updated = old.copy(prefs = prefs, watchlist = watchlist)
        connectionInfo = updated
        ws?.send(buildSyncStateMessage(updated))
    }

    fun stop() {
        shouldRun.set(false)
        reconnectAttempts.set(0)
        connectionSerial.incrementAndGet()
        reconnectJob?.cancel()
        reconnectJob = null
        stopHeartbeat()
        ws?.close(1000, "stopped")
        ws = null
        onConnectionStateChanged(WsConnectionState(WsConnectionStatus.DISCONNECTED, "stopped"))
    }

    private fun connectNow(detail: String = "connect") {
        if (!shouldRun.get()) return
        val info = connectionInfo ?: return
        val serial = connectionSerial.incrementAndGet()
        stopHeartbeat()
        ws?.cancel()
        onConnectionStateChanged(WsConnectionState(WsConnectionStatus.CONNECTING, detail))
        val wsUrl = info.baseUrl.trimEnd('/').replace("http://", "ws://").replace("https://", "wss://") + "/ws"
        val request = Request.Builder().url(wsUrl).build()
        ws = client.newWebSocket(
            request,
            object : WebSocketListener() {
                override fun onOpen(webSocket: WebSocket, response: Response) {
                    if (serial != connectionSerial.get() || !shouldRun.get()) {
                        webSocket.close(1000, "stale_socket")
                        return
                    }
                    val current = connectionInfo ?: return
                    reconnectAttempts.set(0)
                    reconnectJob?.cancel()
                    reconnectJob = null
                    webSocket.send(buildHelloMessage(current))
                    webSocket.send(buildSyncStateMessage(current))
                    startHeartbeat(webSocket, serial)
                    onConnectionStateChanged(WsConnectionState(WsConnectionStatus.CONNECTED, "open"))
                }

                override fun onMessage(webSocket: WebSocket, text: String) {
                    scope.launch {
                        runCatching {
                            val envelope = json.decodeFromString<WsEnvelope>(text)
                            if (envelope.type == "server.recommendation.created") {
                                val payload = json.decodeFromJsonElement<RecommendationPayload>(envelope.payload)
                                onRecommendation(payload.recommendation)
                            } else if (envelope.type == "server.debug.result") {
                                val payload = json.decodeFromJsonElement<DebugResultPayload>(envelope.payload)
                                onDebugResult(payload.summary)
                            } else if (envelope.type == "pong") {
                                return@runCatching
                            }
                        }
                    }
                }

                override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                    handleSocketDropped(serial, "closed:$code")
                }

                override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                    val code = response?.code ?: -1
                    handleSocketDropped(serial, "failure:$code:${t.message.orEmpty()}", failed = true)
                }
            }
        )
    }

    private fun handleSocketDropped(serial: Int, detail: String, failed: Boolean = false) {
        if (serial != connectionSerial.get()) return
        stopHeartbeat()
        ws = null
        if (!shouldRun.get()) return
        onConnectionStateChanged(
            WsConnectionState(
                if (failed) WsConnectionStatus.FAILED else WsConnectionStatus.RECONNECTING,
                detail,
            )
        )
        scheduleReconnect()
    }

    private fun scheduleReconnect() {
        if (!shouldRun.get()) return
        if (reconnectJob?.isActive == true) return
        reconnectJob = scope.launch {
            val attempt = reconnectAttempts.incrementAndGet()
            onConnectionStateChanged(
                WsConnectionState(WsConnectionStatus.RECONNECTING, "attempt:$attempt")
            )
            delay(minOf(30_000L, attempt * 1_500L))
            if (!isActive || !shouldRun.get()) {
                reconnectJob = null
                return@launch
            }
            reconnectJob = null
            connectNow(detail = "attempt:$attempt")
        }
    }

    private fun startHeartbeat(webSocket: WebSocket, serial: Int) {
        stopHeartbeat()
        heartbeatJob = scope.launch {
            while (isActive && shouldRun.get() && serial == connectionSerial.get()) {
                delay(25_000L)
                if (!isActive || !shouldRun.get() || serial != connectionSerial.get()) return@launch
                val sent = runCatching { webSocket.send(buildPingMessage()) }.getOrDefault(false)
                if (!sent) {
                    webSocket.cancel()
                    return@launch
                }
            }
        }
    }

    private fun stopHeartbeat() {
        heartbeatJob?.cancel()
        heartbeatJob = null
    }

    private fun buildHelloMessage(info: ConnectionInfo): String {
        return json.encodeToString(
            WsEnvelope(
                type = "client.hello",
                payload = buildJsonObject {
                    put("client_id", info.clientId)
                    put("app_version", info.appVersion)
                    put("locale", info.prefs.locale)
                }
            )
        )
    }

    private fun buildSyncStateMessage(info: ConnectionInfo): String {
        return json.encodeToString(
            WsEnvelope(
                type = "client.sync_state",
                payload = buildJsonObject {
                    put("client_id", info.clientId)
                    putJsonArray("watchlist") {
                        info.watchlist.forEach { item ->
                            add(
                                buildJsonObject {
                                    put("symbol", item.symbol)
                                    put("name", item.name)
                                    put("group", item.group)
                                    put("sort_index", item.sortIndex)
                                }
                            )
                        }
                    }
                    putJsonObject("preferences") {
                        put("locale", info.prefs.locale)
                        put("notifications_enabled", info.prefs.notificationsEnabled)
                        putJsonObject("quiet_hours") {
                            put("start_hour", info.prefs.quietStartHour)
                            put("end_hour", info.prefs.quietEndHour)
                        }
                        put("risk_profile", info.prefs.riskProfile)
                    }
                }
            )
        )
    }

    private fun buildPingMessage(): String {
        return json.encodeToString(
            WsEnvelope(type = "ping")
        )
    }

    private data class ConnectionInfo(
        val baseUrl: String,
        val clientId: String,
        val prefs: SyncPreferences,
        val watchlist: List<SyncWatchItem>,
        val appVersion: String,
    )
}
