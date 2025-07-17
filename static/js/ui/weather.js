// static/js/ui/weather.js

// --- Global State ---
let map = null,
	animationTimer = null,
	radarLayers = [],
	currentAnimationRequest = 0;

// --- Helper Functions ---
/**
 * Converts a WMO weather code to a human-readable string.
 * @param {number} code - The WMO weather code.
 * @returns {string} The weather description.
 */
function getWeatherDescription(code) {
	const descriptions = { 0:"Clear sky", 1:"Mainly clear", 2:"Partly cloudy", 3:"Cloudy", 45:"Fog", 48:"Rime fog", 51:"Light drizzle", 53:"Mod. drizzle", 55:"Dense drizzle", 61:"Slight rain", 63:"Mod. rain", 65:"Heavy rain", 71:"Slight snow", 73:"Mod. snow", 75:"Heavy snow", 80:"Slight showers", 81:"Mod. showers", 82:"Violent showers", 95:"Thunderstorm", 96:"T-Storm w/ hail" };
	return descriptions[code] || "Unknown";
}

function formatTime(dateString) {
	return new Date(dateString).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}

/**
 * Determines the appropriate SVG icon ID based on the weather code and time of day.
 * @param {number} code - The WMO weather code.
 * @param {number} isDay - 1 for day, 0 for night.
 * @returns {string} The ID of the SVG symbol to use.
 */
function getWeatherIconId(code, isDay) {
	const isDaytime = isDay === 1;
	if (code <= 1) return isDaytime ? 'day' : 'night';
	if (code === 2) return isDaytime ? 'cloudy-day-1' : 'cloudy-night-1';
	if (code === 3 || (code >= 45 && code <= 48)) return 'cloudy';
	if ((code >= 51 && code <= 67) || (code >= 80 && code <= 82)) return 'rainy-6';
	if (code >= 71 && code <= 86) return 'snowy-6';
	if (code >= 95 && code <= 99) return 'thunder';
	return 'cloudy';
}

// --- Core Application Logic ---
/**
 * Updates the UI of the weather card with the latest data.
 * @param {object} data - The weather data object from the Open-Meteo API.
 * @param {string} locationName - The display name for the location.
 */
function updateWeatherCard(data, locationName) {
    const config = window.WEATHER_CONFIG;
	const { current, daily, timezone } = data;
	const now = new Date();
	const dateOptions = { timeZone: timezone, month: 'short', day: 'numeric' };
	const timeOptions = { timeZone: timezone, hour: 'numeric', minute: '2-digit', hour12: true };
	const localDate = now.toLocaleDateString('en-US', dateOptions);
	const localTime = now.toLocaleTimeString('en-US', timeOptions).toLowerCase();
	const tempUnit = config.temp_unit === "celsius" ? "°C" : "°F";

	document.getElementById('datetime').textContent = `${localDate}, ${localTime}`;
	document.getElementById('location').textContent = locationName;
	document.getElementById('temperature').textContent = `${Math.round(current.temperature_2m)}${tempUnit}`;
	document.getElementById('main-weather-icon').setAttributeNS('http://www.w3.org/1999/xlink', 'xlink:href', `#${getWeatherIconId(current.weather_code, current.is_day)}`);
	document.getElementById('weather-type').textContent = getWeatherDescription(current.weather_code);
	document.getElementById('precipitation').textContent = `${current.precipitation_probability} %`;
	document.getElementById('cloud-cover').textContent = `${current.cloud_cover} %`;
	document.getElementById('sunrise').textContent = formatTime(daily.sunrise[0]);
	document.getElementById('sunset').textContent = formatTime(daily.sunset[0]);
	document.getElementById('wind').textContent = `W ${current.windspeed_10m.toFixed(1)} km/h`;
	document.getElementById('visibility').textContent = `${(current.visibility / 1000).toFixed(1)} km`;

	const forecastContainer = document.getElementById('daily-forecast-container');
	forecastContainer.innerHTML = '';
	for (let i = 1; i < 6; i++) {
		const day = document.createElement('div');
		day.className = 'forecast-day';
		const dayName = new Date(daily.time[i]).toLocaleDateString('en-US', { weekday: 'short' }).toUpperCase();
		const iconId = getWeatherIconId(daily.weather_code[i], 1);
		const temp = Math.round(daily.temperature_2m_max[i]);
		day.innerHTML = `<div class="day-name">${dayName}</div><svg class="icon"><use xlink:href="#${iconId}"></use></svg><div class="temp">${temp}${tempUnit}</div>`;
		forecastContainer.appendChild(day);
	}
}

/**
 * Fetches radar frame data from the RainViewer API and sets up an animation loop
 * to display the radar overlay on the map.
 */
async function updateRadarAnimation() {
	const requestId = ++currentAnimationRequest;
	try {
		if (animationTimer) clearInterval(animationTimer);
		radarLayers.forEach(layer => { if (map && map.hasLayer(layer)) map.removeLayer(layer); });
		radarLayers = [];

		const response = await fetch('https://api.rainviewer.com/public/weather-maps.json');
		if (requestId !== currentAnimationRequest) return;
		const data = await response.json();
		
		const host = data.host;
		const radarFrames = data.radar.past;
		if (radarFrames.length === 0) return;

		let currentFrameIndex = 0;
		radarFrames.forEach(frame => {
			const layer = L.tileLayer(`${host}${frame.path}/512/{z}/{x}/{y}/2/1_0.png`, { opacity: 0, zIndex: frame.time });
            if (map) {
                layer.addTo(map);
			    radarLayers.push(layer);
            }
		});

		const showFrame = (index) => {
			radarLayers.forEach((layer, i) => layer.setOpacity(i === index ? 0.8 : 0));
			currentFrameIndex = index;
		};

		showFrame(radarFrames.length - 1);
		animationTimer = setInterval(() => {
			showFrame((currentFrameIndex + 1) % radarFrames.length);
		}, 700);

	} catch (error) {
		console.error("Failed to update radar animation:", error);
	}
}

/**
 * Initializes the Leaflet map, fetches weather data for a specific location,
 * and sets up periodic updates.
 * @param {object} locationConfig - An object containing {lat, lon, name}.
 */
async function loadWeather(locationConfig) {
	if (map) {
		map.remove();
		map = null;
	}
	const mapElement = document.getElementById('map');
	if (!mapElement) return;

	map = L.map('map', { zoomControl: false, attributionControl: false }).setView([locationConfig.lat, locationConfig.lon], window.WEATHER_CONFIG.map_zoom_level);
	
    updateWeatherTheme(document.body.classList.contains('dark') ? 'dark' : 'light');

	// --- Reverse Geocoding to get a better location name ---
	let displayName = locationConfig.name;
	if (["Default Location", "Current Location"].includes(locationConfig.name)) {
		try {
			const geoApiUrl = `https://nominatim.openstreetmap.org/reverse?format=json&lat=${locationConfig.lat}&lon=${locationConfig.lon}`;
			const geoResponse = await fetch(geoApiUrl);
			if (geoResponse.ok) {
				const geoData = await geoResponse.json();
				if (geoData.address) {
					const { city, town, village, country } = geoData.address;
					displayName = `${city || town || village}, ${country}`;
				}
			}
		} catch (error) {
			console.warn("Reverse geocoding failed, using default name.", error);
		}
	}

	L.control.attribution({ prefix: '<a href="https://www.rainviewer.com/" target="_blank">RainViewer</a>' }).addTo(map);

	const forecastApiUrl = 'https://api.open-meteo.com/v1/forecast';
	const params = {
		latitude: locationConfig.lat, longitude: locationConfig.lon,
		current: "temperature_2m,precipitation_probability,weather_code,windspeed_10m,is_day,visibility,cloud_cover",
		daily: "weather_code,temperature_2m_max,sunrise,sunset",
		temperature_unit: window.WEATHER_CONFIG.temp_unit,
		windspeed_unit: "kmh",
		precipitation_unit: "mm",
		timezone: "auto",
		forecast_days: 6
	};
	const forecastUrl = `${forecastApiUrl}?${new URLSearchParams(params)}`;

	const updateAll = async () => {
		try {
			const forecastResponse = await fetch(forecastUrl);
			if (!forecastResponse.ok) {
				const e = await forecastResponse.json();
				throw new Error(`Forecast fetch failed: ${e.reason}`);
			}
			const forecastData = await forecastResponse.json();
			updateWeatherCard(forecastData, displayName);
		} catch (error) {
			console.error("Failed to update weather data:", error);
		}
		updateRadarAnimation();
	};

	updateAll();
	setInterval(updateAll, window.WEATHER_CONFIG.update_interval_mins * 60 * 1000);
}

/**
 * Initializes the weather module. Checks if it's enabled in the config,
 * determines the location (auto or default), and kicks off the loading process.
 */
export function initWeather() {
    const config = window.WEATHER_CONFIG;
    if (!config || !config.enabled) {
        console.log("Weather widget is disabled in config.");
        return;
    }
    document.getElementById('weatherViewTab').style.display = 'inline-flex';
    
    const locationToLoad = {
        name: "Default Location",
        lat: config.default_lat,
        lon: config.default_lon
    };

	if (config.use_auto_location && 'geolocation' in navigator) {
		navigator.geolocation.getCurrentPosition(
			(position) => {
				const { latitude, longitude } = position.coords;
				loadWeather({ name: "Current Location", lat: latitude, lon: longitude });
			},
			(error) => {
				console.warn(`Geolocation error (${error.code}): ${error.message}. Using default location.`);
				loadWeather(locationToLoad);
			}
		);
	} else {
		loadWeather(locationToLoad);
	}
}

/**
 * Updates the map's base tile layer to match the current UI theme.
 * @param {string} theme - The theme name, 'light' or 'dark'.
 */
export function updateWeatherTheme(theme) {
    if (map) {
        let tileUrl = theme === 'dark' 
            ? 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
            : 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png';
        
        let mapHasBaseLayer = false;
        map.eachLayer(layer => {
            if (layer instanceof L.TileLayer && 'setUrl' in layer && layer.options.zIndex === undefined) {
                layer.setUrl(tileUrl);
                mapHasBaseLayer = true;
            }
        });

        if (!mapHasBaseLayer) {
            L.tileLayer(tileUrl).addTo(map);
        }
    }
}

/**
 * Forces the map to recalculate its size, which is useful when its container becomes visible or resizes.
 */
export function handleMapResize() {
    if (map) {
        map.invalidateSize();
    }
}