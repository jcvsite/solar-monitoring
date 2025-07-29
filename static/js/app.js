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
    handleMapResize
} from './ui/weather.js';

// --- Socket.IO Connection ---
const socket = io({
	transports: ['websocket'],
	upgrade: false,
	rememberUpgrade: false
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
/** Chart.js instances. */
let powerChart, historicalEnergyChart, hourlyEnergyChart;
/** Flag indicating if BMS data is present and the tab should be shown. */
let bmsDataAvailable = false;
/** Caches the last BMS data payload to avoid redundant iframe updates. */
let lastBmsDataString = '';
/** Tracks the last time battery SOC was updated to detect stale data. */
let lastBatterySocUpdate = 0;
/** Stores the last known battery SOC value for comparison. */
let lastBatterySocValue = null;

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
	// Track battery SOC updates for staleness detection
	if (data.hasOwnProperty(SDK.BATTERY_STATE_OF_CHARGE_PERCENT)) {
		const newSocValue = data[SDK.BATTERY_STATE_OF_CHARGE_PERCENT];
		const now = Date.now();
		
		// Check if SOC value has actually changed
		if (newSocValue !== lastBatterySocValue) {
			lastBatterySocUpdate = now;
			lastBatterySocValue = newSocValue;
		}
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
						/* Ignore */ }
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
 * Main rendering function for the dashboard.
 * It takes the raw clientState, transforms it into a structured `flowBoardData` object,
 * and then calls the `updateFlowBoard` function to update the UI.
 * It also updates the "Last Update" timestamp.
 * @param {object} state - The current clientState.
 */
function renderDashboard(state) {
	if (!initialDataReceived || !chartsInitialized || !state) return;
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
		

		
		flowBoardData.battery = {
			power: state[SDK.BATTERY_POWER_WATTS] ?? 0,
			soc: batterySoc,
			kwhUp: state[SDK.ENERGY_BATTERY_DAILY_CHARGE_KWH],
			kwhDown: state[SDK.ENERGY_BATTERY_DAILY_DISCHARGE_KWH],
			volts: state[SDK.BATTERY_VOLTAGE_VOLTS],
			amps: state[SDK.BATTERY_CURRENT_AMPS],
			statusText: state[SDK.BATTERY_STATUS_TEXT],
			runtimeTextDisplay: state.display_battery_time_remaining,
			bmsPluginConnectionStatus: state[SDK.BMS_PLUGIN_CONNECTION_STATUS_KEY_PATTERN.replace('{instance_id}', 'BMS_Seplos_v2')]
		};
		const pvDaily = state[SDK.ENERGY_PV_DAILY_KWH] ?? 0,
			battCharge = state[SDK.ENERGY_BATTERY_DAILY_CHARGE_KWH] ?? 0,
			battDischarge = state[SDK.ENERGY_BATTERY_DAILY_DISCHARGE_KWH] ?? 0,
			gridImport = state[SDK.ENERGY_GRID_DAILY_IMPORT_KWH] ?? 0,
			gridExport = state[SDK.ENERGY_GRID_DAILY_EXPORT_KWH] ?? 0,
			loadTotal = state[SDK.ENERGY_LOAD_DAILY_KWH] ?? 0;
		const loadFromSolar = Math.max(0, pvDaily - battCharge - gridExport);
		const pBLoad = loadTotal > 0.01 ? loadTotal : (loadFromSolar + battDischarge + gridImport);
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
		const lastUpdateEl = document.getElementById('lastUpdate');
		if (lastUpdateEl && state.display_timestamp) {
			lastUpdateEl.textContent = `Last Update: ${state.display_timestamp}`;
		}
	} catch (e) {
		console.error("Error during dashboard rendering:", e);
	}
}

/**
 * Updates the MQTT status indicator button with the correct color and tooltip.
 * @param {string} status - The connection status string (e.g., "Connected", "Disconnected").
 */
function updateMqttStatusButton(status) {
	const mqttButton = document.getElementById('mqttStatus');
	if (!mqttButton) return;

	const statusLower = String(status).toLowerCase();

	if (statusLower === 'disabled') {
		mqttButton.style.display = 'none';
		return;
	}

	mqttButton.style.display = 'inline-flex';

	const dot = document.getElementById('mqtt-dot');
	mqttButton.dataset.tooltip = `MQTT: ${status}`;

	mqttButton.classList.remove('good', 'warning', 'bad');
	if (dot) dot.classList.remove('good-dot', 'warning-dot', 'bad-dot');

	if (statusLower === 'connected') {
		mqttButton.classList.add('good');
		if (dot) dot.classList.add('good-dot');
	} else if (statusLower.includes('connecting') || statusLower.includes('reconnecting')) {
		mqttButton.classList.add('warning');
		if (dot) dot.classList.add('warning-dot');
	} else {
		mqttButton.classList.add('bad');
		if (dot) dot.classList.add('bad-dot');
	}
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
	hideDisconnectPopup();
	if (disconnectTimer) clearTimeout(disconnectTimer);
	clientState = {};
	initialDataReceived = false;
});

socket.on('disconnect', (reason) => {
	console.error('Socket disconnected:', reason);
	showDisconnectPopup(`Disconnected: ${reason}. Reconnecting...`);
	if (disconnectTimer) clearTimeout(disconnectTimer);
	initialDataReceived = false;
});

/** Handles the initial, large data payload from the server upon connection. */
socket.on('full_update', async (data) => {
	if (disconnectTimer) clearTimeout(disconnectTimer);
	disconnectTimer = setTimeout(() => showDisconnectPopup("Connection stalled."), DISCONNECT_TIMEOUT_MS);

	processAndSanitizeData(data);

	await appReadyPromise;

    if (clientState[SDK.BMS_CELL_COUNT] > 0) {
        if (!bmsDataAvailable) {
            bmsDataAvailable = true;
            const bmsTabButton = document.getElementById('bmsViewTab');
            if (bmsTabButton) {
                bmsTabButton.style.display = 'inline-flex';
                bmsTabButton.click(); // Switch to the BMS tab
            }
        }
    } else {
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
	
	// Check for potential stale battery data before processing
	const currentSoc = clientState[SDK.BATTERY_STATE_OF_CHARGE_PERCENT];
	const newSoc = data[SDK.BATTERY_STATE_OF_CHARGE_PERCENT];
	
	processAndSanitizeData(data);



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
	document.addEventListener('visibilitychange', () => {
		if (!document.hidden && socket.connected) {
			showToast('Refreshing data...', 'info', 2000);
			socket.emit('request_full_update');
		}
	});

	const themeToggle = document.getElementById('themeToggle');

    /**
     * Applies a theme to the application and notifies child components (BMS iframe, charts, weather).
     * @param {string} theme - The theme to apply ('light' or 'dark').
     */
	function applyTheme(theme) {
		const body = document.body;
		if (theme === 'dark') {
			body.classList.remove('light');
			body.classList.add('dark');
		} else {
			body.classList.remove('dark');
			body.classList.add('light');
		}
		const bmsIframe = document.getElementById('bms-iframe');
		if (bmsIframe?.contentWindow?.bmsViewer) {
			bmsIframe.contentWindow.bmsViewer.setTheme(theme);
		}
		setTimeout(resizeFlowBoard, 50);
	}

	const savedTheme = getCookie("theme");
	applyTheme(savedTheme ? savedTheme : 'dark');
	
	themeToggle?.addEventListener('click', () => {
		const newTheme = document.body.classList.contains('dark') ? 'light' : 'dark';
		applyTheme(newTheme);
		setCookie("theme", newTheme, 365);
        
        if (chartsInitialized) {
            updateChartTheme(powerChart);
            updateChartTheme(historicalEnergyChart);
            updateChartTheme(hourlyEnergyChart);
        }
        updateWeatherTheme(newTheme);
	});

	const bmsIframe = document.getElementById('bms-iframe');
	if (bmsIframe) {
		bmsIframe.addEventListener('load', () => {
			const currentTheme = getCookie("theme") || 'dark';
			applyTheme(currentTheme);
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
                if(historyControls) historyControls.style.display = 'flex';
            } else if (tabId === 'power-metrics-tab') {
                const powerControls = document.getElementById('powerMetricsControls');
                if(powerControls) powerControls.style.display = 'flex';
            } else if (tabId === 'hourly-tab') {
                const hourlyControls = document.getElementById('hourlyControls');
                if(hourlyControls) hourlyControls.style.display = 'flex';
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
	}

	initializeFlowBoard(debounce);
	startAnimationLoop(() => clientState);
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
			socket.emit('request_full_update');
			showToast('Refreshing flow board data...', 'info', 2000);
			
			// Remove spinning animation after 2 seconds
			setTimeout(() => {
				flowBoardRefreshBtn.classList.remove('spinning');
			}, 2000);
		});
	}

	// Set up periodic check for stale data
	setInterval(() => {
		if (initialDataReceived && socket.connected) {
			const now = Date.now();
			const timeSinceLastSocUpdate = now - lastBatterySocUpdate;
			
			// If battery SOC hasn't updated in 15 minutes, auto-request fresh data
			if (timeSinceLastSocUpdate > 900000) { // 15 minutes
				console.warn(`[STALE DATA] Battery SOC hasn't updated for ${Math.round(timeSinceLastSocUpdate / 60000)} minutes - requesting refresh`);
				socket.emit('request_full_update');
				showToast('Refreshing stale data...', 'warning', 3000);
			}
		}
	}, 300000); // Check every 5 minutes

	resolveAppReady();
};