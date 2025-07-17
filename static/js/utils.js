// static/js/utils.js
/**
 * Returns a function, that, as long as it continues to be invoked, will not
 * be triggered. The function will be called after it stops being called for
 * N milliseconds.
 * @param {Function} func The function to debounce.
 * @param {number} wait The number of milliseconds to delay.
 * @returns {Function} The new debounced function.
 */
export function debounce(func, wait) {
	let timeout;
	return function executedFunction(...args) {
		const context = this;
		const later = () => {
			timeout = null;
			func.apply(context, args);
		};
		clearTimeout(timeout);
		timeout = setTimeout(later, wait);
	};
}

/**
 * Gets a color value based on the current theme (light/dark).
 * @param {string} [type='text'] - The type of color to retrieve ('text', 'grid', 'title').
 * @returns {string} The CSS color string.
 */
export function getThemeColor(type = 'text') {
	const isDark = document.body.classList.contains('dark');
	const colors = {
		light: {
			text: '#444',
			grid: 'rgba(0,0,0,0.08)',
			title: '#555'
		},
		dark: {
			text: '#aaa',
			grid: 'rgba(255,255,255,0.12)',
			title: '#bdc3c7'
		}
	};
	return colors[isDark ? 'dark' : 'light'][type] || colors[isDark ? 'dark' : 'light']['text'];
}

/**
 * Checks if a value is a valid, non-NaN number.
 * @param {*} v - The value to check.
 * @returns {boolean} True if the value is a valid number.
 */
export const isValidNumber = v => v !== null && v !== undefined && typeof v === 'number' && !isNaN(v);

/**
 * Parses a value to a float, returning null if it's not a valid number.
 * @param {*} v - The value to parse.
 * @returns {number|null} The parsed float or null.
 */
export const parseToFloatOrNull = v => {
	if (v === null || v === undefined) return null;
	const p = parseFloat(String(v));
	return !isNaN(p) ? p : null;
};

/**
 * Sanitizes a string, returning a fallback if it's null, empty, or a known invalid keyword.
 * @param {*} v - The value to sanitize.
 * @param {string} [fallback='N/A'] - The fallback string to return.
 * @returns {string} The sanitized string or the fallback.
 */
export const sanitizeString = (v, fallback = 'N/A') => {
	if (v === null || v === undefined || String(v).trim() === '' || ['INIT', 'UNKNOWN', 'N/A'].includes(String(v).toUpperCase()) || String(v).toUpperCase().includes('ERROR')) return fallback;
	return String(v);
};

/**
 * Displays the disconnect overlay and popup with a custom message.
 * @param {string} [message="Disconnected..."] - The message to display in the popup.
 */
export function showDisconnectPopup(message = "Disconnected...") {
	const p = document.getElementById('disconnectPopup'),
		m = document.getElementById('disconnectPopupMessage'),
		b = document.body;
	if (!b.classList.contains('popup-active')) {
		if (m) m.textContent = message;
		b.classList.add('popup-active');
	} else if (m && m.textContent !== message) {
		m.textContent = message;
	}
}

/**
 * Hides the disconnect overlay and popup.
 */
export function hideDisconnectPopup() {
	document.body.classList.remove('popup-active');
}

/**
 * Sets a cookie.
 * @param {string} name - The name of the cookie.
 * @param {string} value - The value of the cookie.
 * @param {number} days - The number of days until the cookie expires.
 */
export function setCookie(name, value, days) {
	let expires = "";
	if (days) {
		const date = new Date;
		date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
		expires = "; expires=" + date.toUTCString();
	}
	document.cookie = `${name}=${value||""}${expires}; path=/; SameSite=Lax`;
}

/**
 * Gets a cookie by name.
 * @param {string} name - The name of the cookie to retrieve.
 * @returns {string|null} The cookie value or null if not found.
 */
export function getCookie(name) {
	const nameEQ = name + "=";
	const ca = document.cookie.split(";");
	for (let i = 0; i < ca.length; i++) {
		let c = ca[i];
		while (c.charAt(0) === ' ') {
			c = c.substring(1, c.length);
		}
		if (c.indexOf(nameEQ) === 0) {
			return c.substring(nameEQ.length, c.length);
		}
	}
	return null;
}

/**
 * Formats a number to a fixed precision string.
 * @param {*} value - The value to format.
 * @param {number} [precision=0] - The number of decimal places.
 * @param {string} [fallback='N/A'] - The fallback string if the value is not a number.
 * @returns {string} The formatted number string.
 */
export function formatNum(value, precision = 0, fallback = 'N/A') {
	const num = parseToFloatOrNull(value);
	return num !== null ? num.toFixed(precision) : fallback;
}

/**
 * Displays a toast notification on the screen.
 * @param {string} message - The message to display.
 * @param {string} [type='info'] - The type of toast ('info', 'success', 'warning', 'error').
 * @param {number} [duration=3000] - The duration in milliseconds to show the toast.
 */
export function showToast(message, type = 'info', duration = 3000) {
	const existingToast = document.querySelector('.toast-notification');
	if (existingToast) existingToast.remove();
	const toast = document.createElement('div');
	toast.className = `toast-notification toast-${type}`;
	toast.textContent = message;
	const styles = {
		position: 'fixed',
		bottom: '20px',
		left: '50%',
		transform: 'translateX(-50%)',
		padding: '10px 20px',
		borderRadius: '5px',
		color: 'white',
		zIndex: '10000',
		opacity: '0',
		transition: 'opacity 0.5s ease, bottom 0.5s ease',
		fontSize: 'max(12px, 0.9em)',
		boxShadow: '0 2px 10px rgba(0,0,0,0.2)'
	};
	const typeStyles = {
		info: {
			backgroundColor: '#3498db'
		},
		success: {
			backgroundColor: '#2ecc71'
		},
		warning: {
			backgroundColor: '#f39c12'
		},
		error: {
			backgroundColor: '#e74c3c'
		}
	};
	Object.assign(toast.style, styles, typeStyles[type] || typeStyles.info);
	document.body.appendChild(toast);
	setTimeout(() => {
		toast.style.opacity = '1';
		toast.style.bottom = '40px';
	}, 10);
	setTimeout(() => {
		toast.style.opacity = '0';
		toast.style.bottom = '20px';
		setTimeout(() => toast.remove(), 500);
	}, duration);
}