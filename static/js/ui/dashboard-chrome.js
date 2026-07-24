/**
 * Dashboard chrome: alerts, KPIs, data age, settings, layout customize, kiosk.
 */
import { SDK } from '../config.js';
import { formatNum, getCookie, setCookie, showToast } from '../utils.js';
import { THEMES, applyThemeId, resolveThemeId } from './themes.js';

const STORAGE_KEY = 'solar_dash_prefs_v1';
const ALERT_HISTORY_KEY = 'solar_dash_alert_history_v1';
const ALERT_HISTORY_MAX = 30;

const DEFAULT_PREFS = {
	theme: 'midnight',
	panels: {
		flow: true,
		kpi: true,
		alerts: true,
		weather: true,
		history: true,
		hourly: true,
		bms: true,
		mqtt: true,
	},
	staleSeconds: 30,
	weather: {
		lat: null,
		lon: null,
		zoom: null,
		tempUnit: null,
		autoLocation: null,
	},
	kiosk: false,
};

let prefs = loadPrefs();
let lastDataAt = 0;
let ageTimer = null;
let alertHistory = loadAlertHistory();

function loadPrefs() {
	try {
		const raw = localStorage.getItem(STORAGE_KEY);
		if (!raw) {
			const prefs0 = structuredClone(DEFAULT_PREFS);
			prefs0.theme = resolveThemeId(getCookie('theme') || 'midnight');
			return prefs0;
		}
		const parsed = JSON.parse(raw);
		const merged = {
			...structuredClone(DEFAULT_PREFS),
			...parsed,
			panels: { ...DEFAULT_PREFS.panels, ...(parsed.panels || {}) },
			weather: { ...DEFAULT_PREFS.weather, ...(parsed.weather || {}) },
		};
		merged.theme = resolveThemeId(parsed.theme || getCookie('theme') || 'midnight');
		return merged;
	} catch {
		return structuredClone(DEFAULT_PREFS);
	}
}

function savePrefs() {
	try {
		localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
	} catch (e) {
		console.warn('Could not save dashboard prefs', e);
	}
}

function loadAlertHistory() {
	try {
		const raw = sessionStorage.getItem(ALERT_HISTORY_KEY);
		return raw ? JSON.parse(raw) : [];
	} catch {
		return [];
	}
}

function saveAlertHistory() {
	try {
		sessionStorage.setItem(ALERT_HISTORY_KEY, JSON.stringify(alertHistory.slice(0, ALERT_HISTORY_MAX)));
	} catch { /* ignore */ }
}

function num(v, fallback = 0) {
	const n = parseFloat(v);
	return Number.isFinite(n) ? n : fallback;
}

function isBenignAlert(msg) {
	const s = String(msg || '').toLowerCase().trim();
	return !s || s === 'ok' || s === 'normal' || s === 'none' || s === 'n/a';
}

/**
 * Collect active alerts from live state.
 * @returns {{severity: string, category: string, message: string}[]}
 */
export function collectAlerts(state) {
	const out = [];
	const cats = state?.[SDK.OPERATIONAL_CATEGORIZED_ALERTS_DICT];
	if (cats && typeof cats === 'object' && !Array.isArray(cats)) {
		for (const [category, list] of Object.entries(cats)) {
			if (!Array.isArray(list)) continue;
			for (const message of list) {
				if (isBenignAlert(message)) continue;
				out.push({ severity: category === 'fault' || category === 'inverter' ? 'bad' : 'warn', category, message: String(message) });
			}
		}
	}
	const faults = state?.[SDK.OPERATIONAL_ACTIVE_FAULT_MESSAGES_LIST];
	if (Array.isArray(faults)) {
		for (const message of faults) {
			if (isBenignAlert(message)) continue;
			out.push({ severity: 'bad', category: 'fault', message: String(message) });
		}
	}
	const bmsAlarms = state?.bms_active_alarms_list;
	if (Array.isArray(bmsAlarms)) {
		for (const message of bmsAlarms) {
			if (isBenignAlert(message)) continue;
			out.push({ severity: 'bad', category: 'bms', message: String(message) });
		}
	}
	const bmsWarns = state?.bms_active_warnings_list;
	if (Array.isArray(bmsWarns)) {
		for (const message of bmsWarns) {
			if (isBenignAlert(message)) continue;
			out.push({ severity: 'warn', category: 'bms', message: String(message) });
		}
	}
	// Deduplicate by category+message
	const seen = new Set();
	return out.filter((a) => {
		const key = `${a.category}|${a.message}`;
		if (seen.has(key)) return false;
		seen.add(key);
		return true;
	});
}

function rememberAlerts(alerts) {
	const now = Date.now();
	for (const a of alerts) {
		const key = `${a.category}|${a.message}`;
		const existing = alertHistory.find((h) => h.key === key);
		if (existing) {
			existing.lastSeen = now;
			existing.count = (existing.count || 1) + 1;
		} else {
			alertHistory.unshift({
				key,
				category: a.category,
				message: a.message,
				severity: a.severity,
				firstSeen: now,
				lastSeen: now,
				count: 1,
			});
		}
	}
	alertHistory = alertHistory.slice(0, ALERT_HISTORY_MAX);
	saveAlertHistory();
}

export function updateAlertsPanel(state) {
	const banner = document.getElementById('alerts-banner');
	const listEl = document.getElementById('alerts-active-list');
	const histEl = document.getElementById('alerts-history-list');
	const countEl = document.getElementById('alerts-count');
	if (!banner || !listEl) return;

	const alerts = collectAlerts(state);
	rememberAlerts(alerts);

	banner.classList.toggle('has-alerts', alerts.length > 0);
	banner.classList.toggle('alerts-ok', alerts.length === 0);
	if (countEl) countEl.textContent = String(alerts.length);

	if (alerts.length === 0) {
		listEl.innerHTML = `<div class="alerts-ok-msg">No active faults — ${state?.[SDK.OPERATIONAL_INVERTER_STATUS_TEXT] || 'OK'}</div>`;
	} else {
		listEl.innerHTML = alerts.map((a) =>
			`<div class="alert-item ${a.severity}"><span class="alert-cat">${escapeHtml(a.category)}</span><span class="alert-msg">${escapeHtml(a.message)}</span></div>`
		).join('');
	}

	if (histEl) {
		const recent = alertHistory.slice(0, 8);
		histEl.innerHTML = recent.length
			? recent.map((h) => {
				const age = formatAge(Date.now() - h.lastSeen);
				return `<div class="alert-hist-item ${h.severity}"><span class="alert-cat">${escapeHtml(h.category)}</span><span class="alert-msg">${escapeHtml(h.message)}</span><span class="alert-age">${age}</span></div>`;
			}).join('')
			: '<div class="alerts-ok-msg">No recent alert history</div>';
	}
}

export function updateKpiStrip(state) {
	const root = document.getElementById('kpi-strip');
	const mobile = document.getElementById('mobile-summary');
	if (!root && !mobile) return;

	const pvDaily = num(state?.[SDK.ENERGY_PV_DAILY_KWH]);
	const battCharge = num(state?.[SDK.ENERGY_BATTERY_DAILY_CHARGE_KWH]);
	const battDischarge = num(state?.[SDK.ENERGY_BATTERY_DAILY_DISCHARGE_KWH]);
	const gridImport = num(state?.[SDK.ENERGY_GRID_DAILY_IMPORT_KWH]);
	const gridExport = num(state?.[SDK.ENERGY_GRID_DAILY_EXPORT_KWH]);
	const loadTotal = num(state?.[SDK.ENERGY_LOAD_DAILY_KWH]);
	const soc = num(state?.[SDK.BATTERY_STATE_OF_CHARGE_PERCENT]);
	const pvNow = num(state?.[SDK.PV_TOTAL_DC_POWER_WATTS]);
	const loadNow = num(state?.[SDK.LOAD_TOTAL_POWER_WATTS]);
	const gridNow = num(state?.[SDK.GRID_TOTAL_ACTIVE_POWER_WATTS]);
	const runtime = state?.display_battery_time_remaining || 'N/A';

	const loadFromSolar = Math.max(0, pvDaily - battCharge - gridExport);
	const sourceSum = loadFromSolar + battDischarge + gridImport;
	const selfPct = sourceSum > 0.01 ? (loadFromSolar / sourceSum) * 100 : 0;
	const autonomyPct = sourceSum > 0.01 ? ((loadFromSolar + battDischarge) / sourceSum) * 100 : 0;

	const items = [
		{ id: 'pv', label: 'PV Today', value: `${formatNum(pvDaily, 1)} kWh`, sub: `${formatNum(pvNow, 0)} W now` },
		{ id: 'load', label: 'Load Today', value: `${formatNum(loadTotal, 1)} kWh`, sub: `${formatNum(loadNow, 0)} W now` },
		{ id: 'import', label: 'Grid Import', value: `${formatNum(gridImport, 1)} kWh`, sub: gridNow >= 0 ? `Import ${formatNum(Math.abs(gridNow), 0)} W` : `Export ${formatNum(Math.abs(gridNow), 0)} W` },
		{ id: 'export', label: 'Grid Export', value: `${formatNum(gridExport, 1)} kWh`, sub: '' },
		{ id: 'self', label: 'Self-Use', value: `${formatNum(selfPct, 0)}%`, sub: `${formatNum(loadFromSolar, 1)} kWh from PV` },
		{ id: 'auto', label: 'Autonomy', value: `${formatNum(autonomyPct, 0)}%`, sub: 'PV + battery vs load' },
		{ id: 'soc', label: 'Battery SOC', value: `${formatNum(soc, 0)}%`, sub: String(runtime) },
	];

	if (root) {
		root.innerHTML = items.map((it) =>
			`<div class="kpi-card kpi-${it.id}"><div class="kpi-label">${it.label}</div><div class="kpi-value">${it.value}</div><div class="kpi-sub">${it.sub || '&nbsp;'}</div></div>`
		).join('');
	}

	if (mobile) {
		mobile.innerHTML = `
			<div class="ms-card"><span class="ms-label">PV</span><span class="ms-value">${formatNum(pvNow, 0)} W</span><span class="ms-sub">${formatNum(pvDaily, 1)} kWh</span></div>
			<div class="ms-card"><span class="ms-label">Load</span><span class="ms-value">${formatNum(loadNow, 0)} W</span><span class="ms-sub">${formatNum(loadTotal, 1)} kWh</span></div>
			<div class="ms-card"><span class="ms-label">SOC</span><span class="ms-value">${formatNum(soc, 0)}%</span><span class="ms-sub">${escapeHtml(String(runtime))}</span></div>
			<div class="ms-card"><span class="ms-label">Grid</span><span class="ms-value">${formatNum(Math.abs(gridNow), 0)} W</span><span class="ms-sub">${gridNow >= 0 ? 'Import' : 'Export'}</span></div>
		`;
	}
}

export function markDataReceived() {
	lastDataAt = Date.now();
	updateDataAgeDisplay();
}

function formatAge(ms) {
	const s = Math.max(0, Math.floor(ms / 1000));
	if (s < 60) return `${s}s ago`;
	const m = Math.floor(s / 60);
	if (m < 60) return `${m}m ago`;
	return `${Math.floor(m / 60)}h ago`;
}

export function updateDataAgeDisplay() {
	const ageEl = document.getElementById('data-age');
	const lastUpdateEl = document.getElementById('lastUpdate');
	const footer = document.querySelector('footer');
	if (!lastDataAt) return;
	const ageMs = Date.now() - lastDataAt;
	const ageText = formatAge(ageMs);
	const staleSec = Math.max(5, num(prefs.staleSeconds, 30));
	const stale = ageMs > staleSec * 1000;

	if (ageEl) ageEl.textContent = ageText;
	if (lastUpdateEl) {
		lastUpdateEl.classList.toggle('stale', stale);
		if (ageEl) {
			/* age shown separately */
		} else {
			const base = lastUpdateEl.dataset.baseStamp || lastUpdateEl.textContent.replace(/^Last Update:\s*/, '');
			lastUpdateEl.dataset.baseStamp = base;
			lastUpdateEl.textContent = `Last Update: ${base} (${ageText})`;
		}
	}
	footer?.classList.toggle('data-stale', stale);
	document.body.classList.toggle('data-stale', stale);
}

function escapeHtml(s) {
	return String(s)
		.replace(/&/g, '&amp;')
		.replace(/</g, '&lt;')
		.replace(/>/g, '&gt;')
		.replace(/"/g, '&quot;');
}

export function applyPanelVisibility() {
	const p = prefs.panels;
	toggle('energy-flow-diagram-container', p.flow, true);
	toggle('kpi-strip-section', p.kpi);
	toggle('alerts-banner', p.alerts);
	toggle('mqttStatus', p.mqtt);

	const weatherTab = document.getElementById('weatherViewTab');
	const weatherEnabled = !!(window.WEATHER_CONFIG && window.WEATHER_CONFIG.enabled);
	if (weatherTab) {
		weatherTab.style.display = weatherEnabled && p.weather ? '' : 'none';
		if (!p.weather && weatherTab.classList.contains('active')) {
			document.querySelector('#top-tab-section .tab-link[data-tab="power-metrics-tab"]')?.click();
		}
	}

	const histBtn = document.querySelector('#tabbed-card-section .tab-link[data-tab="history-tab"]');
	const hourlyBtn = document.querySelector('#tabbed-card-section .tab-link[data-tab="hourly-tab"]');
	const bmsBtn = document.getElementById('bmsViewTab');
	if (histBtn) histBtn.style.display = p.history ? '' : 'none';
	if (hourlyBtn) hourlyBtn.style.display = p.hourly ? '' : 'none';
	if (bmsBtn && bmsBtn.dataset.available === '1') {
		bmsBtn.style.display = p.bms ? '' : 'none';
	}
}

function toggle(id, show, isClass = false) {
	const el = isClass ? document.querySelector(`.${id}`) : document.getElementById(id);
	if (!el) return;
	el.style.display = show ? '' : 'none';
	el.classList.toggle('prefs-hidden', !show);
}

export function applyWeatherOverrides() {
	if (!window.WEATHER_CONFIG) return;
	const w = prefs.weather;
	if (w.lat != null && w.lat !== '') window.WEATHER_CONFIG.default_lat = Number(w.lat);
	if (w.lon != null && w.lon !== '') window.WEATHER_CONFIG.default_lon = Number(w.lon);
	if (w.zoom != null && w.zoom !== '') window.WEATHER_CONFIG.map_zoom_level = Number(w.zoom);
	if (w.tempUnit) window.WEATHER_CONFIG.temp_unit = w.tempUnit;
	if (w.autoLocation != null) window.WEATHER_CONFIG.use_auto_location = !!w.autoLocation;
}

export function setKioskMode(on) {
	prefs.kiosk = !!on;
	document.body.classList.toggle('kiosk-mode', prefs.kiosk);
	const btn = document.getElementById('kioskToggle');
	if (btn) btn.textContent = prefs.kiosk ? 'Exit Kiosk' : 'Kiosk';
	savePrefs();
	if (prefs.kiosk && document.documentElement.requestFullscreen) {
		document.documentElement.requestFullscreen().catch(() => {});
	} else if (!prefs.kiosk && document.fullscreenElement) {
		document.exitFullscreen?.().catch(() => {});
	}
	// Reflow flow board after chrome/layout changes
	requestAnimationFrame(() => {
		document.dispatchEvent(new CustomEvent('solar-dash-flow-resize'));
		setTimeout(() => document.dispatchEvent(new CustomEvent('solar-dash-flow-resize')), 200);
	});
}

function fillSettingsForm() {
	const form = document.getElementById('dash-settings-form');
	if (!form) return;
	form.querySelectorAll('[data-panel]').forEach((cb) => {
		cb.checked = !!prefs.panels[cb.dataset.panel];
	});
	const stale = form.querySelector('#setting-stale-seconds');
	if (stale) stale.value = prefs.staleSeconds;
	const w = prefs.weather;
	const set = (id, val) => {
		const el = form.querySelector(id);
		if (el) el.value = val ?? '';
	};
	set('#setting-weather-lat', w.lat ?? window.WEATHER_CONFIG?.default_lat ?? '');
	set('#setting-weather-lon', w.lon ?? window.WEATHER_CONFIG?.default_lon ?? '');
	set('#setting-weather-zoom', w.zoom ?? window.WEATHER_CONFIG?.map_zoom_level ?? '');
	const unit = form.querySelector('#setting-weather-unit');
	if (unit) unit.value = w.tempUnit || window.WEATHER_CONFIG?.temp_unit || 'celsius';
	const auto = form.querySelector('#setting-weather-auto');
	if (auto) auto.checked = w.autoLocation != null ? !!w.autoLocation : !!window.WEATHER_CONFIG?.use_auto_location;
	syncThemePickerSelection();
}

function readSettingsForm() {
	const form = document.getElementById('dash-settings-form');
	if (!form) return;
	form.querySelectorAll('[data-panel]').forEach((cb) => {
		prefs.panels[cb.dataset.panel] = cb.checked;
	});
	prefs.staleSeconds = Math.max(5, parseInt(form.querySelector('#setting-stale-seconds')?.value || '30', 10) || 30);
	prefs.weather = {
		lat: form.querySelector('#setting-weather-lat')?.value || null,
		lon: form.querySelector('#setting-weather-lon')?.value || null,
		zoom: form.querySelector('#setting-weather-zoom')?.value || null,
		tempUnit: form.querySelector('#setting-weather-unit')?.value || null,
		autoLocation: !!form.querySelector('#setting-weather-auto')?.checked,
	};
	const selected = form.querySelector('#setting-theme-select');
	if (selected) prefs.theme = resolveThemeId(selected.value);
}

function syncThemePickerSelection() {
	const sel = document.getElementById('setting-theme-select');
	if (sel) sel.value = prefs.theme;
}

function renderThemePicker() {
	const sel = document.getElementById('setting-theme-select');
	if (!sel) return;
	sel.innerHTML = THEMES.map((t) => {
		const modeTag = t.mode === 'dark' ? 'Dark' : 'Light';
		return `<option value="${t.id}">${t.label} — ${t.desc} (${modeTag})</option>`;
	}).join('');
	sel.value = prefs.theme;
	sel.onchange = () => {
		selectTheme(sel.value);
	};
}

/**
 * Apply a theme and persist in prefs.
 * @param {string} themeId
 */
export function selectTheme(themeId) {
	prefs.theme = resolveThemeId(themeId);
	const theme = applyThemeId(prefs.theme);
	savePrefs();
	setCookie('theme', theme.id, 365);
	return theme;
}

export function applyStoredTheme() {
	const id = resolveThemeId(prefs.theme || getCookie('theme') || 'midnight');
	prefs.theme = id;
	return applyThemeId(id);
}

function setSettingsOpen(open) {
	const panel = document.getElementById('dash-settings-panel');
	const backdrop = document.getElementById('dash-settings-backdrop');
	if (!panel) return;
	panel.hidden = !open;
	if (backdrop) backdrop.hidden = !open;
	document.body.classList.toggle('settings-open', open);
	if (open) fillSettingsForm();
}

/**
 * Wire chrome controls once after DOM ready.
 */
export function initDashboardChrome() {
	applyStoredTheme();
	applyWeatherOverrides();
	applyPanelVisibility();
	renderThemePicker();
	setKioskMode(prefs.kiosk);

	if (ageTimer) clearInterval(ageTimer);
	ageTimer = setInterval(updateDataAgeDisplay, 1000);

	document.getElementById('settingsToggle')?.addEventListener('click', () => setSettingsOpen(true));
	document.getElementById('dash-settings-close')?.addEventListener('click', () => setSettingsOpen(false));
	document.getElementById('dash-settings-backdrop')?.addEventListener('click', () => setSettingsOpen(false));
	document.getElementById('kioskToggle')?.addEventListener('click', () => setKioskMode(!prefs.kiosk));

	document.getElementById('dash-settings-save')?.addEventListener('click', () => {
		readSettingsForm();
		selectTheme(prefs.theme);
		savePrefs();
		applyWeatherOverrides();
		applyPanelVisibility();
		setSettingsOpen(false);
		showToast('Dashboard settings saved (this browser)', 'success', 2500);
	});

	document.getElementById('dash-settings-reset')?.addEventListener('click', () => {
		prefs = structuredClone(DEFAULT_PREFS);
		savePrefs();
		selectTheme(prefs.theme);
		renderThemePicker();
		fillSettingsForm();
		applyWeatherOverrides();
		applyPanelVisibility();
		setKioskMode(false);
		showToast('Settings reset to defaults', 'info', 2500);
	});

	document.getElementById('alerts-toggle-history')?.addEventListener('click', () => {
		document.getElementById('alerts-history')?.classList.toggle('open');
	});

	document.addEventListener('keydown', (e) => {
		if (e.key === 'Escape') {
			if (document.body.classList.contains('settings-open')) setSettingsOpen(false);
			else if (prefs.kiosk) setKioskMode(false);
		}
	});

	document.addEventListener('solar-dash-prefs-apply', () => applyPanelVisibility());

	document.addEventListener('fullscreenchange', () => {
		if (!document.fullscreenElement && prefs.kiosk) {
			prefs.kiosk = false;
			document.body.classList.remove('kiosk-mode');
			const btn = document.getElementById('kioskToggle');
			if (btn) btn.textContent = 'Kiosk';
			savePrefs();
		}
	});
}

/** Mark BMS tab as available so customize prefs can show/hide it. */
export function markBmsAvailable(available) {
	const bmsBtn = document.getElementById('bmsViewTab');
	if (bmsBtn) bmsBtn.dataset.available = available ? '1' : '0';
	applyPanelVisibility();
}

export function getPrefs() {
	return prefs;
}
