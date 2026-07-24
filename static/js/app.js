// static/js/app.js
import {
	SDK,
	DISCONNECT_TIMEOUT_MS
} from './config.js';
import {
	debounce,
	getThemeColor,
	showDisconnectPopup,
	hideDisconnectPopup,
	setCookie,
	getCookie,
	showToast,
	formatNum,
	parseToFloatOrNull,
	sanitizeString
} from './utils.js';
import {
	initializeFlowBoard,
	updateFlowBoard,
	resizeFlowBoard,
	startAnimationLoop
} from './ui/flow-board.js';
import {
	initializeCharts,
	updatePowerChart,
	updateHistoryChart,
	updateHourlyChart,
	handleHistoryPeriodChange,
	exportChartDataToCSV,
	updateChartTheme
} from './ui/charts.js';
import {
	initWeather,
	updateWeatherTheme,
	handleMapResize,
	ensureWeatherStarted
} from './ui/weather.js';
import {
	initDashboardChrome,
	updateAlertsPanel,
	updateKpiStrip,
	markDataReceived,
	updateDataAgeDisplay,
	markBmsAvailable,
	applyPanelVisibility,
} from './ui/dashboard-chrome.js';
import { getThemeById, resolveThemeId } from './ui/themes.js';

// --- Socket.IO Connection ---
const socket = io({
	transports: ['websocket'],
	upgrade: false,
	rememberUpgrade: false,
	reconnection: true,
	reconnectionDelay: 1000,
	reconnectionDelayMax: 5000,
	maxReconnectionAttempts: Infinity,
	timeout: 20000,
	forceNew: true
});

// --- Application State ---
/** Holds the most recent, complete state received from the server. */
let clientState = {};
/** Flag to ensure initial setup runs only once. */
let initialDataReceived = false;
/** Flag to prevent rendering before charts are ready. */
let chartsInitialized = false;
/** Timer to detect stalled connections. */
let disconnectTimer = null;
/** Timer for connection health checks. */
let connectionHealthTimer = null;
/** Last time we received any data from server. */
let lastDataReceived = Date.now();
/** Chart.js instances. */
let powerChart, historicalEnergyChart, hourlyEnergyChart;
/** Flag indicating if BMS data is present and the tab should be shown. */
let bmsDataAvailable = false;
/** Caches the last BMS data payload to avoid redundant iframe updates. */
let lastBmsDataString = '';


/**
 * A promise that resolves when the main application components (DOM, charts) are initialized.
 * This is used to gate logic that depends on the app being fully ready.
 */
let resolveAppReady;
const appReadyPromise = new Promise(resolve => {
	resolveAppReady = resolve;
});

/**
 * Debounced function to update the power chart. This prevents overwhelming the chart
 * with rapid-fire updates from the 'update' socket event.
 */
const debouncedUpdatePowerChart = debounce((chart, state) => {
	if (initialDataReceived && chart) {
		updatePowerChart(chart, state);
	}
}, 500);

/**
 * Processes incoming data from the server, merging it into the clientState.
 * It attempts to parse string numbers and JSON strings into their correct types.
 * It also determines when the initial, required data has been received to trigger the first render.
 * @param {object} data - The data payload from the server.
 */
function processAndSanitizeData(data) {
	// Update last data received timestamp
	lastDataReceived = Date.now();

	// Track battery SOC updates for debugging
	if (data.hasOwnProperty(SDK.BATTERY_STATE_OF_CHARGE_PERCENT)) {
		console.log(`[SOC DEBUG] Battery SOC received: ${data[SDK.BATTERY_STATE_OF_CHARGE_PERCENT]}%`);
	}

	Object.assign(clientState, data);
	for (const key in clientState) {
		if (clientState.hasOwnProperty(key)) {
			const value = clientState[key];
			if (typeof value === 'string') {
				const trimmedValue = value.trim();
				if (trimmedValue !== '' && !isNaN(trimmedValue) && !isNaN(parseFloat(trimmedValue))) {
					const parsedValue = parseFloat(trimmedValue);
					clientState[key] = parsedValue;


					continue;
				}
				if ((trimmedValue.startsWith('{') && trimmedValue.endsWith('}')) || (trimmedValue.startsWith('[') && trimmedValue.endsWith(']'))) {
					try {
						clientState[key] = JSON.parse(trimmedValue.replace(/'/g, '"'));
					} catch (e) {
						/* Ignore */
}
				}
			}
		}
	}
	if (!initialDataReceived) {
		const requiredKeys = [SDK.OPERATIONAL_INVERTER_STATUS_TEXT, SDK.PV_TOTAL_DC_POWER_WATTS, SDK.LOAD_TOTAL_POWER_WATTS];
		const isReady = requiredKeys.every(key => {
			const val = clientState[key];
			return val !== undefined && val !== null && String(val).toLowerCase() !== 'init';
		});
		if (isReady) {
			initialDataReceived = true;
		}
	}

	// Handle update notification display
	updateNotificationDisplay();
}

/**
 * Updates the update notification display in the footer.
 * Shows update notification only when an update is available.
 */
function updateNotificationDisplay() {
	const updateStatusElement = document.getElementById('updateStatusMessage');
	if (!updateStatusElement) return;

	// Only show notification if update check is completed and update is available
	if (clientState.update_check_completed && clientState.update_available && clientState.latest_version) {
		updateStatusElement.innerHTML = ` | <span style="color: #ff6b35; font-weight: bold;">🔄 Update v${clientState.latest_version} Available!</span>`;
		updateStatusElement.style.display = 'inline';
	} else {
		updateStatusElement.innerHTML = '';
		updateStatusElement.style.display = 'none';
	}
}

/**
 * Updates the connection status indicator in the footer.
 */
function updateConnectionStatus(status) {
	const statusElement = document.getElementById('connectionStatus');
	if (!statusElement) return;

	statusElement.className = 'connection-status';
	statusElement.title = `Connection: ${status}`;

	switch (status) {
		case 'connected':
			statusElement.classList.add('connected');
			break;
		case 'connecting':
		case 'reconnecting':
			statusElement.classList.add('connecting');
			break;
		case 'disconnected':
		default:
			statusElement.classList.add('disconnected');
			break;
	}
}

/**
 * Monitors connection health and forces reconnection if no data received for too long.
 */
function startConnectionHealthMonitor() {
	if (connectionHealthTimer) clearInterval(connectionHealthTimer);

	connectionHealthTimer = setInterval(() => {
		const timeSinceLastData = Date.now() - lastDataReceived;
		const maxStaleTime = 5 * 60 * 1000; // 5 minutes
		const dashboardStaleTime = 2 * 60 * 1000; // 2 minutes

		// Check if dashboard appears stuck (receiving data but not updating)
		if (timeSinceLastData < dashboardStaleTime && socket.connected && initialDataReceived) {
			// Force a dashboard refresh if we're receiving data but UI might be stuck
			console.log(`[DASHBOARD HEALTH] Forcing dashboard refresh to prevent stale UI`);
			renderDashboard(clientState);
		}

		if (timeSinceLastData > maxStaleTime && socket.connected) {
			console.warn(`[CONNECTION HEALTH] No data received for ${Math.round(timeSinceLastData / 1000)}s, forcing reconnection`);
			showToast('Connection appears stale, reconnecting...', 'warning', 3000);
			updateConnectionStatus('reconnecting');
			socket.disconnect();
			setTimeout(() => {
				socket.connect();
			}, 1000);
		}
	}, 30000); // Check every 30 seconds
}

/**
 * Main rendering function for the dashboard.
 * It takes the raw clientState, transforms it into a structured `flowBoardData` object,
 * and then calls the `updateFlowBoard` function to update the UI.
 * It also updates the "Last Update" timestamp.
 * @param {object} state - The current clientState.
 */
function renderDashboard(state) {
	if (!initialDataReceived || !chartsInitialized || !state) return;

	// Add debug logging for SOC updates
	if (state.hasOwnProperty(SDK.BATTERY_STATE_OF_CHARGE_PERCENT)) {
		console.log(`[RENDER DEBUG] Rendering dashboard with SOC: ${state[SDK.BATTERY_STATE_OF_CHARGE_PERCENT]}%`);
	}

	try {
		const flowBoardData = {
			pv: [],
			pvTotal: {},
			grid: {},
			inverter: {},
			battery: {},
			load: {},
			production: {}
		};
		const mpptCount = state[SDK.STATIC_NUMBER_OF_MPPTS] ?? 0;
		for (let i = 1; i <= 4; i++) {
			flowBoardData.pv.push({
				name: `PV ${i}`,
				w: i <= mpptCount ? (state[SDK[`PV_MPPT${i}_POWER_WATTS`]] ?? 0) : 0,
				v: i <= mpptCount ? (state[SDK[`PV_MPPT${i}_VOLTAGE_VOLTS`]] ?? 0) : 0,
				a: i <= mpptCount ? (state[SDK[`PV_MPPT${i}_CURRENT_AMPS`]] ?? 0) : 0,
				is_configured: i <= mpptCount
			});
		}
		flowBoardData.pvTotal = {
			w: state[SDK.PV_TOTAL_DC_POWER_WATTS] ?? 0,
			kwh: state[SDK.ENERGY_PV_DAILY_KWH],
			percent: (state[SDK.CONFIG_PV_INSTALLED_CAPACITY_WATT_PEAK] > 0) ? ((state[SDK.PV_TOTAL_DC_POWER_WATTS] ?? 0) / state[SDK.CONFIG_PV_INSTALLED_CAPACITY_WATT_PEAK]) * 100 : 0
		};
		flowBoardData.grid = {
			w: -(state[SDK.GRID_TOTAL_ACTIVE_POWER_WATTS] ?? 0),
			kwhUp: state[SDK.ENERGY_GRID_DAILY_EXPORT_KWH],
			kwhDown: state[SDK.ENERGY_GRID_DAILY_IMPORT_KWH],
			noGrid: (state[SDK.OPERATIONAL_INVERTER_STATUS_TEXT] || "").toLowerCase().includes('grid off')
		};
		flowBoardData.inverter = {
			brand: state[SDK.STATIC_INVERTER_MANUFACTURER],
			firmware: state[SDK.STATIC_INVERTER_FIRMWARE_VERSION],
			temp: state[SDK.OPERATIONAL_INVERTER_TEMPERATURE_CELSIUS],
			volts: state[SDK.GRID_L1_VOLTAGE_VOLTS],
			amps: state[SDK.GRID_L1_CURRENT_AMPS],
			hz: state[SDK.GRID_FREQUENCY_HZ],
			tuyaStatus: state.display_tuya_status,
			statusText: state[SDK.OPERATIONAL_INVERTER_STATUS_TEXT],
			categorizedAlerts: state[SDK.OPERATIONAL_CATEGORIZED_ALERTS_DICT],
			pluginConnectionStatus: state[SDK.CORE_PLUGIN_CONNECTION_STATUS]
		};
		const batterySoc = state[SDK.BATTERY_STATE_OF_CHARGE_PERCENT] ?? 0;

		// Resolve BMS plugin connection status dynamically (any configured BMS instance).
		let bmsPluginConnectionStatus = null;
		const statusSuffix = '_core_plugin_connection_status';
		for (const key of Object.keys(state)) {
			if (typeof key === 'string' && key.endsWith(statusSuffix)) {
				const instanceId = key.slice(0, -statusSuffix.length);
				const lower = instanceId.toLowerCase();
				if (lower.includes('bms') || lower.includes('seplos') || lower.includes('jk') || lower.includes('battery')) {
					bmsPluginConnectionStatus = state[key];
					break;
				}
			}
		}
		if (bmsPluginConnectionStatus == null && SDK.BMS_PLUGIN_CONNECTION_STATUS_KEY_PATTERN) {
			bmsPluginConnectionStatus = state[SDK.BMS_PLUGIN_CONNECTION_STATUS_KEY_PATTERN.replace('{instance_id}', 'BMS_Seplos_v2')];
		}

		flowBoardData.battery = {
			power: state[SDK.BATTERY_POWER_WATTS] ?? 0,
			soc: batterySoc,
			firmware: state[SDK.STATIC_BATTERY_FIRMWARE_VERSION],
			kwhUp: state[SDK.ENERGY_BATTERY_DAILY_CHARGE_KWH],
			kwhDown: state[SDK.ENERGY_BATTERY_DAILY_DISCHARGE_KWH],
			volts: state[SDK.BATTERY_VOLTAGE_VOLTS],
			amps: state[SDK.BATTERY_CURRENT_AMPS],
			statusText: state[SDK.BATTERY_STATUS_TEXT],
			runtimeTextDisplay: state.display_battery_time_remaining,
			bmsPluginConnectionStatus
		};

		// Debug log the battery data being passed to flow board
		console.log(`[RENDER DEBUG] Battery data for flow board:`, {
			power: flowBoardData.battery.power,
			soc: flowBoardData.battery.soc,
			volts: flowBoardData.battery.volts
		});
		const pvDaily = state[SDK.ENERGY_PV_DAILY_KWH] ?? 0,
			battCharge = state[SDK.ENERGY_BATTERY_DAILY_CHARGE_KWH] ?? 0,
			battDischarge = state[SDK.ENERGY_BATTERY_DAILY_DISCHARGE_KWH] ?? 0,
			gridImport = state[SDK.ENERGY_GRID_DAILY_IMPORT_KWH] ?? 0,
			gridExport = state[SDK.ENERGY_GRID_DAILY_EXPORT_KWH] ?? 0,
			loadTotal = state[SDK.ENERGY_LOAD_DAILY_KWH] ?? 0;
		const loadFromSolar = Math.max(0, pvDaily - battCharge - gridExport);
		// Daily sources can exceed load kWh (charge earlier, discharge later). Normalize % to source sum.
		const loadSourceSum = loadFromSolar + battDischarge + gridImport;
		const pBLoad = loadSourceSum > 0.01 ? loadSourceSum : (loadTotal > 0.01 ? loadTotal : 0);
		flowBoardData.load = {
			currentW: state[SDK.LOAD_TOTAL_POWER_WATTS] ?? 0,
			totalEnergyConsumedToday: loadTotal,
			energy_from_solar_kWh: loadFromSolar,
			percent_from_solar: pBLoad > 0.01 ? (loadFromSolar / pBLoad) * 100 : 0,
			energy_from_battery_kWh: battDischarge,
			percent_from_battery: pBLoad > 0.01 ? (battDischarge / pBLoad) * 100 : 0,
			energy_from_grid_kWh: gridImport,
			percent_from_grid: pBLoad > 0.01 ? (gridImport / pBLoad) * 100 : 0
		};
		const pBProd = pvDaily > 0.01 ? pvDaily : (loadFromSolar + battCharge + gridExport);
		flowBoardData.production = {
			to_load_direct_kWh: loadFromSolar,
			percent_to_load_direct: pBProd > 0.01 ? (loadFromSolar / pBProd) * 100 : 0,
			to_battery_kWh: battCharge,
			percent_to_battery: pBProd > 0.01 ? (battCharge / pBProd) * 100 : 0,
			to_grid_export_kWh: gridExport,
			percent_to_grid_export: pBProd > 0.01 ? (gridExport / pBProd) * 100 : 0
		};
		updateFlowBoard(flowBoardData);
		updateBmsPacksStrip(state);
		updatePluginHealthPanel(state);
		updateAlertsPanel(state);
		updateKpiStrip(state);
		markDataReceived();
		const lastUpdateEl = document.getElementById('lastUpdate');
		if (lastUpdateEl && state.display_timestamp) {
			lastUpdateEl.textContent = `Last Update: ${state.display_timestamp}`;
			lastUpdateEl.dataset.baseStamp = state.display_timestamp;
			lastUpdateEl.title = `Server time: ${state.display_timestamp}`;
		}
		updateDataAgeDisplay();
	} catch (e) {
		console.error("Error during dashboard rendering:", e);
	}
}

function updateBmsPacksStrip(state) {
	const section = document.getElementById('bms-packs-section');
	const strip = document.getElementById('bms-packs-strip');
	if (!section || !strip) return;
	let packs = state[SDK.BMS_PACKS_LIST];
	if (typeof packs === 'string') {
		try { packs = JSON.parse(packs); } catch (e) { packs = null; }
	}
	// Single pack is already shown on the battery tile — only list multi-pack setups
	if (!Array.isArray(packs) || packs.length < 2) {
		section.style.display = 'none';
		return;
	}
	section.style.display = '';
	strip.innerHTML = packs.map(p => {
		const id = (p && p.instance_id) ? p.instance_id : '?';
		const soc = (p && p.soc != null && !isNaN(Number(p.soc))) ? Number(p.soc).toFixed(0) : '--';
		const power = (p && p.power != null && !isNaN(Number(p.power))) ? Number(p.power).toFixed(0) : '--';
		const status = (p && p.status) ? p.status : '';
		return `<div class="bms-pack-chip"><strong>${id}</strong><span>${soc}%</span><span>${power} W</span><span>${status}</span></div>`;
	}).join('');
}

function updatePluginHealthPanel(state) {
	const body = document.getElementById('plugin-health-body');
	const toggle = document.getElementById('pluginHealthToggle');
	const dot = document.getElementById('pluginHealthToggleDot');
	if (!body) return;

	const rows = [];
	let worst = 'ok';
	for (const key of Object.keys(state)) {
		if (!key.endsWith('_health_connection_status')) continue;
		const instance = key.slice(0, -'_health_connection_status'.length);
		const status = String(state[key] || 'unknown');
		const age = state[`${instance}_health_last_success_age_s`];
		const fails = state[`${instance}_health_consecutive_failures`];
		const meta = state[`${instance}_health_plugin_meta_status`] || '';
		let cls = 'health-ok';
		const sl = status.toLowerCase();
		if (sl.includes('error') || sl.includes('disconnect') || sl.includes('fail')) {
			cls = 'health-bad';
			worst = 'bad';
		} else if ((sl.includes('connect') && !sl.includes('connected')) || sl.includes('stall') || (Number(fails) > 0)) {
			cls = 'health-warn';
			if (worst === 'ok') worst = 'warn';
		}
		const ageTxt = (age != null && age !== '' && !isNaN(Number(age))) ? `${Number(age).toFixed(0)}s` : '--';
		rows.push(`<div class="plugin-health-row ${cls}"><span>${instance}</span><span>${status}</span><span>${ageTxt}</span><span>${fails ?? 0}</span><span>${meta}</span></div>`);
	}

	if (toggle) {
		toggle.disabled = !rows.length;
		toggle.classList.toggle('has-data', rows.length > 0);
	}
	if (dot) {
		dot.classList.remove('good-dot', 'warning-dot', 'bad-dot');
		if (!rows.length) {
			/* leave neutral */
		} else if (worst === 'bad') {
			dot.classList.add('bad-dot');
		} else if (worst === 'warn') {
			dot.classList.add('warning-dot');
		} else {
			dot.classList.add('good-dot');
		}
	}

	if (!rows.length) {
		body.innerHTML = `<div class="plugin-health-empty">No plugin health data yet</div>`;
		return;
	}
	body.innerHTML =
		`<div class="plugin-health-row plugin-health-header"><span>Instance</span><span>Status</span><span>Age</span><span>Fail</span><span>Meta</span></div>` +
		rows.join('');
}

function setPluginHealthPopoverOpen(open) {
	const popover = document.getElementById('plugin-health-popover');
	const toggle = document.getElementById('pluginHealthToggle');
	if (!popover || !toggle) return;
	if (open) {
		popover.hidden = false;
		toggle.setAttribute('aria-expanded', 'true');
		toggle.classList.add('is-open');
	} else {
		popover.hidden = true;
		toggle.setAttribute('aria-expanded', 'false');
		toggle.classList.remove('is-open');
	}
}

function initPluginHealthToggle() {
	const toggle = document.getElementById('pluginHealthToggle');
	const closeBtn = document.getElementById('pluginHealthClose');
	const popover = document.getElementById('plugin-health-popover');
	if (!toggle || !popover) return;

	toggle.addEventListener('click', (e) => {
		e.stopPropagation();
		if (toggle.disabled) return;
		const willOpen = popover.hidden;
		setPluginHealthPopoverOpen(willOpen);
	});
	closeBtn?.addEventListener('click', (e) => {
		e.stopPropagation();
		setPluginHealthPopoverOpen(false);
	});
	document.addEventListener('click', (e) => {
		if (popover.hidden) return;
		if (popover.contains(e.target) || toggle.contains(e.target)) return;
		setPluginHealthPopoverOpen(false);
	});
	document.addEventListener('keydown', (e) => {
		if (e.key === 'Escape') setPluginHealthPopoverOpen(false);
	});
}

/**
 * Updates the MQTT status indicator button with the correct color and tooltip.
 * @param {string} status - The connection status string (e.g., "Connected", "Disconnected").
 */
function updateMqttStatusButton(status) {
	const mqttButton = document.getElementById('mqttStatus');
	if (!mqttButton) return;

	const statusText = String(status ?? 'Unknown');
	const statusLower = statusText.toLowerCase();

	if (statusLower === 'disabled') {
		mqttButton.style.display = 'none';
		return;
	}

	mqttButton.style.display = 'inline-flex';

	const dot = document.getElementById('mqtt-dot');
	const textEl = document.getElementById('mqtt-status-text');
	mqttButton.dataset.tooltip = `MQTT: ${statusText}`;
	mqttButton.title = `MQTT: ${statusText}`;
	if (textEl) textEl.textContent = statusText;

	mqttButton.classList.remove('good', 'warning', 'bad', 'mqtt-ok', 'mqtt-warn', 'mqtt-bad');
	if (dot) dot.classList.remove('good-dot', 'warning-dot', 'bad-dot');

	if (statusLower === 'connected') {
		mqttButton.classList.add('good', 'mqtt-ok');
		if (dot) dot.classList.add('good-dot');
	} else if (
		statusLower.includes('connecting') ||
		statusLower.includes('reconnect')
	) {
		mqttButton.classList.add('warning', 'mqtt-warn');
		if (dot) dot.classList.add('warning-dot');
	} else {
		mqttButton.classList.add('bad', 'mqtt-bad');
		if (dot) dot.classList.add('bad-dot');
	}

	applyPanelVisibility();
}

/**
 * Packages BMS-related data from the main clientState and sends it to the BMS iframe.
 * It uses a stringified cache (`lastBmsDataString`) to prevent sending redundant updates
 * if the data hasn't changed.
 * @param {object} state - The current clientState.
 */
function updateBmsIframe(state) {
	if (!bmsDataAvailable) return;
	const bmsIframe = document.getElementById('bms-iframe');
	if (!bmsIframe || !bmsIframe.contentWindow || !bmsIframe.contentWindow.bmsViewer) return;
	const cells = [];
	if (state[SDK.BMS_CELL_COUNT]) {
		for (let i = 1; i <= state[SDK.BMS_CELL_COUNT]; i++) {
			cells.push({
				id: i,
				voltage: parseToFloatOrNull(state[`bms_cell_voltage_${i}`]),
				balancing: state[`bms_cell_balance_active_${i}`] === 'True'
			});
		}
	}
	const summary = {
		batteryFlow: {
			status: state[SDK.BATTERY_STATUS_TEXT] || 'Idle',
			power: state[SDK.BATTERY_POWER_WATTS] || 0
		},
		packVoltage: state[SDK.BATTERY_VOLTAGE_VOLTS],
		portVoltage: state[SDK.BATTERY_VOLTAGE_VOLTS],
		remainingAh: state[SDK.BMS_REMAINING_CAPACITY_AH],
		soc: state[SDK.BATTERY_STATE_OF_CHARGE_PERCENT],
		soh: state[SDK.BATTERY_STATE_OF_HEALTH_PERCENT],
		cycles: state[SDK.BATTERY_CYCLES_COUNT],
		packs: state[SDK.BMS_PACKS_LIST] || [],
		packCount: state[SDK.BMS_PACK_COUNT] || 0,
		bmsTemperatures: state[SDK.BMS_CELL_TEMPERATURES_LIST] || [],
		totalCapacity: state[SDK.BMS_FULL_CAPACITY_AH],
		deltaCellVoltage: parseToFloatOrNull(state[SDK.BMS_CELL_VOLTAGE_DELTA_VOLTS]),
		averageCellVoltage: parseToFloatOrNull(state[SDK.BMS_CELL_VOLTAGE_AVERAGE_VOLTS]),
		highestCell: {
			ids: [state[SDK.BMS_CELL_WITH_MAX_VOLTAGE_NUMBER]],
			voltage: parseToFloatOrNull(state[SDK.BMS_CELL_VOLTAGE_MAX_VOLTS])
		},
		lowestCell: {
			ids: [state[SDK.BMS_CELL_WITH_MIN_VOLTAGE_NUMBER]],
			voltage: parseToFloatOrNull(state[SDK.BMS_CELL_VOLTAGE_MIN_VOLTS])
		},
		minPackVoltageConfig: 44.8,
		maxPackVoltageConfig: 58.4
	};
	const bmsPayload = {
		cells,
		summary
	};
	const bmsPayloadString = JSON.stringify(bmsPayload);
	if (bmsPayloadString !== lastBmsDataString) {
		bmsIframe.contentWindow.bmsViewer.updateData(bmsPayload);
		lastBmsDataString = bmsPayloadString;
	}
}

/**
 * The main render loop, driven by `requestAnimationFrame`.
 * It continuously calls the necessary rendering functions based on the current application state.
 */
function masterRenderLoop() {
	if (initialDataReceived) {
		renderDashboard(clientState);
		if (bmsDataAvailable) {
			updateBmsIframe(clientState);
		}
		if (clientState.hasOwnProperty('display_mqtt_connection_status')) {
			updateMqttStatusButton(clientState.display_mqtt_connection_status);
		}
	}
	requestAnimationFrame(masterRenderLoop);
}

// --- Socket Event Handlers ---
socket.on('connect', () => {
	console.log('Socket connected successfully');
	hideDisconnectPopup();
	updateConnectionStatus('connected');
	if (disconnectTimer) clearTimeout(disconnectTimer);
	clientState = {};
	initialDataReceived = false;
	lastDataReceived = Date.now();
	startConnectionHealthMonitor();
	showToast('Connected to server', 'success', 2000);
});

socket.on('disconnect', (reason) => {
	console.error('Socket disconnected:', reason);
	updateConnectionStatus('disconnected');
	showDisconnectPopup(`Disconnected: ${reason}. Reconnecting...`);
	if (disconnectTimer) clearTimeout(disconnectTimer);
	initialDataReceived = false;
});

socket.on('connect_error', (error) => {
	console.error('Socket connection error:', error);
	updateConnectionStatus('connecting');
	showDisconnectPopup(`Connection error: ${error.message}. Retrying...`);
});

socket.on('reconnect', (attemptNumber) => {
	console.log(`Socket reconnected after ${attemptNumber} attempts`);
	updateConnectionStatus('connected');
	showToast(`Reconnected after ${attemptNumber} attempts`, 'success', 3000);
	hideDisconnectPopup();
	// Request fresh data after reconnection
	socket.emit('request_full_update');
});

socket.on('reconnect_attempt', (attemptNumber) => {
	console.log(`Reconnection attempt ${attemptNumber}`);
	updateConnectionStatus('reconnecting');
	showDisconnectPopup(`Reconnecting... (attempt ${attemptNumber})`);
});

socket.on('reconnect_error', (error) => {
	console.error('Reconnection error:', error);
});

socket.on('reconnect_failed', () => {
	console.error('Failed to reconnect after maximum attempts');
	showDisconnectPopup('Failed to reconnect. Please refresh the page.');
});

/** Handles the initial, large data payload from the server upon connection. */
socket.on('full_update', async (data) => {
	if (disconnectTimer) clearTimeout(disconnectTimer);
	disconnectTimer = setTimeout(() => showDisconnectPopup("Connection stalled."), DISCONNECT_TIMEOUT_MS);

	// Log battery SOC data for debugging
	if (data.hasOwnProperty(SDK.BATTERY_STATE_OF_CHARGE_PERCENT)) {
		console.log(`[FULL_UPDATE] Battery SOC: ${data[SDK.BATTERY_STATE_OF_CHARGE_PERCENT]}%`);
	}

	processAndSanitizeData(data);

	await appReadyPromise;

	if (clientState[SDK.BMS_CELL_COUNT] > 0) {
		if (!bmsDataAvailable) {
			bmsDataAvailable = true;
			markBmsAvailable(true);
			const bmsTabButton = document.getElementById('bmsViewTab');
			if (bmsTabButton) {
				bmsTabButton.click(); // Switch to the BMS tab
			}
		}
	} else {
		markBmsAvailable(false);
		const historyTabButton = document.querySelector('#tabbed-card-section .tab-link[data-tab="history-tab"]');
		if (historyTabButton) historyTabButton.click();
	}

	socket.emit('request_history', {
		days: 7 // Request 7 days for panning
	});

	const histSel = document.getElementById('historyPeriodSelect');
	if (histSel) {
		handleHistoryPeriodChange(histSel.value, socket);
	}
	const hourlyDateSelect = document.getElementById('hourlyDateSelect');
	if (hourlyDateSelect) {
		socket.emit('request_hourly_summary', { date: hourlyDateSelect.value });
	}
});

/** Handles smaller, periodic data updates from the server. */
socket.on('update', (data) => {
	if (disconnectTimer) clearTimeout(disconnectTimer);
	disconnectTimer = setTimeout(() => showDisconnectPopup("Connection stalled."), DISCONNECT_TIMEOUT_MS);

	// Log battery SOC updates for debugging
	if (data.hasOwnProperty(SDK.BATTERY_STATE_OF_CHARGE_PERCENT)) {
		console.log(`[UPDATE] Battery SOC: ${data[SDK.BATTERY_STATE_OF_CHARGE_PERCENT]}%`);
	}

	processAndSanitizeData(data);

	// Force immediate dashboard update for critical data changes
	if (initialDataReceived && chartsInitialized) {
		renderDashboard(clientState);
	} else {
		markDataReceived();
	}

	debouncedUpdatePowerChart(powerChart, clientState);
});

/** Handles historical power data for the main power chart. */
socket.on('history_data', (payload) => {
	if (powerChart && payload && payload.power) {
		updatePowerChart(powerChart, clientState, payload.power, true);
		showToast(`Power history loaded.`, 'success');
	}
});

/** Handles historical energy summary data for the history bar chart. */
socket.on('daily_summary_data', (response) => {
	if (historicalEnergyChart) {
		updateHistoryChart(historicalEnergyChart, response);
	}
});

/** Handles hourly energy summary data for the hourly bar chart. */
socket.on('hourly_summary_data', (response) => {
	if (hourlyEnergyChart) {
		updateHourlyChart(hourlyEnergyChart, response);
	}
});

/** Main application entry point, triggered when the DOM is fully loaded. */
window.onload = () => {
	initDashboardChrome();

	document.addEventListener('visibilitychange', () => {
		if (!document.hidden && socket.connected) {
			showToast('Refreshing data...', 'info', 2000);
			socket.emit('request_full_update');
		}
	});

	const densityToggle = document.getElementById('densityToggle');

	/**
	 * Applies theme side-effects (BMS palette, charts, weather map).
	 * @param {string|object} modeOrTheme - 'light'|'dark'|theme id|theme detail object
	 */
	function applyTheme(modeOrTheme) {
		let theme = null;
		if (modeOrTheme && typeof modeOrTheme === 'object' && modeOrTheme.id) {
			theme = modeOrTheme;
		} else if (typeof modeOrTheme === 'string' && modeOrTheme !== 'light' && modeOrTheme !== 'dark') {
			theme = getThemeById(resolveThemeId(modeOrTheme));
		} else {
			const id = resolveThemeId(document.body.dataset.theme || getCookie('theme') || 'midnight');
			theme = getThemeById(id);
		}
		const mode = theme?.mode || (document.body.classList.contains('dark') ? 'dark' : 'light');
		const bmsIframe = document.getElementById('bms-iframe');
		if (bmsIframe?.contentWindow?.bmsViewer) {
			const palette = theme?.bms ? { ...theme.bms, mode: theme.mode } : null;
			bmsIframe.contentWindow.bmsViewer.setTheme(theme?.id || mode, palette);
		}
		setTimeout(resizeFlowBoard, 50);
		if (chartsInitialized) {
			updateChartTheme(powerChart);
			updateChartTheme(historicalEnergyChart);
			updateChartTheme(hourlyEnergyChart);
		}
		updateWeatherTheme(mode);
	}

	function applyDensity(density) {
		const body = document.body;
		body.classList.remove('density-comfortable', 'density-compact');
		body.classList.add(density === 'compact' ? 'density-compact' : 'density-comfortable');
		if (densityToggle) {
			densityToggle.textContent = density === 'compact' ? 'Comfortable' : 'Compact';
		}
		setTimeout(resizeFlowBoard, 50);
	}

	const savedDensity = getCookie("ui_density") || 'comfortable';
	applyDensity(savedDensity);
	initPluginHealthToggle();

	// Theme changes from Settings (instant preview + save)
	document.addEventListener('solar-dash-theme-applied', (e) => {
		applyTheme(e.detail || document.body.dataset.theme);
	});
	// Initial sync after chrome applied theme
	applyTheme(document.body.dataset.theme || 'midnight');

	densityToggle?.addEventListener('click', () => {
		const next = document.body.classList.contains('density-compact') ? 'comfortable' : 'compact';
		applyDensity(next);
		setCookie("ui_density", next, 365);
	});

	const bmsIframe = document.getElementById('bms-iframe');
	if (bmsIframe) {
		bmsIframe.addEventListener('load', () => {
			applyTheme(document.body.dataset.theme || 'midnight');
			if (bmsDataAvailable) updateBmsIframe(clientState);
		});
	}

	function setupTabGroup(containerSelector) {
		const container = document.querySelector(containerSelector);
		if (!container) return;

		const tabLinks = container.querySelectorAll('.tab-link');
		const tabContents = container.querySelectorAll('.tab-content');
		const controlGroups = container.querySelectorAll('.section-header-controls');

		const switchTab = (tabId) => {
			tabLinks.forEach(l => l.classList.remove('active'));
			tabContents.forEach(c => c.classList.remove('active'));

			const activeLink = container.querySelector(`.tab-link[data-tab="${tabId}"]`);
			const activeContent = container.querySelector(`#${tabId}`);

			if (activeLink) activeLink.classList.add('active');
			if (activeContent) activeContent.classList.add('active');

			controlGroups.forEach(cg => { cg.style.display = 'none' });
			if (tabId === 'history-tab') {
				const historyControls = document.getElementById('historyControls');
				if (historyControls) historyControls.style.display = 'flex';
			} else if (tabId === 'power-metrics-tab') {
				const powerControls = document.getElementById('powerMetricsControls');
				if (powerControls) powerControls.style.display = 'flex';
			} else if (tabId === 'hourly-tab') {
				const hourlyControls = document.getElementById('hourlyControls');
				if (hourlyControls) hourlyControls.style.display = 'flex';
			}

			setTimeout(() => {
				if (window.Chart?.instances) {
					for (const id in window.Chart.instances) {
						if (Object.hasOwnProperty.call(window.Chart.instances, id)) {
							window.Chart.instances[id].resize();
						}
					}
				}
				if (tabId === 'weather-tab') {
					ensureWeatherStarted();
					handleMapResize();
				}
			}, 50);
		};

		tabLinks.forEach(link => {
			link.addEventListener('click', (e) => {
				const tabId = e.currentTarget.getAttribute('data-tab');
				switchTab(tabId);
			});
		});

		const firstActive = container.querySelector('.tab-link.active');
		if (firstActive) {
			switchTab(firstActive.getAttribute('data-tab'));
		}
	}

	setupTabGroup('#top-tab-section');
	setupTabGroup('#tabbed-card-section');

	// Initialize all UI components
	const charts = initializeCharts();
	powerChart = charts.powerChart;
	historicalEnergyChart = charts.historicalEnergyChart;
	hourlyEnergyChart = charts.hourlyEnergyChart;
	if (powerChart && historicalEnergyChart && hourlyEnergyChart) {
		chartsInitialized = true;
		applyTheme(document.body.dataset.theme || 'midnight');
	}

	initializeFlowBoard(debounce);
	startAnimationLoop(() => clientState);
	document.addEventListener('solar-dash-flow-resize', () => resizeFlowBoard());
	masterRenderLoop();
	initWeather();

	// --- Bind Event Listeners for UI Controls ---
	const histSel = document.getElementById('historyPeriodSelect');
	histSel?.addEventListener('change', () => handleHistoryPeriodChange(histSel.value, socket));

	document.getElementById('refreshPowerChartBtn')?.addEventListener('click', () => socket.emit('request_history', { days: 7 }));

	document.getElementById('refreshHistoryChartBtn')?.addEventListener('click', () => {
		if (histSel) handleHistoryPeriodChange(histSel.value, socket);
	});
	document.getElementById('exportPowerChartBtn')?.addEventListener('click', () => exportChartDataToCSV(powerChart, 'power_metrics'));
	document.getElementById('exportHistoryChartBtn')?.addEventListener('click', () => {
		if (histSel) {
			const sT = histSel.options[histSel.selectedIndex].text.toLowerCase().replace(/\s+/g, '_');
			exportChartDataToCSV(historicalEnergyChart, `history_${sT}`);
		}
	});

	const hourlyDateSelect = document.getElementById('hourlyDateSelect');
	if (hourlyDateSelect) {
		const today = new Date();
		const yyyy = today.getFullYear();
		const mm = String(today.getMonth() + 1).padStart(2, '0');
		const dd = String(today.getDate()).padStart(2, '0');
		hourlyDateSelect.value = `${yyyy}-${mm}-${dd}`;
		hourlyDateSelect.addEventListener('change', () => {
			socket.emit('request_hourly_summary', { date: hourlyDateSelect.value });
		});
	}

	document.getElementById('refreshHourlyChartBtn')?.addEventListener('click', () => {
		if (hourlyDateSelect) socket.emit('request_hourly_summary', { date: hourlyDateSelect.value });
	});
	document.getElementById('exportHourlyChartBtn')?.addEventListener('click', () => exportChartDataToCSV(hourlyEnergyChart, `hourly_summary_${hourlyDateSelect.value}`));

	// Flow board refresh button functionality
	const flowBoardRefreshBtn = document.getElementById('flowBoardRefreshBtn');
	if (flowBoardRefreshBtn) {
		flowBoardRefreshBtn.addEventListener('click', () => {
			console.log('[MANUAL] Flow board refresh requested by user');
			flowBoardRefreshBtn.classList.add('spinning');

			// Force immediate dashboard re-render with current data
			if (initialDataReceived && chartsInitialized) {
				console.log('[MANUAL] Forcing immediate dashboard refresh with current data');
				renderDashboard(clientState);
			}

			// Also request fresh data from server
			socket.emit('request_full_update');
			showToast('Refreshing flow board data...', 'info', 2000);

			// Remove spinning animation after 2 seconds
			setTimeout(() => {
				flowBoardRefreshBtn.classList.remove('spinning');
			}, 2000);
		});
	}

	// Manual reconnect button functionality
	const manualReconnectBtn = document.getElementById('manualReconnectBtn');
	if (manualReconnectBtn) {
		manualReconnectBtn.addEventListener('click', () => {
			console.log('[MANUAL] Manual reconnection requested by user');
			manualReconnectBtn.classList.add('spinning');
			showToast('Forcing reconnection...', 'info', 3000);

			// Force disconnect and reconnect
			if (socket.connected) {
				socket.disconnect();
			}
			setTimeout(() => {
				socket.connect();
				manualReconnectBtn.classList.remove('spinning');
			}, 1000);
		});
	}



	resolveAppReady();
};