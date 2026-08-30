/**
 * ESP32 display global config (display_config.json) + mockup gallery.
 */
const DISPLAY_LAYOUTS = [
	{ id: 0, name: 'Classic', desc: 'Large SOC + 2×2 tiles' },
	{ id: 1, name: 'Compact', desc: 'Dense metric row' },
	{ id: 2, name: 'Ring', desc: 'SOC arc gauge' },
	{ id: 3, name: 'Bars', desc: 'Power bar meters' },
	{ id: 4, name: 'Flow', desc: 'Energy flow diagram' },
];

const DISPLAY_THEMES = [
	{ id: 0, name: 'Dark', bg: '#000', card: '#1c1c1e', text: '#fff', accent: '#0a84ff', pv: '#ff9f0a' },
	{ id: 1, name: 'Light', bg: '#f2f2f7', card: '#fff', text: '#111', accent: '#007aff', pv: '#ff9500' },
	{ id: 2, name: 'Solar', bg: '#1a1208', card: '#2a2010', text: '#fff', accent: '#ff9f0a', pv: '#ffb340' },
	{ id: 3, name: 'Ocean', bg: '#0a1628', card: '#122240', text: '#e8f4ff', accent: '#34c759', pv: '#5ac8fa' },
	{ id: 4, name: 'Forest', bg: '#0a1a0e', card: '#142818', text: '#e8ffe8', accent: '#30d158', pv: '#ffd60a' },
];

const DEMO_GLANCE = {
	title: 'My Solar',
	soc: 78,
	pv_w: 3400,
	load_w: 820,
	grid_w: 120,
	pv_today_kwh: 12.6,
	grid_state: 'export',
};

let displayConfig = null;
let displayPinUnlocked = false;
let displaySessionPin = '';
let previewOrient = 'portrait';
let previewTheme = 0;
let previewLayout = 0;

function themeVars(tid) {
	const t = DISPLAY_THEMES[tid] || DISPLAY_THEMES[0];
	return `--dm-bg:${t.bg};--dm-card:${t.card};--dm-text:${t.text};--dm-header:${t.bg};--dm-muted:#888;--dm-accent:${t.accent};--dm-pv:${t.pv};`;
}

function mockBodyClassic(parent, g, landscape) {
	parent.innerHTML = landscape
		? `<div style="display:flex;height:100%;gap:2px">
			<div style="flex:1;text-align:center"><div style="font-size:10px;font-weight:700">${Math.round(g.soc)}%</div><div style="height:3px;background:var(--dm-accent);margin-top:2px;width:${g.soc}%"></div></div>
			<div style="flex:2;display:grid;grid-template:1fr 1fr;gap:2px;font-size:4px">
				<span style="background:var(--dm-card);padding:2px">PV ${(g.pv_w/1000).toFixed(1)}k</span>
				<span style="background:var(--dm-card);padding:2px">Ld ${(g.load_w/1000).toFixed(1)}k</span>
				<span style="background:var(--dm-card);padding:2px">Gr</span><span style="background:var(--dm-card);padding:2px">Today</span>
			</div></div>`
		: `<div style="text-align:center;font-size:12px;font-weight:700;margin:2px 0">${Math.round(g.soc)}%</div>
			<div style="display:grid;grid-template:1fr 1fr;gap:2px;height:calc(100% - 20px);font-size:4px">
				<span style="background:var(--dm-card);padding:3px;color:var(--dm-pv)">Solar ${(g.pv_w/1000).toFixed(1)}kW</span>
				<span style="background:var(--dm-card);padding:3px">Home ${(g.load_w/1000).toFixed(1)}kW</span>
				<span style="background:var(--dm-card);padding:3px">Grid</span>
				<span style="background:var(--dm-card);padding:3px">${g.pv_today_kwh} kWh</span>
			</div>`;
}

function mockBodyCompact(parent, g, landscape) {
	const row = `PV ${(g.pv_w/1000).toFixed(1)} | Ld ${(g.load_w/1000).toFixed(1)} | Gr`;
	parent.innerHTML = `<div style="font-size:9px;text-align:center">${Math.round(g.soc)}%</div>
		<div style="font-size:4px;margin-top:4px;text-align:center;background:var(--dm-card);padding:2px">${row}</div>
		<div style="font-size:4px;margin-top:2px;text-align:center">Today ${g.pv_today_kwh} kWh</div>`;
}

function mockBodyRing(parent, g) {
	parent.innerHTML = `<div style="display:flex;align-items:center;justify-content:center;height:100%">
		<div style="width:40px;height:40px;border:3px solid var(--dm-card);border-top-color:var(--dm-accent);border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:8px">${Math.round(g.soc)}</div></div>`;
}

function mockBodyBars(parent, g, landscape) {
	const bar = (label, w, max, col) =>
		`<div style="margin:2px 0"><span style="font-size:3px">${label}</span>
		<div style="height:4px;background:var(--dm-card)"><div style="width:${Math.min(100,w/max*100)}%;height:100%;background:${col}"></div></div></div>`;
	parent.innerHTML = bar('PV', g.pv_w, 5000, 'var(--dm-pv)') + bar('Load', g.load_w, 5000, 'var(--dm-text)') +
		bar('Grid', Math.abs(g.grid_w), 3000, 'var(--dm-accent)') +
		`<div style="font-size:6px;margin-top:4px">SOC ${Math.round(g.soc)}%</div>`;
}

function mockBodyFlow(parent, g, landscape) {
	parent.innerHTML = landscape
		? `<div style="display:flex;align-items:center;justify-content:center;height:100%;font-size:4px;gap:4px">
			<span style="color:var(--dm-pv)">PV</span>→<span>Home</span>←<span style="color:var(--dm-accent)">Grid</span></div>`
		: `<div style="text-align:center;padding-top:20%;font-size:4px;line-height:1.8">
			<div style="color:var(--dm-pv)">☀ PV ${(g.pv_w/1000).toFixed(1)}kW</div>
			<div>↓ Home ${(g.load_w/1000).toFixed(1)}kW</div>
			<div style="color:var(--dm-accent)">⚡ Grid</div>
			<div style="margin-top:4px">${Math.round(g.soc)}% SOC</div></div>`;
}

const MOCK_RENDERERS = [
	(g, l) => mockBodyClassic(null, g, l),
	(g, l) => mockBodyCompact(null, g, l),
	(g, l) => mockBodyRing(null, g, false),
	(g, l) => mockBodyBars(null, g, l),
	(g, l) => mockBodyFlow(null, g, l),
];

function renderMockFrame(layoutId, themeId, orient, glance) {
	const g = glance || DEMO_GLANCE;
	const landscape = orient === 'landscape';
	const wrap = document.createElement('div');
	wrap.className = `display-mock-frame ${landscape ? 'landscape' : 'portrait'}`;
	wrap.style.cssText = themeVars(themeId);
	const header = document.createElement('div');
	header.className = 'display-mock-header';
	header.innerHTML = `<span>${g.title || 'Solar'}</span><span>12:00</span>`;
	const body = document.createElement('div');
	body.className = 'display-mock-body';
	const fn = MOCK_RENDERERS[layoutId] || MOCK_RENDERERS[0];
	if (layoutId === 0) mockBodyClassic(body, g, landscape);
	else if (layoutId === 1) mockBodyCompact(body, g, landscape);
	else if (layoutId === 2) mockBodyRing(body, g, landscape);
	else if (layoutId === 3) mockBodyBars(body, g, landscape);
	else mockBodyFlow(body, g, landscape);
	const nav = document.createElement('div');
	nav.className = 'display-mock-nav';
	nav.innerHTML = '<span class="on">Home</span><span>BMS</span><span>Hist</span><span>Set</span>';
	wrap.appendChild(header);
	wrap.appendChild(body);
	wrap.appendChild(nav);
	return wrap;
}

function renderLayoutGallery() {
	const gal = document.getElementById('display-layout-gallery');
	if (!gal) return;
	gal.innerHTML = '';
	DISPLAY_LAYOUTS.forEach((lay) => {
		const card = document.createElement('div');
		card.className = 'display-layout-card' + (lay.id === previewLayout ? ' selected' : '');
		card.dataset.layout = lay.id;
		card.innerHTML = `<h4>${lay.name}</h4><p>${lay.desc}</p>`;
		const mount = document.createElement('div');
		mount.appendChild(renderMockFrame(lay.id, previewTheme, previewOrient, DEMO_GLANCE));
		card.appendChild(mount);
		card.addEventListener('click', () => {
			previewLayout = lay.id;
			const sel = document.getElementById('display-glance-layout');
			if (sel) sel.value = String(lay.id);
			renderLayoutGallery();
		});
		gal.appendChild(card);
	});
}

function renderThemeSwatches() {
	const row = document.getElementById('display-theme-swatches');
	if (!row) return;
	row.innerHTML = '';
	DISPLAY_THEMES.forEach((t) => {
		const sw = document.createElement('button');
		sw.type = 'button';
		sw.className = 'display-theme-swatch' + (t.id === previewTheme ? ' selected' : '');
		sw.style.background = t.bg;
		sw.textContent = t.name;
		sw.addEventListener('click', () => {
			previewTheme = t.id;
			const sel = document.getElementById('display-theme-id');
			if (sel) sel.value = String(t.id);
			renderThemeSwatches();
			renderLayoutGallery();
		});
		row.appendChild(sw);
	});
}

function readDisplayForm() {
	const get = (id, def) => document.getElementById(id)?.value ?? def;
	const getChk = (id, def) => document.getElementById(id)?.checked ?? def;
	return {
		glance_layout: parseInt(get('display-glance-layout', '0'), 10) || 0,
		theme: parseInt(get('display-theme-id', '0'), 10) || 0,
		rotation: parseInt(get('display-rotation', '0'), 10) || 0,
		brightness: Math.min(255, Math.max(0, parseInt(get('display-brightness', '200'), 10) || 200)),
		poll_ms: Math.min(60000, Math.max(2000, parseInt(get('display-poll-ms', '5000'), 10) || 5000)),
		grid_offline_alert: getChk('display-grid-alert', true),
		check_for_update: getChk('display-check-update', false),
		auto_install_update: getChk('display-auto-update', false),
	};
}

function readDisplayPinField() {
	const el = document.getElementById('display-settings-pin');
	const v = (el?.value || '').trim();
	return /^\d{4}$/.test(v) ? v : '';
}

function fillDisplayForm(cfg) {
	if (!cfg) return;
	const set = (id, v) => { const el = document.getElementById(id); if (el) el.value = v; };
	const setChk = (id, v) => { const el = document.getElementById(id); if (el) el.checked = !!v; };
	set('display-glance-layout', cfg.glance_layout ?? 0);
	set('display-theme-id', cfg.theme ?? 0);
	set('display-rotation', cfg.rotation ?? 0);
	set('display-brightness', cfg.brightness ?? 200);
	set('display-poll-ms', cfg.poll_ms ?? 5000);
	setChk('display-grid-alert', cfg.grid_offline_alert !== false);
	setChk('display-check-update', cfg.check_for_update);
	setChk('display-auto-update', cfg.auto_install_update);
	const pinEl = document.getElementById('display-settings-pin');
	if (pinEl) pinEl.value = '';
	previewLayout = cfg.glance_layout ?? 0;
	previewTheme = cfg.theme ?? 0;
	renderThemeSwatches();
	renderLayoutGallery();
}

function setDisplaySectionLocked(locked) {
	const fs = document.getElementById('display-settings-fieldset');
	if (!fs) return;
	fs.classList.toggle('display-settings-locked', locked);
	fs.querySelectorAll('input,select,button').forEach((el) => {
		if (el.id === 'display-pin-unlock-btn') return;
		el.disabled = locked;
	});
	const gate = document.getElementById('display-pin-gate');
	if (gate) gate.hidden = !locked;
}

async function verifyDisplayPin(pin) {
	const r = await fetch('/api/display/verify-pin', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ pin }),
	});
	if (!r.ok) return false;
	const data = await r.json();
	return !!data.unlocked;
}

async function ensureDisplayPinUnlocked() {
	if (!displayConfig?.settings_pin_set) {
		displayPinUnlocked = true;
		setDisplaySectionLocked(false);
		return true;
	}
	if (displayPinUnlocked && displaySessionPin) {
		setDisplaySectionLocked(false);
		return true;
	}
	setDisplaySectionLocked(true);
	return false;
}

async function promptDisplayPin() {
	const pin = window.prompt('Enter 4-digit display settings PIN');
	if (!pin) return false;
	if (!/^\d{4}$/.test(pin.trim())) {
		alert('PIN must be exactly 4 digits');
		return false;
	}
	if (!(await verifyDisplayPin(pin.trim()))) {
		alert('Wrong PIN');
		return false;
	}
	displaySessionPin = pin.trim();
	displayPinUnlocked = true;
	setDisplaySectionLocked(false);
	return true;
}

export async function loadDisplayConfig() {
	try {
		const r = await fetch('/api/display/config');
		if (!r.ok) throw new Error(String(r.status));
		displayConfig = await r.json();
		displayPinUnlocked = !displayConfig.settings_pin_set;
		displaySessionPin = '';
		fillDisplayForm(displayConfig);
		await ensureDisplayPinUnlocked();
		return displayConfig;
	} catch (e) {
		console.warn('Display config load failed', e);
		return null;
	}
}

export async function saveDisplayConfig(extra = {}) {
	const body = { ...readDisplayForm(), ...extra };
	const newPin = readDisplayPinField();
	if (newPin) body.settings_pin = newPin;
	if (displayConfig?.settings_pin_set) {
		if (!displaySessionPin) throw new Error('Unlock display settings with PIN first');
		body.pin = displaySessionPin;
	}
	const r = await fetch('/api/display/config', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(body),
	});
	if (!r.ok) throw new Error(await r.text());
	displayConfig = await r.json();
	return displayConfig;
}

export async function fetchDisplayUpdateInfo() {
	const r = await fetch('/api/display/update-info');
	return r.json();
}

export function initDisplaySettings() {
	document.getElementById('display-pin-unlock-btn')?.addEventListener('click', async () => {
		await promptDisplayPin();
	});
	document.querySelectorAll('input[name="display-preview-orient"]').forEach((el) => {
		el.addEventListener('change', () => {
			if (el.checked) {
				previewOrient = el.value;
				renderLayoutGallery();
			}
		});
	});
	['display-glance-layout', 'display-theme-id'].forEach((id) => {
		document.getElementById(id)?.addEventListener('change', (e) => {
			if (id === 'display-glance-layout') previewLayout = parseInt(e.target.value, 10) || 0;
			else previewTheme = parseInt(e.target.value, 10) || 0;
			renderLayoutGallery();
			renderThemeSwatches();
		});
	});
	document.getElementById('display-save-btn')?.addEventListener('click', async () => {
		try {
			await saveDisplayConfig();
			const st = document.getElementById('display-save-status');
			if (st) { st.textContent = 'Saved — devices polling host will apply.'; }
		} catch (e) {
			alert('Save failed: ' + e.message);
		}
	});
	document.getElementById('display-force-update-btn')?.addEventListener('click', async () => {
		try {
			await saveDisplayConfig({ force_update: true });
			const st = document.getElementById('display-ota-status');
			if (st) st.textContent = 'Force update queued for displays using host settings.';
		} catch (e) {
			alert(e.message);
		}
	});
	document.getElementById('display-check-update-btn')?.addEventListener('click', async () => {
		const info = await fetchDisplayUpdateInfo();
		const st = document.getElementById('display-ota-status');
		if (st) {
			if (info.release?.tag) st.textContent = `Latest: ${info.release.tag}`;
			else st.textContent = info.error || 'No release info';
		}
	});
	loadDisplayConfig();
}
