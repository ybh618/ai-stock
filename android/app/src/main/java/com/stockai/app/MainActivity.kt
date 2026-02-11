package com.stockai.app

import android.Manifest
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.appcompat.app.AppCompatDelegate
import androidx.compose.foundation.clickable
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CenterAlignedTopAppBar
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.core.os.LocaleListCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.stockai.app.network.NewsItemDto
import com.stockai.app.network.DiscoverStockDto
import com.stockai.app.data.RecommendationEntity
import com.stockai.app.data.WatchlistEntity
import com.stockai.app.network.WsConnectionState
import com.stockai.app.network.WsConnectionStatus
import com.stockai.app.service.ServiceLauncher
import com.stockai.app.ui.MainViewModel

class MainActivity : ComponentActivity() {
    private val vm by viewModels<MainViewModel>()

    private val notificationPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
        ServiceLauncher.startWsForegroundService(this)
        vm.syncRecommendations()
        val startRecommendationId = intent?.getIntExtra("recommendation_id", -1)?.takeIf { it > 0 }
        setContent {
            MaterialTheme {
                val prefs by vm.prefs.collectAsStateWithLifecycle()
                LaunchedEffect(prefs.locale) {
                    applyAppLocale(prefs.locale)
                }
                LaunchedEffect(prefs.floatingWindowEnabled) {
                    ServiceLauncher.syncFloatingWidgetService(this@MainActivity, prefs.floatingWindowEnabled)
                }
                if (!prefs.disclaimerAccepted) {
                    DisclaimerScreen(onAccept = vm::acceptDisclaimer)
                } else {
                    MainApp(
                        vm = vm,
                        startRecommendationId = startRecommendationId,
                        onToggleFloatingWindow = ::onToggleFloatingWindow,
                        onRequestOverlayPermission = ::requestOverlayPermission,
                        onRequestIgnoreBatteryOptimizations = ::requestIgnoreBatteryOptimizations,
                    )
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
    }

    override fun onDestroy() {
        super.onDestroy()
    }

    private fun applyAppLocale(locale: String) {
        val tags = when (locale) {
            "zh" -> "zh"
            "en" -> "en"
            else -> ""
        }
        AppCompatDelegate.setApplicationLocales(LocaleListCompat.forLanguageTags(tags))
    }

    private fun onToggleFloatingWindow(enabled: Boolean) {
        vm.setFloatingWindowEnabled(enabled)
        if (enabled) {
            if (ServiceLauncher.canDrawOverlays(this)) {
                ServiceLauncher.startFloatingWidgetService(this)
            } else {
                requestOverlayPermission()
            }
        } else {
            ServiceLauncher.stopFloatingWidgetService(this)
        }
    }

    private fun requestOverlayPermission() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M || ServiceLauncher.canDrawOverlays(this)) return
        val intent = Intent(
            Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
            Uri.parse("package:$packageName")
        )
        startActivity(intent)
    }

    private fun requestIgnoreBatteryOptimizations() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M) return
        val pm = getSystemService(PowerManager::class.java)
        if (pm != null && pm.isIgnoringBatteryOptimizations(packageName)) return
        val directIntent = Intent(
            Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,
            Uri.parse("package:$packageName")
        )
        runCatching { startActivity(directIntent) }.onFailure {
            startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))
        }
    }
}

@Composable
private fun DisclaimerScreen(onAccept: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.Center
    ) {
        Text(text = stringResource(R.string.disclaimer_title), style = MaterialTheme.typography.headlineMedium)
        Text(
            text = stringResource(R.string.disclaimer_content),
            modifier = Modifier.padding(top = 12.dp, bottom = 24.dp)
        )
        Button(onClick = onAccept) {
            Text(text = stringResource(R.string.accept))
        }
    }
}

@Composable
@OptIn(ExperimentalMaterial3Api::class)
private fun MainApp(
    vm: MainViewModel,
    startRecommendationId: Int?,
    onToggleFloatingWindow: (Boolean) -> Unit,
    onRequestOverlayPermission: () -> Unit,
    onRequestIgnoreBatteryOptimizations: () -> Unit,
) {
    var tab by rememberSaveable { mutableStateOf(if (startRecommendationId != null) "recommendations" else "watchlist") }
    val watchlist by vm.watchlist.collectAsStateWithLifecycle()
    val recommendations by vm.recommendations.collectAsStateWithLifecycle()
    val news by vm.news.collectAsStateWithLifecycle()
    val discoveries by vm.discoveries.collectAsStateWithLifecycle()
    val newsLoading by vm.newsLoading.collectAsStateWithLifecycle()
    val newsActionMessage by vm.newsActionMessage.collectAsStateWithLifecycle()
    val prefs by vm.prefs.collectAsStateWithLifecycle()
    val wsConnectionState by vm.wsConnectionState.collectAsStateWithLifecycle()
    var selectedRecommendationId by rememberSaveable { mutableStateOf(startRecommendationId) }

    val selectedRecommendation = recommendations.firstOrNull { it.id == selectedRecommendationId }

    if (selectedRecommendation != null) {
        RecommendationDetailDialog(
            item = selectedRecommendation,
            locale = prefs.locale,
            onDismiss = { selectedRecommendationId = null },
            onUseful = { vm.submitFeedback(selectedRecommendation.id, true, null) },
            onNotUseful = { vm.submitFeedback(selectedRecommendation.id, false, "manual_feedback") },
        )
    }

    Scaffold(
        topBar = {
            CenterAlignedTopAppBar(
                title = {
                    Text(
                        when (tab) {
                            "watchlist" -> stringResource(R.string.watchlist)
                            "recommendations" -> stringResource(R.string.recommendations)
                            "news" -> stringResource(R.string.news)
                            else -> stringResource(R.string.settings)
                        }
                    )
                }
            )
        },
        bottomBar = {
            NavigationBar {
                NavigationBarItem(
                    selected = tab == "watchlist",
                    onClick = { tab = "watchlist" },
                    label = { Text(stringResource(R.string.watchlist)) },
                    icon = {}
                )
                NavigationBarItem(
                    selected = tab == "recommendations",
                    onClick = { tab = "recommendations" },
                    label = { Text(stringResource(R.string.recommendations)) },
                    icon = {}
                )
                NavigationBarItem(
                    selected = tab == "settings",
                    onClick = { tab = "settings" },
                    label = { Text(stringResource(R.string.settings)) },
                    icon = {}
                )
                NavigationBarItem(
                    selected = tab == "news",
                    onClick = { tab = "news" },
                    label = { Text(stringResource(R.string.news)) },
                    icon = {}
                )
            }
        }
    ) { padding ->
        when (tab) {
            "watchlist" -> WatchlistScreen(
                padding = padding,
                items = watchlist,
                onAdd = vm::addWatch,
                onRemove = vm::removeWatch
            )
            "recommendations" -> RecommendationsScreen(
                padding = padding,
                items = recommendations,
                locale = prefs.locale,
                onClick = { selectedRecommendationId = it.id }
            )
            "news" -> NewsScreen(
                padding = padding,
                items = news,
                discoveries = discoveries,
                discoverModeEnabled = prefs.discoverModeEnabled,
                loading = newsLoading,
                actionMessage = newsActionMessage,
                onFetchNews = {
                    vm.clearNewsActionMessage()
                    vm.fetchLatestNews()
                },
                onTriggerAi = {
                    vm.clearNewsActionMessage()
                    vm.triggerAiStockRecommendation()
                },
                onDiscover = {
                    vm.clearNewsActionMessage()
                    vm.discoverNewStocks()
                },
            )
            else -> SettingsScreen(
                padding = padding,
                locale = prefs.locale,
                notificationsEnabled = prefs.notificationsEnabled,
                riskProfile = prefs.riskProfile,
                backendBaseUrl = prefs.backendBaseUrl,
                wsConnectionState = wsConnectionState,
                quietStartHour = prefs.quietStartHour,
                quietEndHour = prefs.quietEndHour,
                autoStartEnabled = prefs.autoStartEnabled,
                floatingWindowEnabled = prefs.floatingWindowEnabled,
                discoverModeEnabled = prefs.discoverModeEnabled,
                onLocale = vm::setLocale,
                onNotifications = vm::setNotificationsEnabled,
                onRiskProfile = vm::setRiskProfile,
                onBackendUrlSave = vm::setBackendBaseUrl,
                onQuietHours = vm::setQuietHours,
                onAutoStartEnabled = vm::setAutoStartEnabled,
                onFloatingWindowEnabled = { onToggleFloatingWindow(it) },
                onDiscoverModeEnabled = vm::setDiscoverModeEnabled,
                onRequestOverlayPermission = onRequestOverlayPermission,
                onRequestIgnoreBatteryOptimizations = onRequestIgnoreBatteryOptimizations,
            )
        }
    }
}

@Composable
private fun WatchlistScreen(
    padding: PaddingValues,
    items: List<WatchlistEntity>,
    onAdd: (String, String) -> Unit,
    onRemove: (String) -> Unit,
) {
    var symbol by rememberSaveable { mutableStateOf("") }
    var name by rememberSaveable { mutableStateOf("") }
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(padding)
            .padding(16.dp)
    ) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
            OutlinedTextField(
                value = symbol,
                onValueChange = { symbol = it },
                label = { Text(stringResource(R.string.symbol)) },
                modifier = Modifier.weight(1f)
            )
            OutlinedTextField(
                value = name,
                onValueChange = { name = it },
                label = { Text(stringResource(R.string.name)) },
                modifier = Modifier.weight(1f)
            )
        }
        Button(
            onClick = {
                if (symbol.isNotBlank() && name.isNotBlank()) {
                    onAdd(symbol.trim(), name.trim())
                    symbol = ""
                    name = ""
                }
            },
            modifier = Modifier.padding(top = 12.dp)
        ) {
            Text(stringResource(R.string.add))
        }
        LazyColumn(modifier = Modifier.padding(top = 16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(items) { item ->
                Card(modifier = Modifier.fillMaxWidth()) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(12.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text("${item.symbol} ${item.name}")
                        TextButton(onClick = { onRemove(item.symbol) }) {
                            Text(stringResource(R.string.delete))
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun RecommendationsScreen(
    padding: PaddingValues,
    items: List<RecommendationEntity>,
    locale: String,
    onClick: (RecommendationEntity) -> Unit,
) {
    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(padding)
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        items(items) { item ->
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { onClick(item) }
            ) {
                Column(modifier = Modifier.padding(12.dp)) {
                    Text("[${item.action.uppercase()}] ${item.symbol}", style = MaterialTheme.typography.titleMedium)
                    Text(if (locale == "en") item.summaryEn else item.summaryZh, modifier = Modifier.padding(top = 6.dp))
                    Text(
                        "${stringResource(R.string.target_position)}=${item.targetPositionPct}%, ${stringResource(R.string.confidence)}=${item.confidence}",
                        modifier = Modifier.padding(top = 6.dp)
                    )
                }
            }
        }
    }
}

@Composable
private fun NewsScreen(
    padding: PaddingValues,
    items: List<NewsItemDto>,
    discoveries: List<DiscoverStockDto>,
    discoverModeEnabled: Boolean,
    loading: Boolean,
    actionMessage: String,
    onFetchNews: () -> Unit,
    onTriggerAi: () -> Unit,
    onDiscover: () -> Unit,
) {
    val context = LocalContext.current
    val messageText = newsActionMessageText(actionMessage)

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(padding)
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        item {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(
                    onClick = onFetchNews,
                    enabled = !loading,
                    modifier = Modifier.weight(1f)
                ) {
                    Text(stringResource(R.string.fetch_latest_news))
                }
                Button(
                    onClick = onTriggerAi,
                    enabled = !loading,
                    modifier = Modifier.weight(1f)
                ) {
                    Text(stringResource(R.string.ai_stock_recommendation))
                }
            }
        }
        if (discoverModeEnabled) {
            item {
                Button(
                    onClick = onDiscover,
                    enabled = !loading,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text(stringResource(R.string.discover_new_stocks))
                }
            }
        }
        if (loading) {
            item {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 8.dp),
                    horizontalArrangement = Arrangement.Center
                ) {
                    CircularProgressIndicator()
                }
            }
        }
        if (messageText != null) {
            item {
                Text(
                    text = messageText,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
        if (!loading && items.isEmpty()) {
            item {
                Text(
                    text = stringResource(R.string.news_empty),
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
        if (discoveries.isNotEmpty()) {
            item {
                Text(
                    text = stringResource(R.string.discover_results_title),
                    style = MaterialTheme.typography.titleMedium,
                )
            }
        }
        items(discoveries) { item ->
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text(
                        text = "[${item.action.uppercase()}] ${item.symbol} ${item.name}",
                        style = MaterialTheme.typography.titleMedium
                    )
                    Text(
                        text = item.summaryZh,
                        style = MaterialTheme.typography.bodyMedium
                    )
                    Text(
                        text = "score=${item.score}, confidence=${item.confidence}, news=${item.newsCount}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        }
        items(items) { item ->
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable {
                        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(item.url))
                        runCatching { context.startActivity(intent) }
                    }
            ) {
                Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text(
                        text = "[${item.symbol}] ${item.title}",
                        style = MaterialTheme.typography.titleMedium
                    )
                    Text(
                        text = item.snippet,
                        style = MaterialTheme.typography.bodyMedium
                    )
                    Text(
                        text = "${item.source} • ${item.publishedAt}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        }
    }
}

@Composable
private fun newsActionMessageText(raw: String): String? {
    if (raw.isBlank()) return null
    return when {
        raw == "ai_trigger_ok" -> stringResource(R.string.ai_trigger_ok)
        raw == "ai_trigger_failed" -> stringResource(R.string.ai_trigger_failed)
        raw == "discover_trigger_failed" -> stringResource(R.string.discover_trigger_failed)
        raw == "news_empty" -> stringResource(R.string.news_empty)
        raw == "discover_empty" -> stringResource(R.string.discover_empty)
        raw.startsWith("discover_loaded:") -> {
            val count = raw.substringAfter("discover_loaded:", "0")
            stringResource(R.string.discover_loaded_count, count)
        }
        raw.startsWith("news_loaded:") -> {
            val count = raw.substringAfter("news_loaded:", "0")
            stringResource(R.string.news_loaded_count, count)
        }
        else -> raw
    }
}

@Composable
private fun RecommendationDetailDialog(
    item: RecommendationEntity,
    locale: String,
    onDismiss: () -> Unit,
    onUseful: () -> Unit,
    onNotUseful: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("[${item.action.uppercase()}] ${item.symbol}") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(if (locale == "en") item.summaryEn else item.summaryZh)
                Text("${stringResource(R.string.target_position)}: ${item.targetPositionPct}%")
                Text("${stringResource(R.string.confidence)}: ${item.confidence}")
                Text("${stringResource(R.string.risk_label)}: ${item.riskJson}")
                Text("${stringResource(R.string.evidence_label)}: ${item.evidenceJson}")
            }
        },
        confirmButton = {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TextButton(onClick = onUseful) { Text(stringResource(R.string.feedback_useful)) }
                TextButton(onClick = onNotUseful) { Text(stringResource(R.string.feedback_not_useful)) }
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text(stringResource(R.string.close)) }
        }
    )
}

@Composable
private fun SettingsScreen(
    padding: PaddingValues,
    locale: String,
    notificationsEnabled: Boolean,
    riskProfile: String,
    backendBaseUrl: String,
    wsConnectionState: WsConnectionState,
    quietStartHour: Int,
    quietEndHour: Int,
    autoStartEnabled: Boolean,
    floatingWindowEnabled: Boolean,
    discoverModeEnabled: Boolean,
    onLocale: (String) -> Unit,
    onNotifications: (Boolean) -> Unit,
    onRiskProfile: (String) -> Unit,
    onBackendUrlSave: (String) -> Unit,
    onQuietHours: (Int, Int) -> Unit,
    onAutoStartEnabled: (Boolean) -> Unit,
    onFloatingWindowEnabled: (Boolean) -> Unit,
    onDiscoverModeEnabled: (Boolean) -> Unit,
    onRequestOverlayPermission: () -> Unit,
    onRequestIgnoreBatteryOptimizations: () -> Unit,
) {
    val context = LocalContext.current
    val canDrawOverlay = ServiceLauncher.canDrawOverlays(context)
    val powerManager = context.getSystemService(PowerManager::class.java)
    val batteryOptimizationIgnored = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
        powerManager?.isIgnoringBatteryOptimizations(context.packageName) == true
    } else {
        true
    }
    var backendUrlInput by rememberSaveable(backendBaseUrl) { mutableStateOf(backendBaseUrl) }
    val localeLabel = when (locale) {
        "zh" -> stringResource(R.string.locale_value_zh)
        "en" -> stringResource(R.string.locale_value_en)
        else -> stringResource(R.string.locale_value_system)
    }
    val riskLabel = when (riskProfile) {
        "aggressive" -> stringResource(R.string.risk_value_aggressive)
        "conservative" -> stringResource(R.string.risk_value_conservative)
        else -> stringResource(R.string.risk_value_neutral)
    }
    val connectionStatusLabel = when (wsConnectionState.status) {
        WsConnectionStatus.CONNECTED -> stringResource(R.string.connection_status_connected)
        WsConnectionStatus.CONNECTING -> stringResource(R.string.connection_status_connecting)
        WsConnectionStatus.RECONNECTING -> stringResource(R.string.connection_status_reconnecting)
        WsConnectionStatus.FAILED -> stringResource(R.string.connection_status_failed)
        WsConnectionStatus.DISCONNECTED -> stringResource(R.string.connection_status_disconnected)
    }
    val connectionColor = when (wsConnectionState.status) {
        WsConnectionStatus.CONNECTED -> androidx.compose.ui.graphics.Color(0xFF2E7D32)
        WsConnectionStatus.CONNECTING -> androidx.compose.ui.graphics.Color(0xFFF9A825)
        WsConnectionStatus.RECONNECTING -> androidx.compose.ui.graphics.Color(0xFFF57C00)
        WsConnectionStatus.FAILED -> androidx.compose.ui.graphics.Color(0xFFC62828)
        WsConnectionStatus.DISCONNECTED -> androidx.compose.ui.graphics.Color(0xFF757575)
    }
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(padding)
            .padding(16.dp)
            .verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(10.dp)
                    .background(connectionColor, CircleShape)
            )
            Text("${stringResource(R.string.connection_status)}: $connectionStatusLabel")
        }
        if (wsConnectionState.detail.isNotBlank()) {
            Text(
                text = wsConnectionState.detail,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }

        Text("${stringResource(R.string.locale)}: $localeLabel")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = { onLocale("zh") }) { Text(stringResource(R.string.locale_value_zh)) }
            Button(onClick = { onLocale("en") }) { Text(stringResource(R.string.locale_value_en)) }
            Button(onClick = { onLocale("system") }) { Text(stringResource(R.string.locale_value_system)) }
        }

        Row(horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
            Text(stringResource(R.string.notifications))
            Switch(checked = notificationsEnabled, onCheckedChange = onNotifications)
        }

        Row(horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
            Text(stringResource(R.string.auto_start))
            Switch(checked = autoStartEnabled, onCheckedChange = onAutoStartEnabled)
        }

        Row(horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
            Text(stringResource(R.string.floating_window))
            Switch(checked = floatingWindowEnabled, onCheckedChange = onFloatingWindowEnabled)
        }
        Row(horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
            Text(stringResource(R.string.discover_mode))
            Switch(checked = discoverModeEnabled, onCheckedChange = onDiscoverModeEnabled)
        }
        Text(
            text = if (canDrawOverlay) {
                stringResource(R.string.floating_window_permission_granted)
            } else {
                stringResource(R.string.floating_window_permission_required)
            },
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        if (!canDrawOverlay) {
            Button(onClick = onRequestOverlayPermission) {
                Text(stringResource(R.string.floating_window_grant_button))
            }
        }

        Text(
            text = if (batteryOptimizationIgnored) {
                stringResource(R.string.battery_optimization_ignored)
            } else {
                stringResource(R.string.battery_optimization_active)
            },
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Button(onClick = onRequestIgnoreBatteryOptimizations) {
            Text(stringResource(R.string.battery_optimization_disable_button))
        }

        Text("${stringResource(R.string.risk)}: $riskLabel")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = { onRiskProfile("aggressive") }) { Text(stringResource(R.string.risk_value_aggressive)) }
            Button(onClick = { onRiskProfile("neutral") }) { Text(stringResource(R.string.risk_value_neutral)) }
            Button(onClick = { onRiskProfile("conservative") }) { Text(stringResource(R.string.risk_value_conservative)) }
        }

        Text("${stringResource(R.string.quiet_hours)}: ${quietStartHour}:00 - ${quietEndHour}:00")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = { onQuietHours(22, 8) }) { Text(stringResource(R.string.quiet_preset_default)) }
            Button(onClick = { onQuietHours(0, 0) }) { Text(stringResource(R.string.quiet_preset_off)) }
            Button(onClick = { onQuietHours(12, 13) }) { Text(stringResource(R.string.quiet_preset_lunch)) }
        }

        OutlinedTextField(
            value = backendUrlInput,
            onValueChange = { backendUrlInput = it },
            label = { Text(stringResource(R.string.backend_url)) },
            modifier = Modifier.fillMaxWidth()
        )
        Button(onClick = { onBackendUrlSave(backendUrlInput) }) {
            Text(stringResource(R.string.save))
        }
    }
}
