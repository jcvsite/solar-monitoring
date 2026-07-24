/**
 * Dashboard theme catalog and apply helpers.
 * Each theme has a light/dark mode for charts, weather map, and a BMS color palette.
 */
export const THEMES = [
	{
		id: 'solar',
		label: 'Solar Warm',
		mode: 'light',
		swatch: ['#ffcc33', '#e67e22', '#fffacd'],
		desc: 'Classic sunny orange',
		bms: {
			bgPrimary: '#ffeb99',
			bgSecondary: '#fffacd',
			bgTertiary: 'rgba(211, 84, 0, 0.05)',
			textPrimary: '#d35400',
			textSecondary: '#555555',
			textAccent: '#d35400',
			borderColor: 'rgba(211, 84, 0, 0.2)',
			cellBorder: '#d35400',
			cellDefaultBg: '#fdf5e6',
			iconColor: '#e67e22',
			cellCapBg: '#f1c40f',
			cellCapBorder: '#d35400',
			cellText: '#333',
		},
	},
	{
		id: 'midnight',
		label: 'Midnight',
		mode: 'dark',
		swatch: ['#111', '#3498db', '#2c3e50'],
		desc: 'Dark with blue accents',
		bms: {
			bgPrimary: '#000000',
			bgSecondary: 'rgba(35, 35, 35, 0.9)',
			bgTertiary: 'rgba(52, 152, 219, 0.1)',
			textPrimary: '#ecf0f1',
			textSecondary: '#bdc3c7',
			textAccent: '#3498db',
			borderColor: 'rgba(52, 152, 219, 0.25)',
			cellBorder: '#3498db',
			cellDefaultBg: '#2c3e50',
			iconColor: '#3498db',
			cellCapBg: '#3498db',
			cellCapBorder: '#2980b9',
			cellText: '#ecf0f1',
		},
	},
	{
		id: 'ocean',
		label: 'Ocean',
		mode: 'light',
		swatch: ['#e8f4fc', '#0288d1', '#4fc3f7'],
		desc: 'Cool blues and teal',
		bms: {
			bgPrimary: '#e3f2fd',
			bgSecondary: '#f7fbff',
			bgTertiary: 'rgba(2, 136, 209, 0.06)',
			textPrimary: '#01579b',
			textSecondary: '#455a64',
			textAccent: '#0288d1',
			borderColor: 'rgba(2, 136, 209, 0.25)',
			cellBorder: '#0288d1',
			cellDefaultBg: '#e1f5fe',
			iconColor: '#0288d1',
			cellCapBg: '#4fc3f7',
			cellCapBorder: '#0277bd',
			cellText: '#263238',
		},
	},
	{
		id: 'slate',
		label: 'Slate',
		mode: 'dark',
		swatch: ['#0f1419', '#5c7cfa', '#1e293b'],
		desc: 'Modern dark slate',
		bms: {
			bgPrimary: '#0b1220',
			bgSecondary: 'rgba(22, 30, 46, 0.95)',
			bgTertiary: 'rgba(92, 124, 250, 0.1)',
			textPrimary: '#e8eef8',
			textSecondary: '#a8b3c7',
			textAccent: '#74c0fc',
			borderColor: 'rgba(92, 124, 250, 0.3)',
			cellBorder: '#5c7cfa',
			cellDefaultBg: '#1a2336',
			iconColor: '#74c0fc',
			cellCapBg: '#5c7cfa',
			cellCapBorder: '#4c6ef5',
			cellText: '#e8eef8',
		},
	},
	{
		id: 'forest',
		label: 'Forest',
		mode: 'light',
		swatch: ['#eef6ee', '#2e7d32', '#81c784'],
		desc: 'Soft greens',
		bms: {
			bgPrimary: '#e8f5e9',
			bgSecondary: '#f7fbf7',
			bgTertiary: 'rgba(46, 125, 50, 0.06)',
			textPrimary: '#1b5e20',
			textSecondary: '#546e7a',
			textAccent: '#2e7d32',
			borderColor: 'rgba(46, 125, 50, 0.25)',
			cellBorder: '#2e7d32',
			cellDefaultBg: '#e8f5e9',
			iconColor: '#43a047',
			cellCapBg: '#81c784',
			cellCapBorder: '#2e7d32',
			cellText: '#1b5e20',
		},
	},
	{
		id: 'contrast',
		label: 'High Contrast',
		mode: 'dark',
		swatch: ['#000', '#fff', '#ffe600'],
		desc: 'Max readability',
		bms: {
			bgPrimary: '#000000',
			bgSecondary: '#0a0a0a',
			bgTertiary: 'rgba(255, 230, 0, 0.08)',
			textPrimary: '#ffffff',
			textSecondary: '#eeeeee',
			textAccent: '#ffe600',
			borderColor: 'rgba(255, 230, 0, 0.5)',
			cellBorder: '#ffe600',
			cellDefaultBg: '#111111',
			iconColor: '#ffe600',
			cellCapBg: '#ffe600',
			cellCapBorder: '#ffffff',
			cellText: '#ffffff',
		},
	},
	{
		id: 'ember',
		label: 'Ember',
		mode: 'dark',
		swatch: ['#1a0b0b', '#ff7043', '#3e2723'],
		desc: 'Warm dark coals',
		bms: {
			bgPrimary: '#140a08',
			bgSecondary: 'rgba(40, 20, 16, 0.95)',
			bgTertiary: 'rgba(255, 112, 67, 0.1)',
			textPrimary: '#ffe0d4',
			textSecondary: '#d7ccc8',
			textAccent: '#ff7043',
			borderColor: 'rgba(255, 112, 67, 0.35)',
			cellBorder: '#ff7043',
			cellDefaultBg: '#2a1510',
			iconColor: '#ff8a65',
			cellCapBg: '#ff7043',
			cellCapBorder: '#e64a19',
			cellText: '#ffe0d4',
		},
	},
	{
		id: 'arctic',
		label: 'Arctic',
		mode: 'light',
		swatch: ['#f4f7fb', '#546e7a', '#90a4ae'],
		desc: 'Cool neutral frost',
		bms: {
			bgPrimary: '#eceff1',
			bgSecondary: '#f7f9fb',
			bgTertiary: 'rgba(84, 110, 122, 0.08)',
			textPrimary: '#37474f',
			textSecondary: '#607d8b',
			textAccent: '#455a64',
			borderColor: 'rgba(84, 110, 122, 0.28)',
			cellBorder: '#607d8b',
			cellDefaultBg: '#eceff1',
			iconColor: '#546e7a',
			cellCapBg: '#90a4ae',
			cellCapBorder: '#546e7a',
			cellText: '#263238',
		},
	},
	{
		id: 'sand',
		label: 'Sand',
		mode: 'light',
		swatch: ['#f5efe6', '#8d6e63', '#d7ccc8'],
		desc: 'Soft beige neutrals',
		bms: {
			bgPrimary: '#efebe9',
			bgSecondary: '#faf7f2',
			bgTertiary: 'rgba(141, 110, 99, 0.08)',
			textPrimary: '#5d4037',
			textSecondary: '#6d4c41',
			textAccent: '#8d6e63',
			borderColor: 'rgba(141, 110, 99, 0.3)',
			cellBorder: '#8d6e63',
			cellDefaultBg: '#efebe9',
			iconColor: '#a1887f',
			cellCapBg: '#bcaaa4',
			cellCapBorder: '#8d6e63',
			cellText: '#3e2723',
		},
	},
	{
		id: 'dusk',
		label: 'Dusk',
		mode: 'dark',
		swatch: ['#1a1226', '#ce93d8', '#311b4d'],
		desc: 'Purple evening',
		bms: {
			bgPrimary: '#12081c',
			bgSecondary: 'rgba(35, 20, 50, 0.95)',
			bgTertiary: 'rgba(206, 147, 216, 0.1)',
			textPrimary: '#f3e5f5',
			textSecondary: '#ce93d8',
			textAccent: '#ce93d8',
			borderColor: 'rgba(206, 147, 216, 0.3)',
			cellBorder: '#ba68c8',
			cellDefaultBg: '#2a1638',
			iconColor: '#ce93d8',
			cellCapBg: '#ab47bc',
			cellCapBorder: '#8e24aa',
			cellText: '#f3e5f5',
		},
	},
	{
		id: 'graphite',
		label: 'Graphite',
		mode: 'dark',
		swatch: ['#121212', '#9e9e9e', '#2a2a2a'],
		desc: 'Neutral charcoal',
		bms: {
			bgPrimary: '#101010',
			bgSecondary: 'rgba(30, 30, 30, 0.95)',
			bgTertiary: 'rgba(158, 158, 158, 0.1)',
			textPrimary: '#f5f5f5',
			textSecondary: '#bdbdbd',
			textAccent: '#e0e0e0',
			borderColor: 'rgba(158, 158, 158, 0.35)',
			cellBorder: '#9e9e9e',
			cellDefaultBg: '#1e1e1e',
			iconColor: '#bdbdbd',
			cellCapBg: '#757575',
			cellCapBorder: '#9e9e9e',
			cellText: '#f5f5f5',
		},
	},
	{
		id: 'neon',
		label: 'Neon',
		mode: 'dark',
		swatch: ['#050510', '#00e5ff', '#ff00aa'],
		desc: 'Cyber accents',
		bms: {
			bgPrimary: '#050510',
			bgSecondary: 'rgba(12, 12, 28, 0.95)',
			bgTertiary: 'rgba(0, 229, 255, 0.08)',
			textPrimary: '#e8f9ff',
			textSecondary: '#80deea',
			textAccent: '#00e5ff',
			borderColor: 'rgba(0, 229, 255, 0.35)',
			cellBorder: '#00e5ff',
			cellDefaultBg: '#0d1528',
			iconColor: '#00e5ff',
			cellCapBg: '#ff00aa',
			cellCapBorder: '#00e5ff',
			cellText: '#e8f9ff',
		},
	},
];

const BMS_VAR_MAP = {
	bgPrimary: '--bg-primary',
	bgSecondary: '--bg-secondary',
	bgTertiary: '--bg-tertiary',
	textPrimary: '--text-primary',
	textSecondary: '--text-secondary',
	textAccent: '--text-accent',
	borderColor: '--border-color',
	cellBorder: '--cell-border-default',
	cellDefaultBg: '--cell-default-bg',
	iconColor: '--icon-color',
	cellCapBg: '--cell-cap-bg',
	cellCapBorder: '--cell-cap-border',
	cellText: '--cell-text-color',
};

export function getThemeById(id) {
	return THEMES.find((t) => t.id === id) || THEMES[0];
}

/**
 * Map legacy cookie values (light/dark) to theme ids.
 */
export function resolveThemeId(raw) {
	if (!raw) return 'midnight';
	if (raw === 'light') return 'solar';
	if (raw === 'dark') return 'midnight';
	if (THEMES.some((t) => t.id === raw)) return raw;
	return 'midnight';
}

/**
 * Apply theme id to <body>: data-theme + light/dark class.
 * @param {string} themeId
 * @param {{ skipPersist?: boolean }} [opts]
 * @returns {object} theme
 */
export function applyThemeId(themeId, opts = {}) {
	const theme = getThemeById(resolveThemeId(themeId));
	const body = document.body;
	body.dataset.theme = theme.id;
	body.classList.remove('light', 'dark');
	body.classList.add(theme.mode);

	if (!opts.skipPersist) {
		try {
			document.cookie = `theme=${theme.id}; path=/; max-age=${365 * 24 * 60 * 60}; SameSite=Lax`;
		} catch { /* ignore */ }
	}

	document.dispatchEvent(new CustomEvent('solar-dash-theme', { detail: theme }));
	document.dispatchEvent(new CustomEvent('solar-dash-theme-applied', { detail: theme }));
	return theme;
}

export function currentThemeMode() {
	return document.body.classList.contains('dark') ? 'dark' : 'light';
}

/**
 * Apply BMS palette CSS variables onto a documentElement (iframe or main).
 * @param {Document} doc
 * @param {object} theme
 */
export function applyBmsPaletteToDocument(doc, theme) {
	if (!doc?.documentElement || !theme?.bms) return;
	const root = doc.documentElement;
	root.setAttribute('data-theme', theme.mode === 'dark' ? 'dark' : theme.id);
	root.setAttribute('data-theme-id', theme.id);
	for (const [key, cssVar] of Object.entries(BMS_VAR_MAP)) {
		if (theme.bms[key] != null) root.style.setProperty(cssVar, theme.bms[key]);
	}
	if (theme.mode === 'dark') {
		root.style.setProperty('--cell-text-shadow', '0 0 2px black');
	} else {
		root.style.setProperty('--cell-text-shadow', 'none');
	}
}
