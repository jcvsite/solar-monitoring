/**
 * @file Manages the main energy flow diagram on the dashboard.
 * This module handles DOM element caching, SVG path animations for energy flow,
 * dynamic updates to power/energy text values, and visual state changes
 * (e.g., dimming inactive components, showing fault lights).
 */
import {
	SDK,
	FLOW_THRESHOLD_W,
	MIN_VOLTAGE_FOR_ACTIVE_STRING,
	JS_TUYA_STATE_ON,
	JS_TUYA_STATE_OFF,
	JS_TUYA_STATE_UNKNOWN
} from '../config.js';
import {
	debounce,
	parseToFloatOrNull,
	formatNum,
	sanitizeString,
	isValidNumber
} from '../utils.js';

// --- Module-level State ---
const domElements = {};
const animators = [];
let animationFrameId = null;

/** Colors for different fault/status levels. */
const faultColors = {
	good: '#2ecc71',
	warning: '#f39c12',
	error: '#e74c3c',
	unknown: '#7f8c8d'
};

/** Configuration for the battery charge/discharge bubble animation. */
const BUBBLE_CONFIG = {
	maxBubbles: 15,
	spawnInterval: 250,
	minRadius: 0.4,
	maxRadius: 3.8,
	minSpeedY: 0.15,
	maxSpeedY: 0.5,
	batteryFillVisualX: 5,
	batteryFillVisualWidth: 30,
	batteryCaseVisualTopY: 5,
	batteryCaseVisualHeight: 92
};
BUBBLE_CONFIG.batteryCaseVisualBottomY = BUBBLE_CONFIG.batteryCaseVisualTopY + BUBBLE_CONFIG.batteryCaseVisualHeight;
let activeBatteryBubbles = [],
	lastBubbleSpawnTime = 0;

/** Default maximum power values for calculating animation speeds. These can be updated from system config. */
let MAX_POWER_PV_TOTAL_STATIC = 16000;
let MAX_POWER_PV_STRING = 4000;
const MAX_POWER_GRID = 15000;
const MAX_POWER_BATTERY = 7000;
let MAX_POWER_LOAD = 16000;

/**
 * Queries the DOM and caches references to all elements that will be manipulated
 * for the flow board. This is done once on initialization for performance.
 */
function cacheDOMElements() {
	const s = document.querySelector('.energy-flow-board');
	if (!s) {
		console.error("FlowBoard: Main board .energy-flow-board not found!");
		return;
	}
	const d = domElements;

	for (let i = 1; i <= 4; i++) {
		d[`pv${i}_container`] = s.querySelector(`.pv${i}-container`);
		if (d[`pv${i}_container`]) {
			d[`pv${i}_name`] = d[`pv${i}_container`].querySelector(`.pv${i}-name-text`);
			d[`pv${i}_w`] = d[`pv${i}_container`].querySelector(`.pv${i}-watts-text`);
			d[`pv${i}_v`] = d[`pv${i}_container`].querySelector(`.pv${i}-volts-text`);
			d[`pv${i}_a`] = d[`pv${i}_container`].querySelector(`.pv${i}-amps-text`);
		}
		d[`pv${i}_line`] = s.querySelector(`.pv${i}-to-pvtotal-line`);
	}

	d.pvTotalContainer = s.querySelector('.pv-total-container');
	if (d.pvTotalContainer) {
		d.pvTotalIconSvg = d.pvTotalContainer.querySelector('.pv-total-icon svg');
		d.pvTotalWatts = s.querySelector('.pv-total-watts-text');
		d.pvTotalPercent = s.querySelector('.pv-total-percent-text');
		d.pvTotalKwh = s.querySelector('.pv-total-kwh-text');
	}
	d.pvTotalToInverterLine = s.querySelector('.pvtotal-to-inverter-line');
	d.pvCells = Array.from(s.querySelectorAll('.pv-cell-glow-overlay'));
	d.gridPowerContainer = s.querySelector('.grid-power-container');
	if (d.gridPowerContainer) {
		d.gridPowerText = s.querySelector('.grid-power-text');
		d.gridPowerBorder = s.querySelector('.grid-power-border');
	}
	const gC = s.querySelector('.grid-container');
	if (gC) {
		d.gridKwhUp = s.querySelector('#grid-kwh-up-value');
		d.gridKwhDown = s.querySelector('#grid-kwh-down-value');
		d.noGridText = s.querySelector('#no-grid-text');
		d.gridIconSvg = gC.querySelector('.grid-icon svg');
	}
	d.gridToInverterLineContainer = s.querySelector('.grid-to-inverter-line');
	d.gridToInverterLineContainer2 = s.querySelector('.grid-to-inverter-line2');
	d.gridFlowIndicator = s.querySelector('#flowBoard_grid-flow-indicator');
	d.gridFlowIndicator2 = s.querySelector('#flowBoard_grid-flow-indicator2');
	const invC = s.querySelector('.inverter-container');
	if (invC) {
		d.inverterBrandText = invC.querySelector('#flowBoard_inverter-brand-text');
		d.inverterTemp = invC.querySelector('.inverter-temp-text');
		d.inverterVolts = invC.querySelector('.inverter-volts-text');
		d.inverterAmps = invC.querySelector('.inverter-amps-text');
		d.inverterHz = invC.querySelector('.inverter-hz-text');
		d.faultLight1 = invC.querySelector('.inverter-fault-1');
		d.faultLight2 = invC.querySelector('.inverter-fault-2');
		d.faultLight3 = invC.querySelector('.inverter-fault-3');
		d.faultLight4 = invC.querySelector('.inverter-fault-4');
		d.inverterFanIconDiv = invC.querySelector('.inverter-fan-icon');
		d.inverterFanWrapper = invC.querySelector('#flowBoard_inverterFanWrapper');
		d.inverterFanSvg = invC.querySelector('.inverter-fan-icon svg');
	}
	d.batteryPowerContainer = s.querySelector('.battery-power-container');
	if (d.batteryPowerContainer) {
		d.batteryPowerText = s.querySelector('.battery-power-text');
		d.batteryPowerBorder = s.querySelector('.battery-power-border');
	}
	d.batteryToInverterLineContainer = s.querySelector('.battery-to-inverter-line');
	d.batteryToInverterLineContainer2 = s.querySelector('.battery-to-inverter-line2');
	const battC = s.querySelector('.battery-container');
	if (battC) {
		d.batterySocPercentText = battC.querySelector('#flowBoard_battery-soc-percent .value-text');
		d.batteryKwhUp = battC.querySelector('.battery-kwh-up-text');
		d.batteryKwhDown = battC.querySelector('.battery-kwh-down-text');
		d.batteryVolts = battC.querySelector('.battery-volts-text');
		d.batteryAmps = battC.querySelector('.battery-amps-text');
		d.batteryStatus = battC.querySelector('.battery-status-text');
		d.batteryRuntimeText = battC.querySelector('#flowBoard_battery-runtime .value-text');
		d.batteryFillLevel = battC.querySelector('#flowBoard_battery-fill-level');
		d.bmsPluginStatusLight = battC.querySelector('.bms-plugin-fault-indicator');
	}
	d.loadPowerContainer = s.querySelector('.load-power-container');
	if (d.loadPowerContainer) d.loadPowerText = s.querySelector('.load-power-text');
	const loadC = s.querySelector('.load-container');
	if (loadC) {
		d.loadTotalText = loadC.querySelector('.load-total-text .value-text');
		['Solar', 'Battery', 'Grid'].forEach(t => {
			const tl = t.toLowerCase();
			const prodCol = s.querySelector(`#flowBoard_prod-to-${tl}-col`);
			if (prodCol) {
				d[`prodTo${t}Kwh`] = prodCol.querySelector('.production-power');
				d[`prodTo${t}Perc`] = prodCol.querySelector('.production-percentage');
			}
			const sourceCol = s.querySelector(`#flowBoard_load-from-${tl}-col`);
			if (sourceCol) {
				d[`loadFrom${t}Kwh`] = sourceCol.querySelector('.source-power');
				d[`loadFrom${t}Perc`] = sourceCol.querySelector('.source-percentage');
			}
		});
	}
	d.pvFlowIndicator = s.querySelector('#flowBoard_pv-flow-indicator');
	d.batteryFlowIndicator = s.querySelector('#flowBoard_battery-flow-indicator');
	d.batteryFlowIndicator2 = s.querySelector('#flowBoard_battery-flow-indicator2');
	d.loadFlowIndicator = s.querySelector('#flowBoard_load-flow-indicator');
	d.pv1FlowIndicator = s.querySelector('#flowBoard_pv1-to-total-flow-indicator');
	d.pv2FlowIndicator = s.querySelector('#flowBoard_pv2-to-total-flow-indicator');
	d.pv3FlowIndicator = s.querySelector('#flowBoard_pv3-to-total-flow-indicator');
	d.pv4FlowIndicator = s.querySelector('#flowBoard_pv4-to-total-flow-indicator');
	const bIconSvg = battC ? battC.querySelector('.battery-icon svg') : null;
	if (bIconSvg) {
		d.batteryClipRect = bIconSvg.querySelector('#flowBoard_batteryClipRect');
		d.batteryBubblesGroup = bIconSvg.querySelector('#flowBoard_batteryBubblesGroup');
	}
}

/**
 * Initializes all the flow line animators by mapping SVG path IDs to their
 * corresponding indicator elements and default animation directions.
 */
function setupAllAnimators() {
	const animMap = {
		'flowBoard_pv-to-inverter-path': { indicatorId: 'flowBoard_pv-flow-indicator', direction: 'forward' },
		'flowBoard_grid-to-inverter-path': { indicatorId: 'flowBoard_grid-flow-indicator', direction: 'backward' },
		'flowBoard_grid-to-inverter-path2': { indicatorId: 'flowBoard_grid-flow-indicator2', direction: 'backward' },
		'flowBoard_battery-to-inverter-path': { indicatorId: 'flowBoard_battery-flow-indicator', direction: 'backward' },
		'flowBoard_battery-to-inverter-path2': { indicatorId: 'flowBoard_battery-flow-indicator2', direction: 'backward' },
		'flowBoard_inverter-to-load-path': { indicatorId: 'flowBoard_load-flow-indicator', direction: 'forward' },
		'flowBoard_pv1-to-pvtotal-path': { indicatorId: 'flowBoard_pv1-to-total-flow-indicator', direction: 'forward' },
		'flowBoard_pv2-to-pvtotal-path': { indicatorId: 'flowBoard_pv2-to-total-flow-indicator', direction: 'forward' },
		'flowBoard_pv3-to-pvtotal-path': { indicatorId: 'flowBoard_pv3-to-total-flow-indicator', direction: 'forward' },
		'flowBoard_pv4-to-pvtotal-path': { indicatorId: 'flowBoard_pv4-to-total-flow-indicator', direction: 'forward' }
	};

	Object.entries(animMap).forEach(([pathId, config]) => {
		setupAnimator(pathId, config.indicatorId, config.direction);
	});
}

/**
 * Safely updates the text content of a DOM element with a formatted number or string.
 * @param {HTMLElement} element - The DOM element to update.
 * @param {*} value - The value to display.
 * @param {string} [unit=''] - The unit to append to the value.
 * @param {number} [precision=1] - The number of decimal places for numeric values.
 * @param {string} [fallback='N/A'] - The text to display if the value is invalid.
 */
function updateElementText(element, value, unit = '', precision = 1, fallback = 'N/A') {
	if (!element) return;
	let textContent = fallback;
	if (value !== null && value !== undefined) {
		const num = parseToFloatOrNull(value);
		if (isValidNumber(num)) {
			textContent = formatNum(num, precision);
			if (unit) textContent += ` ${unit}`;
		} else {
			textContent = sanitizeString(value, fallback);
		}
	}
	
	// Force DOM update to prevent stale values
	if (element.textContent !== textContent) {
		element.textContent = textContent;
	}
}

/**
 * Enhanced version of updateElementText with validation and return status.
 * @param {HTMLElement} element - The DOM element to update.
 * @param {*} value - The value to display.
 * @param {string} [unit=''] - The unit to append to the value.
 * @param {number} [precision=1] - The number of decimal places for numeric values.
 * @param {string} [fallback='N/A'] - The text to display if the value is invalid.
 * @returns {boolean} True if update was successful, false otherwise.
 */
function updateElementTextWithValidation(element, value, unit = '', precision = 1, fallback = 'N/A') {
	if (!element) return false;
	
	const originalText = element.textContent;
	updateElementText(element, value, unit, precision, fallback);
	
	// Verify the update actually took place
	const expectedText = (() => {
		if (value !== null && value !== undefined) {
			const num = parseToFloatOrNull(value);
			if (isValidNumber(num)) {
				let text = formatNum(num, precision);
				if (unit) text += ` ${unit}`;
				return text;
			}
		}
		return fallback;
	})();
	
	const updateSuccessful = element.textContent === expectedText;
	if (!updateSuccessful) {
		console.warn(`[UPDATE VALIDATION FAILED] Expected: "${expectedText}", Got: "${element.textContent}"`);
	}
	
	return updateSuccessful;
}

/**
 * Sets up a single animator instance for a given SVG path.
 * @param {string} pathId - The ID of the SVG <path> element.
 * @param {string} indicatorId - The ID of the corresponding flow indicator <div>.
 * @param {string} [defaultDirection='forward'] - The default animation direction.
 */
function setupAnimator(pathId, indicatorId, defaultDirection = 'forward') {
	const sizer = document.querySelector('.energy-flow-board');
	if (!sizer) return;
	const pathElement = sizer.querySelector(`#${pathId}`);
	const indicatorElement = sizer.querySelector(`#${indicatorId}`);
	if (!pathElement || !indicatorElement) { return; }
	const svgContainer = pathElement.closest('.flow-line-container');
	if (!svgContainer) { return; }
	let totalLength = 0;
	try { totalLength = pathElement.getTotalLength(); } catch (e) { return; }
	animators.push({ id: indicatorId, path: pathElement, indicator: indicatorElement, svgContainer: svgContainer, totalLength: totalLength, currentDistance: 0, direction: defaultDirection, isVisible: false, speedMultiplier: 1 });
}

/**
 * The main animation loop, driven by requestAnimationFrame.
 * It updates the position of all visible flow indicators along their SVG paths
 * and triggers the battery bubble animation.
 * @param {function(): object} getState - A function that returns the current clientState.
 */
function animateFlow(getState) {
	const clientState = getState();
	if (!clientState || Object.keys(clientState).length === 0) {
		requestAnimationFrame(() => animateFlow(getState));
		return;
	}

	const socForBubbles = clientState[SDK.BATTERY_STATE_OF_CHARGE_PERCENT] ?? 0;
	if (socForBubbles > 0 && domElements.batteryBubblesGroup) {
		animateBatteryBubbles(clientState);
	} else if (activeBatteryBubbles.length > 0) {
		activeBatteryBubbles.forEach(b => b.element.remove());
		activeBatteryBubbles = [];
	}

	animators.forEach(a => {
		if (!a.indicator || !a.isVisible || a.totalLength === 0) {
			if (a.indicator?.classList.contains('visible')) a.indicator.classList.remove('visible');
			return;
		}
		if (!a.indicator.classList.contains('visible')) a.indicator.classList.add('visible');
		const speed = 1.5 * a.speedMultiplier;
		a.currentDistance += (a.direction === 'forward' ? speed : -speed);
		if (a.currentDistance >= a.totalLength) { a.currentDistance = 0; }
		if (a.currentDistance < 0) { a.currentDistance = a.totalLength; }
		try { const pt = a.path.getPointAtLength(a.currentDistance); a.indicator.style.left = (a.svgContainer.offsetLeft + pt.x - a.indicator.offsetWidth / 2) + 'px'; a.indicator.style.top = (a.svgContainer.offsetTop + pt.y - a.indicator.offsetHeight / 2) + 'px'; } catch (e) { }
	});

	animationFrameId = requestAnimationFrame(() => animateFlow(getState));
}

/**
 * Calculates a speed multiplier for animations based on power level.
 * @param {number} power - The current power in Watts.
 * @param {number} maxPwr - The maximum expected power for this flow.
 * @returns {number} A multiplier for the animation speed.
 */
function calculateSpeedMultiplier(power, maxPwr) {
	if (maxPwr <= 0 || power <= 0) return 0.5;
	const ratio = Math.abs(power) / maxPwr;
	return Math.max(0.5, Math.min(0.5 + (2.5 * ratio), 3.0));
}

/**
 * Creates a new bubble element for the battery animation if conditions are met
 * (e.g., not exceeding max bubbles, respecting spawn interval).
 */
function createBatteryBubble() {
	if (!domElements.batteryBubblesGroup || activeBatteryBubbles.length >= BUBBLE_CONFIG.maxBubbles || !domElements.batteryFillLevel) return;
	const now = performance.now();
	if (now - lastBubbleSpawnTime < BUBBLE_CONFIG.spawnInterval) return;
	const currentFillHeight = parseFloat(domElements.batteryFillLevel.getAttribute('height'));
	if (currentFillHeight <= BUBBLE_CONFIG.minRadius * 2) return;
	lastBubbleSpawnTime = now;
	const bubble = document.createElementNS("http://www.w3.org/2000/svg", "circle");
	const radius = BUBBLE_CONFIG.minRadius + Math.random() * (BUBBLE_CONFIG.maxRadius - BUBBLE_CONFIG.minRadius);
	const cx = BUBBLE_CONFIG.batteryFillVisualX + radius + Math.random() * (BUBBLE_CONFIG.batteryFillVisualWidth - 2 * radius);
	const liquidBottomY = parseFloat(domElements.batteryFillLevel.getAttribute('y')) + currentFillHeight;
	const cy = liquidBottomY - radius - 1;
	bubble.setAttribute('cx', cx.toFixed(2));
	bubble.setAttribute('cy', cy.toFixed(2));
	bubble.setAttribute('r', radius.toFixed(2));
	bubble.setAttribute('class', 'battery-bubble');
	bubble.setAttribute('fill-opacity', (0.3 + Math.random() * 0.4).toFixed(2));
	domElements.batteryBubblesGroup.appendChild(bubble);
	activeBatteryBubbles.push({ element: bubble, speedY: BUBBLE_CONFIG.minSpeedY + Math.random() * (BUBBLE_CONFIG.maxSpeedY - BUBBLE_CONFIG.minSpeedY), radius: radius });
}

/**
 * Animates the movement of active battery bubbles, creating new ones if charging,
 * and removing them as they reach the top of the liquid.
 * @param {object} clientState - The current application state.
 */
function animateBatteryBubbles(clientState) {
	if (!domElements.batteryFillLevel || !domElements.batteryBubblesGroup) return;
	const liquidTopY = parseFloat(domElements.batteryFillLevel.getAttribute('y'));
	activeBatteryBubbles = activeBatteryBubbles.filter(b => {
		let currentCy = parseFloat(b.element.getAttribute('cy'));
		currentCy -= b.speedY;
		b.element.setAttribute('cy', currentCy.toFixed(2));
		if (currentCy + b.radius < liquidTopY) { b.element.remove(); return false; }
		return true;
	});
	if ((clientState[SDK.BATTERY_STATE_OF_CHARGE_PERCENT] ?? 0) > 0) { createBatteryBubble(); }
}

/**
 * Initializes the flow board module.
 * Caches DOM elements, sets up animators, and observes the container for resizing.
 * @param {Function} debounceFn - A reference to the debounce utility function.
 */
export function initializeFlowBoard(debounceFn) {
	cacheDOMElements();
	setupAllAnimators();
	const resizeObserver = new ResizeObserver(debounceFn(resizeFlowBoard, 150));
	const flowContainer = document.querySelector('.energy-flow-diagram-container');
	if (flowContainer) resizeObserver.observe(flowContainer);
	setTimeout(resizeFlowBoard, 250);
}

/**
 * Starts the main animation loop if it's not already running.
 * @param {function(): object} stateProvider - A function that provides the latest client state to the animation loop.
 */
export function startAnimationLoop(stateProvider) {
	if (!animationFrameId) { animateFlow(stateProvider); }
}

/**
 * Handles resizing of the flow board container by applying a CSS scale transform
 * to the main board element, ensuring it fits within its container.
 */
export function resizeFlowBoard() {
	const s = document.querySelector('.energy-flow-board'),
		c = document.querySelector('.energy-flow-diagram-container');
	if (!s || !c) return;
	const containerRect = c.getBoundingClientRect();
	if (containerRect.width > 1 && containerRect.height > 1) {
		let scaleFactor = Math.min(containerRect.width / 1513, containerRect.height / 1080);
		if (scaleFactor < 0.01) scaleFactor = 0.01;
		s.style.transform = `scale(${scaleFactor})`;
		if (!s.style.opacity || s.style.opacity === '0') s.style.opacity = '1';
	}
}

/**
 * The main rendering function for the flow board.
 * It takes the processed data object and updates all relevant DOM elements and animator states.
 * @param {object} flowBoardData - The structured data object for the flow board.
 */
export function updateFlowBoard(flowBoardData) {
	if (!flowBoardData || Object.keys(domElements).length === 0) return;
	const d = flowBoardData;
	const el = domElements;

	d.pv.forEach((pvItem, index) => {
		const i = index + 1;
		if (el[`pv${i}_container`]) {
			const isActive = (parseToFloatOrNull(pvItem.w) ?? 0) > FLOW_THRESHOLD_W;
			el[`pv${i}_container`].style.display = pvItem.is_configured ? 'block' : 'none';
			if (el[`pv${i}_line`]) el[`pv${i}_line`].style.display = pvItem.is_configured ? 'block' : 'none';
			el[`pv${i}_container`].classList.toggle('dim', !isActive);
			if (el[`pv${i}_line`]) el[`pv${i}_line`].classList.toggle('dim', !isActive);
			updateElementText(el[`pv${i}_w`], pvItem.w, "W", 0);
			updateElementText(el[`pv${i}_v`], pvItem.v, "V", 1);
			updateElementText(el[`pv${i}_a`], pvItem.a, "A", 1);
		}
	});

	if (d.pvTotal) {
		const isPvDim = (d.pvTotal.w ?? 0) < FLOW_THRESHOLD_W;
		if (el.pvTotalContainer) el.pvTotalContainer.classList.toggle('dim', isPvDim);
		if (el.pvTotalToInverterLine) el.pvTotalToInverterLine.classList.toggle('dim', isPvDim);
		updateElementText(el.pvTotalWatts, d.pvTotal.w, "W", 0);
		updateElementText(el.pvTotalPercent, d.pvTotal.percent, "%", 1);
		updateElementText(el.pvTotalKwh, d.pvTotal.kwh, "kWh", 1);

		if (el.pvTotalIconSvg) {
			const sunAnimationGroup = el.pvTotalIconSvg.querySelector('g#pv-icon-sun-animating-group');
			if (sunAnimationGroup) {
				try {
					if (isPvDim) {
						if (typeof sunAnimationGroup.pauseAnimations === 'function') {
							sunAnimationGroup.pauseAnimations();
						}
					} else {
						if (typeof sunAnimationGroup.unpauseAnimations === 'function') {
							sunAnimationGroup.unpauseAnimations();
						}
					}
				} catch (e) { }
			}

			// Normalize percentage and check if active
			const percentNormalized = Math.min(1, Math.max(0, (d.pvTotal.percent || 0) / 100));
			const isActive = !isPvDim && percentNormalized > 0;
			let fillOpacityToApply = '0'; let filterToApply = 'none';

			if (isActive) {
				// --- PV Cell Glow Effect Calculation ---
				// Base opacity starts low and increases with power percentage.
				const baseFillOpacity = 0.1; const maxAdditionalFillOpacity = 0.8;
				// Blur and shadow spread are calculated based on a power curve (pow(0.65))
				// to make the glow effect more pronounced at lower power levels and less overwhelming at max.
				const maxBlurRadius = 6; const maxShadowSpread = 1;
				const maxShadowOpacity = 0.5; const glowColorRGB = "255, 255, 100";
				const currentCalculatedFillOpacity = baseFillOpacity + (maxAdditionalFillOpacity * percentNormalized);
				const glowIntensityFactor = Math.pow(percentNormalized, 0.65);
				const currentCalculatedBlurRadius = Math.max(1, Math.round(maxBlurRadius * glowIntensityFactor));
				const currentCalculatedShadowSpread = Math.round(maxShadowSpread * glowIntensityFactor);
				const currentCalculatedShadowOpacity = Math.max(0.1, parseFloat((maxShadowOpacity * glowIntensityFactor).toFixed(2)));

				fillOpacityToApply = String(currentCalculatedFillOpacity.toFixed(2));
				filterToApply = `drop-shadow(0 0 ${currentCalculatedBlurRadius}px rgba(${glowColorRGB}, ${currentCalculatedShadowOpacity}))`;
			}

			el.pvCells.forEach(cellElement => {
				if (cellElement) { cellElement.style.opacity = fillOpacityToApply; cellElement.style.filter = filterToApply; }
			});
		}
	}

	if (d.grid) {
		const p = d.grid.w ?? 0;
		const isExporting = p > FLOW_THRESHOLD_W;
		if (el.gridPowerBorder) el.gridPowerBorder.classList.toggle('exporting', isExporting);
		if (el.gridPowerText) el.gridPowerText.classList.toggle('exporting', isExporting);
		updateElementText(el.gridPowerText, Math.abs(p), "W", 0);
		updateElementText(el.gridKwhUp, "↑" + formatNum(d.grid.kwhUp, 2), "kWh");
		updateElementText(el.gridKwhDown, "↓" + formatNum(d.grid.kwhDown, 2), "kWh");
		if (el.noGridText) el.noGridText.classList.toggle('visible', d.grid.noGrid === true);
		if (el.gridIconSvg) el.gridIconSvg.style.opacity = d.grid.noGrid ? 0.3 : 1;
	}

	if (d.inverter) {
		updateElementText(el.inverterBrandText, d.inverter.brand, "", 1, "Inverter");
		updateElementText(el.inverterTemp, d.inverter.temp, "°C", 1);
		updateElementText(el.inverterVolts, d.inverter.volts, " V", 1);
		updateElementText(el.inverterAmps, d.inverter.amps, " A", 1);
		updateElementText(el.inverterHz, d.inverter.hz, " Hz", 1);

		// Handle "No Grid" status display with duration tracking
		const inverterStatus = (d.inverter.statusText || "").toLowerCase().trim();
		const isNoGrid = inverterStatus.includes('no grid');

		// Track "No Grid" duration
		const noGridStartKey = 'noGridStartTime';
		let noGridDuration = '';

		if (isNoGrid) {
			// Check if we already have a start time stored
			let startTime = localStorage.getItem(noGridStartKey);
			if (!startTime) {
				// First time detecting "No Grid", store the current timestamp
				startTime = Date.now();
				localStorage.setItem(noGridStartKey, startTime);
			}

			// Calculate duration
			const now = Date.now();
			const diffMs = Math.max(0, now - parseInt(startTime));
			const totalMinutes = Math.floor(diffMs / (1000 * 60));
			const hours = Math.floor(totalMinutes / 60);
			const minutes = totalMinutes % 60;

			// Format duration string
			let durationStr = '';
			if (hours > 0) {
				durationStr += hours + ' hr' + (hours > 1 ? 's' : '');
				if (minutes > 0) {
					durationStr += ', ';
				}
			}
			if (minutes > 0 || hours === 0) {
				durationStr += minutes + ' min' + (minutes > 1 ? 's' : '');
			}
			if (durationStr === '') {
				durationStr = '< 1 min';
			}

			noGridDuration = durationStr;

			// Set red opaque background and white text for "No Grid"
			if (el.gridPowerBorder) {
				el.gridPowerBorder.style.backgroundColor = 'red';
				el.gridPowerBorder.style.opacity = '1';
			}
			if (el.gridPowerText) {
				el.gridPowerText.style.color = 'white';
				// Determine theme-appropriate color for duration text
				const isDarkTheme = document.body.classList.contains('dark');
				const durationColor = isDarkTheme ? 'rgba(255, 255, 255, 0.8)' : 'rgba(0, 0, 0, 0.8)';
				el.gridPowerText.innerHTML = `No Grid<span style="display: block; font-size: 0.4em; color: ${durationColor}; line-height: 0.8; margin-top: 2px;">Duration: ${noGridDuration}</span>`;
			}
			// Add blinking animation to grid-power-container
			if (el.gridPowerContainer) {
				el.gridPowerContainer.style.animation = 'blink 5s ease infinite';
			}
		} else {
			// Grid is back, clear the stored start time
			localStorage.removeItem(noGridStartKey);

			// Reset to original settings
			if (el.gridPowerBorder) {
				el.gridPowerBorder.style.backgroundColor = '';
				el.gridPowerBorder.style.opacity = '';
			}
			if (el.gridPowerText) {
				el.gridPowerText.style.color = '';
				// Reset to original content (will be updated by normal grid logic)
			}
			// Remove blinking animation
			if (el.gridPowerContainer) {
				el.gridPowerContainer.style.animation = '';
			}
		}
		const fanStat = d.inverter.tuyaStatus;
		const isFanOn = fanStat === JS_TUYA_STATE_ON;
		if (el.inverterFanIconDiv) { el.inverterFanIconDiv.classList.toggle('dimmed', !isFanOn); }
		try {
			if (el.inverterFanSvg && typeof el.inverterFanSvg.animationsPaused === 'function') {
				isFanOn ? el.inverterFanSvg.unpauseAnimations() : el.inverterFanSvg.pauseAnimations();
			}
		} catch (e) { }
		if (el.inverterFanWrapper) { el.inverterFanWrapper.title = `FAN: ${fanStat || 'N/A'}`; }

		const faultLights = [el.faultLight1, el.faultLight2, el.faultLight3, el.faultLight4];
		const invStatusText = (d.inverter.statusText || "").toLowerCase().trim();
		let invColor = faultColors.unknown; let invTitle = `Inverter Status: ${d.inverter.statusText || 'Unknown'}`;
		if (['generating', 'ok', 'normal', 'running'].some(kw => invStatusText.includes(kw))) {
			invColor = faultColors.good;
		} else if (['fault', 'error', 'alarm', 'failed'].some(kw => invStatusText.includes(kw))) {
			invColor = faultColors.error;
		} else if (['standby', 'waiting', 'idle', 'power limiting'].some(kw => invStatusText.includes(kw))) {
			invColor = faultColors.warning;
		} else if (invStatusText && invStatusText !== 'unknown' && invStatusText !== 'init') { invColor = faultColors.warning; }

		if (faultLights[0]) { faultLights[0].style.backgroundColor = invColor; faultLights[0].title = invTitle; }

		["bms", "eps"].forEach((catKey, i) => {
			const light = faultLights[i + 1];
			if (!light) return;
			let color = faultColors.unknown; let title = `${catKey.toUpperCase()}: Status Unknown`;
			const alerts = d.inverter.categorizedAlerts ? d.inverter.categorizedAlerts[catKey] : undefined;
			if (alerts !== undefined && Array.isArray(alerts)) {
				if (alerts.length === 0 || (alerts.length === 1 && alerts[0].toLowerCase() === 'ok')) {
					color = faultColors.good; title = `${catKey.toUpperCase()}: No active alerts`;
				} else {
					title = `${catKey.toUpperCase()} Alerts: ${alerts.join(', ')}`;
					if (['charging', 'discharging', 'idle', 'normal'].some(x => title.toLowerCase().includes(x) && alerts.length === 1)) {
						color = faultColors.good;
					} else { color = faultColors.error; }
				}
			} else {
				if (catKey === 'eps' && d.inverter.categorizedAlerts) {
					color = faultColors.good; title = 'EPS: No active alerts';
				} else { title = `${catKey.toUpperCase()}: Category data N/A`; }
			}
			light.style.backgroundColor = color; light.title = title;
		});

		if (faultLights[3] && d.inverter.hasOwnProperty('pluginConnectionStatus')) {
			const plugStat = String(d.inverter.pluginConnectionStatus).toLowerCase();
			let col = faultColors.unknown; let title = `Inverter Plugin: ${d.inverter.pluginConnectionStatus || 'Unknown'}`;
			if (plugStat === "connected") col = faultColors.good;
			else if (plugStat === "disconnected" || plugStat === "error") col = faultColors.error;
			else if (plugStat.includes("connecting") || plugStat.includes("initializing")) col = faultColors.warning;
			faultLights[3].style.backgroundColor = col; faultLights[3].title = title;
		} else if (faultLights[3]) {
			faultLights[3].style.backgroundColor = faultColors.unknown; faultLights[3].title = "Inverter Plugin: Status N/A";
		}
	}

	if (d.battery) {
		const p = parseFloat(d.battery.power) ?? 0;
		const soc = parseFloat(d.battery.soc) ?? 0;
		

		
		const isChg = p < -FLOW_THRESHOLD_W;
		if (el.batteryPowerBorder) el.batteryPowerBorder.classList.toggle('charging', isChg);
		if (el.batteryPowerText) el.batteryPowerText.classList.toggle('charging', isChg);
		updateElementText(el.batteryPowerText, Math.abs(p), "W", 0);
		
		// Enhanced SOC update with validation and forced refresh
		console.log(`[SOC DEBUG] Updating SOC display: ${soc}%`);
		
		// Force update the SOC display
		if (el.batterySocPercentText && soc !== null && !isNaN(soc)) {
			const newSocText = `${soc.toFixed(0)}%`;
			const currentText = el.batterySocPercentText.textContent;
			
			if (currentText !== newSocText) {
				console.log(`[SOC UPDATE] Changing SOC from "${currentText}" to "${newSocText}"`);
				el.batterySocPercentText.textContent = newSocText;
				
				// Force DOM refresh
				el.batterySocPercentText.style.display = 'none';
				el.batterySocPercentText.offsetHeight; // Trigger reflow
				el.batterySocPercentText.style.display = '';
			}
		} else {
			console.warn(`[SOC UPDATE FAILED] Invalid SOC value or missing element: ${soc}`);
		}
		
		updateElementText(el.batteryVolts, d.battery.volts, "V", 1);
		updateElementText(el.batteryAmps, d.battery.amps, "A", 1);

		// Determine battery direction based on power instead of complex status text
		let batteryDirection = "Idle";
		if (typeof p === 'number') {
			if (p > 10) {
				batteryDirection = "Discharging";
			} else if (p < -10) {
				batteryDirection = "Charging";
			} else if (Math.abs(p) <= 10) {
				batteryDirection = "Floating";
			}
		}
		updateElementText(el.batteryStatus, batteryDirection, "", 0, "Idle");
		updateElementText(el.batteryRuntimeText, d.battery.runtimeTextDisplay, "", 0, "N/A");

		if (el.batteryKwhUp) el.batteryKwhUp.textContent = `↑${formatNum(d.battery.kwhUp, 2)} kWh`;
		if (el.batteryKwhDown) el.batteryKwhDown.textContent = `↓${formatNum(d.battery.kwhDown, 2)} kWh`;

		let shouldHideBMSLight = false;
		if (el.bmsPluginStatusLight && d.battery.hasOwnProperty('bmsPluginConnectionStatus')) {
			const bmsPlugStat = String(d.battery.bmsPluginConnectionStatus).toLowerCase();
			let col = faultColors.unknown; let title = `BMS Plugin: ${d.battery.bmsPluginConnectionStatus || 'Unknown'}`;
			const noBMSKeywords = ['unknown', 'not_loaded', 'disabled', 'not_applicable', 'not_configured', 'undefined', null];
			if (noBMSKeywords.some(kw => bmsPlugStat.includes(kw) || d.battery.bmsPluginConnectionStatus === null)) {
				shouldHideBMSLight = true;
			} else if (["connected", "ok", "active"].includes(bmsPlugStat)) {
				col = faultColors.good;
			} else if (["disconnected", "error", "fault"].includes(bmsPlugStat)) {
				col = faultColors.error;
			} else if (bmsPlugStat.includes("connecting") || bmsPlugStat.includes("initializing") || bmsPlugStat.includes("warning")) { col = faultColors.warning; }

			el.bmsPluginStatusLight.style.display = shouldHideBMSLight ? 'none' : 'block';
			el.bmsPluginStatusLight.style.backgroundColor = col;
			el.bmsPluginStatusLight.title = title;
		} else if (el.bmsPluginStatusLight) {
			el.bmsPluginStatusLight.style.display = 'none'; el.bmsPluginStatusLight.title = "BMS Plugin: Status data N/A";
		}

		if (el.batteryFillLevel && el.batteryClipRect) {
			const fillHeight = (BUBBLE_CONFIG.batteryCaseVisualHeight * soc) / 100;
			const yPos = BUBBLE_CONFIG.batteryCaseVisualBottomY - fillHeight;
			el.batteryFillLevel.setAttribute('height', fillHeight.toFixed(2));
			el.batteryFillLevel.setAttribute('y', yPos.toFixed(2));
			el.batteryClipRect.setAttribute('height', fillHeight.toFixed(2));
			el.batteryClipRect.setAttribute('y', yPos.toFixed(2));
		}
	}

	if (d.load && d.production) {
		updateElementText(el.loadPowerText, d.load.currentW, "W", 0);
		updateElementText(el.loadTotalText, d.load.totalEnergyConsumedToday, "kWh", 1);
		updateElementText(el.loadFromSolarKwh, `(${formatNum(d.load.energy_from_solar_kWh, 1)} kWh)`);
		updateElementText(el.loadFromSolarPerc, formatNum(d.load.percent_from_solar, 0), "%");
		updateElementText(el.loadFromBatteryKwh, `(${formatNum(d.load.energy_from_battery_kWh, 1)} kWh)`);
		updateElementText(el.loadFromBatteryPerc, formatNum(d.load.percent_from_battery, 0), "%");
		updateElementText(el.loadFromGridKwh, `(${formatNum(d.load.energy_from_grid_kWh, 1)} kWh)`);
		updateElementText(el.loadFromGridPerc, formatNum(d.load.percent_from_grid, 0), "%");
		updateElementText(el.prodToSolarKwh, `(${formatNum(d.production.to_load_direct_kWh, 1)} kWh)`);
		updateElementText(el.prodToSolarPerc, formatNum(d.production.percent_to_load_direct, 0), "%");
		updateElementText(el.prodToBatteryKwh, `(${formatNum(d.production.to_battery_kWh, 1)} kWh)`);
		updateElementText(el.prodToBatteryPerc, formatNum(d.production.percent_to_battery, 0), "%");
		updateElementText(el.prodToGridKwh, `(${formatNum(d.production.to_grid_export_kWh, 1)} kWh)`);
		updateElementText(el.prodToGridPerc, formatNum(d.production.percent_to_grid_export, 0), "%");
	}

	if (d.pvTotal && d.grid && d.battery && d.load && d.pv) {
		animators.forEach(anim => {
			let vis = false, newDir = anim.direction, curPwr = 0, maxPwr = 1;
			const id = anim.id;
			if (id.includes('pv-flow-indicator')) {
				curPwr = d.pvTotal.w; maxPwr = MAX_POWER_PV_TOTAL_STATIC; vis = curPwr > FLOW_THRESHOLD_W; newDir = 'forward';
			} else if (id.includes('grid-flow-indicator')) {
				curPwr = d.grid.w; maxPwr = MAX_POWER_GRID; vis = !d.grid.noGrid && (Math.abs(curPwr) > FLOW_THRESHOLD_W); if (vis) newDir = curPwr > 0 ? 'forward' : 'backward';
			} else if (id.includes('battery-flow-indicator')) {
				curPwr = d.battery.power; maxPwr = MAX_POWER_BATTERY; vis = Math.abs(curPwr) > FLOW_THRESHOLD_W; if (vis) newDir = d.battery.power < 0 ? 'forward' : 'backward';
			} else if (id.includes('load-flow-indicator')) {
				curPwr = d.load.currentW; maxPwr = MAX_POWER_LOAD; vis = curPwr > FLOW_THRESHOLD_W; newDir = 'forward';
			} else {
				for (let i = 1; i <= 4; i++) {
					if (id.includes(`pv${i}-to-total-flow-indicator`)) { curPwr = d.pv[i - 1].w; maxPwr = MAX_POWER_PV_STRING; vis = d.pv[i - 1].is_configured && curPwr > FLOW_THRESHOLD_W; newDir = 'forward'; break; }
				}
			}
			anim.speedMultiplier = vis ? calculateSpeedMultiplier(curPwr, maxPwr) : 0.5;
			if (anim.isVisible !== vis || (vis && anim.direction !== newDir)) {
				anim.isVisible = vis;
				anim.direction = newDir;
				if (anim.indicator) {
					if (!vis) { anim.indicator.classList.remove('visible'); }
					else { anim.currentDistance = (anim.direction === 'forward') ? 0 : anim.totalLength; anim.indicator.classList.add('visible'); }
				}
			}
		});
	}
}