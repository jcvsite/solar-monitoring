// static/js/ui/charts.js
import {
   SDK
} from '../config.js';
import {
   getThemeColor,
   parseToFloatOrNull,
   isValidNumber,
   formatNum,
   showToast
} from '../utils.js';

const CHART_COLORS = {
   PV_YIELD: '#FBC02D',
   LOAD: '#EF6C00',
   BATTERY_CHARGE: '#0277BD',
   BATTERY_DISCHARGE: '#56b10bff',
   GRID_IMPORT: '#B71C1C',
   GRID_EXPORT: '#84d3ebff',
};

/**
 * Converts a hex color string to an RGBA color string.
 * @param {string} hex - The hex color code (e.g., '#RRGGBB').
 * @param {number} [alpha=1] - The alpha transparency value (0-1).
 * @returns {string} The color in RGBA format.
 */
const hexToRgba = (hex, alpha = 1) => {
   const [r, g, b] = hex.match(/\w\w/g).map(x => parseInt(x, 16));
   return `rgba(${r},${g},${b},${alpha})`;
};

// --- Module-level state for charts and data ---
let powerChart, historicalEnergyChart, hourlyEnergyChart;
let allPowerHistoryData = [];
let lastPowerChartDataTimestamp = 0;
// Load 7 days of history to enable panning. The initial view will be the last 24 hours.
let currentPowerChartHistoryDays = 7;

/**
 * Initializes all charts on the dashboard (Power, Historical Energy, Hourly Energy).
 * Sets up chart configurations, plugins, and custom interactions like panning.
 * @returns {object} An object containing the initialized chart instances: { powerChart, historicalEnergyChart, hourlyEnergyChart }.
 */
export function initializeCharts() {
   const pCanvas = document.getElementById('powerChart');
   const hCanvas = document.getElementById('historicalEnergyChart');
   const hourlyCanvas = document.getElementById('hourlyEnergyChart');

   if (!pCanvas || !hCanvas || !hourlyCanvas) {
      console.error("Could not find all required chart canvases. Aborting chart initialization.");
      return {};
   }
   const pCtx = pCanvas.getContext('2d');
   const hCtx = hCanvas.getContext('2d');
   const hourlyCtx = hourlyCanvas.getContext('2d');

   /**
    * Creates a vertical linear gradient for a chart area fill.
    * @param {CanvasRenderingContext2D} ctx - The chart's rendering context.
    * @param {object} chartArea - The chart's area object from Chart.js.
    * @param {string} colorOpaque - The starting color (at the top).
    * @param {string} colorTransparent - The ending color (at the bottom).
    * @returns {CanvasGradient|string} The gradient or the opaque color if chartArea is not available.
    */
   const createChartGradient = (ctx, chartArea, colorOpaque, colorTransparent) => {
      if (!chartArea) return colorOpaque;
      const gradient = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
      gradient.addColorStop(0, colorOpaque);
      gradient.addColorStop(1, colorTransparent);
      return gradient;
   };

   powerChart = new Chart(pCtx, {
      type: 'line',
      data: {
         datasets: [
            {
               label: 'SOC',
               yAxisID: 'y',
               borderColor: '#f500fdff',
               fill: false,
               borderWidth: 1.5,
               order: 1 
            },
            {
               label: 'Production',
               yAxisID: 'y1',
               borderColor: CHART_COLORS.PV_YIELD,
               backgroundColor: (context) => createChartGradient(context.chart.ctx, context.chart.chartArea, hexToRgba(CHART_COLORS.PV_YIELD, 0.5), hexToRgba(CHART_COLORS.PV_YIELD, 0.05)),
               fill: 'origin',
               order: 2 
            },
            {
               label: 'Battery',
               yAxisID: 'y1',
               borderColor: CHART_COLORS.BATTERY_CHARGE,
               backgroundColor: (context) => createChartGradient(context.chart.ctx, context.chart.chartArea, hexToRgba(CHART_COLORS.BATTERY_CHARGE, 0.6), hexToRgba(CHART_COLORS.BATTERY_DISCHARGE, 0.05)),
               fill: 'origin',
               order: 3
            },
            {
               label: 'Grid',
               yAxisID: 'y1',
               borderColor: CHART_COLORS.GRID_IMPORT,
               backgroundColor: (context) => createChartGradient(context.chart.ctx, context.chart.chartArea, hexToRgba(CHART_COLORS.GRID_IMPORT, 0.6), hexToRgba(CHART_COLORS.GRID_IMPORT, 0.1)),
               fill: 'origin',
               order: 4
            },
            {
               label: 'Load',
               yAxisID: 'y1',
               borderColor: CHART_COLORS.LOAD,
               backgroundColor: (context) => createChartGradient(context.chart.ctx, context.chart.chartArea, hexToRgba(CHART_COLORS.LOAD, 0.6), hexToRgba(CHART_COLORS.LOAD, 0.05)),
               fill: 'origin',
               order: 5
            }
         ].map(ds => ({
            ...ds,
            data: [],
            tension: 0.1,
            pointRadius: 0,
            borderWidth: ds.borderWidth || 1.0
         }))
      },
      options: {
         responsive: true,
         maintainAspectRatio: false,
         spanGaps: true,
         parsing: false,
         scales: {
            x: {
               type: 'time',
               time: { unit: 'hour', tooltipFormat: 'yyyy-MM-dd HH:mm', displayFormats: { hour: 'HH:mm' } },
               title: { display: true, text: 'Time', color: getThemeColor('title') },
               ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 10, color: getThemeColor('text') },
               grid: { color: getThemeColor('grid') }
            },
            y: {
               title: { display: true, text: 'SOC (%)', color: getThemeColor('title') },
               position: 'left', beginAtZero: true, max: 100,
               ticks: { color: getThemeColor('text') },
               grid: { color: getThemeColor('grid') }
            },
            y1: {
               title: { display: true, text: 'Power (W)', color: getThemeColor('title') },
               position: 'right', beginAtZero: false,
               grid: { drawOnChartArea: false },
               ticks: { color: getThemeColor('text') }
            }
         },
         plugins: {
            legend: {
               position: 'top',
               labels: { usePointStyle: true, boxWidth: 10, padding: 15, color: getThemeColor('text') }
            },
            tooltip: {
               mode: 'index',
               intersect: false,
               callbacks: {
                  label: function (ctx) {
                     let l = ctx.dataset.label || '';
                     if (l) l += ': ';
                     if (ctx.parsed.y !== null) {
                        let v = ctx.parsed.y;
                        let u = ctx.dataset.label.includes('SOC') ? '%' : 'W';
                        l += `${v.toFixed(0)}${u}`;
                        if (ctx.dataset.label === 'Battery') {
                           if (v > 1) l += ' (Discharge)';
                           else if (v < -1) l += ' (Charge)';
                        } else if (ctx.dataset.label === 'Grid') {
                           if (v > 1) l += ' (Import)';
                           else if (v < -1) l += ' (Export)';
                        }
                     } else {
                        l += 'N/A';
                     }
                     return l;
                  }
               }
            },
            datalabels: { display: false },
            zoom: {
               pan: { enabled: false },
               zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: 'x' }
            }
         },
         animation: { duration: 0 }
      }
   });
   
   // --- Custom Pan Logic for Power Chart ---
   const canvas = powerChart.canvas;
   canvas.style.cursor = 'grab';
   let isPanning = false;
   let lastX = 0;

   const startPan = (e) => {
      isPanning = true;
      lastX = e.clientX || (e.touches && e.touches[0].clientX);
      canvas.style.cursor = 'grabbing';
      e.preventDefault();
   };

   const doPan = (e) => {
      if (!isPanning) return;
      const currentX = e.clientX || (e.touches && e.touches[0].clientX);
      const deltaX = currentX - lastX;
      lastX = currentX;
      powerChart.pan({ x: deltaX }, undefined, 'default');
      powerChart.update('none'); // Use 'none' for performance during pan
      e.preventDefault();
   };

   const endPan = () => {
      isPanning = false;
      canvas.style.cursor = 'grab';
   };
   
   canvas.addEventListener('mousedown', startPan);
   canvas.addEventListener('mousemove', doPan);
   canvas.addEventListener('mouseup', endPan);
   canvas.addEventListener('mouseleave', endPan);
   canvas.addEventListener('touchstart', startPan, { passive: true });
   canvas.addEventListener('touchmove', doPan, { passive: true });
   canvas.addEventListener('touchend', endPan);
   canvas.addEventListener('touchcancel', endPan);


   historicalEnergyChart = new Chart(hCtx, {
      type: 'bar',
      data: {
         labels: [],
         datasets: [
            { label: 'PV Yield',          backgroundColor: hexToRgba(CHART_COLORS.PV_YIELD, 0.7),          key: 'pv_yield_kwh',          borderRadius: 3},
            { label: 'Load',              backgroundColor: hexToRgba(CHART_COLORS.LOAD, 0.7),              key: 'load_energy_kwh',       borderRadius: 3},
            { label: 'Battery Charge',    backgroundColor: hexToRgba(CHART_COLORS.BATTERY_CHARGE, 0.7),    key: 'battery_charge_kwh',    borderRadius: 3},
            { label: 'Battery Discharge', backgroundColor: hexToRgba(CHART_COLORS.BATTERY_DISCHARGE, 0.7), key: 'battery_discharge_kwh', borderRadius: 3},
            { label: 'Grid Import',       backgroundColor: hexToRgba(CHART_COLORS.GRID_IMPORT, 0.7),       key: 'grid_import_kwh',       borderRadius: 3},
            { label: 'Grid Export',       backgroundColor: hexToRgba(CHART_COLORS.GRID_EXPORT, 0.7),       key: 'grid_export_kwh',       borderRadius: 3},
         ]
      },
      options: {
         responsive: true,
         maintainAspectRatio: false,
         scales: {
            x: {
               type: 'time',
               time: { unit: 'day', tooltipFormat: 'MMM d, yyyy', displayFormats: { day: 'MMM d' } },
               title: { display: true, text: 'Date', color: getThemeColor('title') },
               ticks: { color: getThemeColor('text') },
               grid: { color: getThemeColor('grid') }
            },
            y: {
               title: { display: true, text: 'Energy (kWh)', color: getThemeColor('title') },
               beginAtZero: true,
               ticks: { callback: v => v.toFixed(1), color: getThemeColor('text') },
               grid: { color: getThemeColor('grid') }
            }
         },
         plugins: {
            legend: {
               position: 'top',
               labels: {
                  color: getThemeColor('text'),
                  usePointStyle: true,
                  pointStyle: 'rectRounded',
                  boxWidth: 12
               },
               onClick: (e, legendItem, legend) => {
                  const index = legendItem.datasetIndex;
                  const ci = legend.chart;
                  if (ci.isDatasetVisible(index)) {
                     ci.hide(index);
                     legendItem.hidden = true;
                  } else {
                     ci.show(index);
                     legendItem.hidden = false;
                  }
               }
            },
            tooltip: {
               mode: 'index',
               intersect: false,
               callbacks: {
                  label: ctx => `${ctx.dataset.label || ''}: ${ctx.parsed.y !== null ? ctx.parsed.y.toFixed(2) + ' kWh' : 'N/A'}`
               }
            },
            datalabels: { display: false }
         }
      }
   });

   /**
    * A scriptable option for Chart.js to dynamically set the border radius
    * of bars in a stacked bar chart. It rounds the corners of the topmost
    * positive bar and the bottommost negative bar in each stack.
    * @param {object} context - The scriptable context provided by Chart.js.
    * @returns {object|number} A border radius object or 0.
    */
   const scriptableBorderRadius = (context) => {
      const { chart, dataIndex, datasetIndex } = context;
      const { datasets } = chart.data;
      const cornerRadius = 3;

      // Get the current dataset's value and metadata
      const value = datasets[datasetIndex].data[dataIndex];
      const meta = chart.getDatasetMeta(datasetIndex);

      // Skip if value is zero, null, or dataset is hidden
      if (!value || value === 0 || !meta.visible) {
         return 0;
      }

      const isPositive = value > 0;
      const stackId = meta.stack; // 'energy' for all datasets in this case

      // Get all visible datasets in the same stack with non-zero values at this dataIndex
      const stackDatasets = datasets
         .map((ds, index) => ({
               value: ds.data[dataIndex],
               index,
               meta: chart.getDatasetMeta(index)
         }))
         .filter(ds => 
               ds.value && ds.value !== 0 && 
               ds.meta.visible && 
               ds.meta.stack === stackId
         );

      // Separate positive and negative values
      const positiveDatasets = stackDatasets.filter(ds => ds.value > 0);
      const negativeDatasets = stackDatasets.filter(ds => ds.value < 0);

      // Find the topmost positive dataset (highest in stack order)
      const topPositive = positiveDatasets.reduce((top, ds) => 
         ds.index > top.index ? ds : top, 
         { index: -1 }
      );

      // Find the bottommost negative dataset (lowest in stack order)
      const bottomNegative = negativeDatasets.reduce((bottom, ds) => 
         ds.index < bottom.index ? ds : bottom, 
         { index: Infinity }
      );

      // Apply border radius based on position in stack
      if (isPositive && datasetIndex === topPositive.index) {
         return { topLeft: cornerRadius, topRight: cornerRadius, bottomLeft: 0, bottomRight: 0 };
      } else if (!isPositive && datasetIndex === bottomNegative.index) {
         return { topLeft: 0, topRight: 0, bottomLeft: cornerRadius, bottomRight: cornerRadius };
      }

      // No border radius for intermediate bars
      return 0;
   };

    hourlyEnergyChart = new Chart(hourlyCtx, {
        type: 'bar',
        data: {
            labels: Array.from({ length: 24 }, (_, i) => i), // 0-23
            datasets: [
                // Positive stack (Consumption by the house) - Order determines stacking order (first is bottom)
                { label: 'From Solar',          backgroundColor: hexToRgba(CHART_COLORS.PV_YIELD, 0.7),          stack: 'energy', key: 'solar_to_load_kwh',     borderRadius: scriptableBorderRadius },
                { label: 'From Battery',        backgroundColor: hexToRgba(CHART_COLORS.BATTERY_DISCHARGE, 0.7), stack: 'energy', key: 'battery_discharge_kwh', borderRadius: scriptableBorderRadius },
                { label: 'From Grid',           backgroundColor: hexToRgba(CHART_COLORS.GRID_IMPORT, 0.7),       stack: 'energy', key: 'grid_import_kwh',       borderRadius: scriptableBorderRadius },
                // Negative stack (Energy sent away)
                { label: 'To Battery (Charge)', backgroundColor: hexToRgba(CHART_COLORS.BATTERY_CHARGE, 0.7),    stack: 'energy', key: 'battery_charge_kwh',    borderRadius: scriptableBorderRadius },
                { label: 'To Grid (Export)',    backgroundColor: hexToRgba(CHART_COLORS.GRID_EXPORT, 0.7),       stack: 'energy', key: 'grid_export_kwh',       borderRadius: scriptableBorderRadius }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    stacked: true,
                    title: { display: true, text: 'Hour of Day', color: getThemeColor('title') },
                    ticks: {
                        color: getThemeColor('text'),
                        callback: function (val, index) {
                            const hour = this.getLabelForValue(val);
                            if (hour % 2 !== 0) return ''; // Show every 2 hours
                            const ampm = hour < 12 ? 'am' : 'pm';
                            const displayHour = hour % 12 === 0 ? 12 : hour % 12;
                            return `${displayHour}${ampm}`;
                        }
                    },
                    grid: { color: getThemeColor('grid') }
                },
                y: {
                    stacked: true,
                    title: { display: true, text: 'Energy (kWh)', color: getThemeColor('title') },
                    ticks: {
                        color: getThemeColor('text'),
                        callback: v => Math.abs(v).toFixed(1)
                    },
                    grid: { color: getThemeColor('grid') }
                }
            },
            plugins: {
                legend: {
                   position: 'top',
                   labels: {
                      color: getThemeColor('text'),
                      usePointStyle: true,
                      pointStyle: 'rectRounded',
                      boxWidth: 12
                   }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    callbacks: {
                        label: ctx => `${ctx.dataset.label || ''}: ${ctx.parsed.y !== null ? Math.abs(ctx.parsed.y).toFixed(2) + ' kWh' : 'N/A'}`
                    }
                },
                datalabels: { display: false }
            }
        }
    });

   return {
      powerChart,
      historicalEnergyChart,
      hourlyEnergyChart
   };
}

/**
 * Updates the power chart with new data.
 * Can operate in two modes:
 * 1. Appending live data points from the clientState.
 * 2. Replacing the entire history with a new dataset.
 * @param {Chart} chartInstance - The Chart.js instance to update.
 * @param {object} clientState - The latest full state object from the server, used for live updates.
 * @param {Array} [historyData] - Optional array of historical data points for a full replacement.
 * @param {boolean} [isFullHistoryReplacement=false] - Flag to indicate a full data replacement.
 */
export function updatePowerChart(chartInstance, clientState, historyData, isFullHistoryReplacement = false) {
   if (!chartInstance) return;

   const nowClientTime = Date.now();
   const nowServerTime = clientState[SDK.SERVER_TIMESTAMP_MS_UTC] || nowClientTime;

   if (isFullHistoryReplacement) {
      allPowerHistoryData = (historyData || []).map(row => ({
         timestamp: parseInt(row.timestamp, 10),
         soc: parseToFloatOrNull(row[SDK.BATTERY_STATE_OF_CHARGE_PERCENT] ?? row.soc),
         production: parseToFloatOrNull(row[SDK.PV_TOTAL_DC_POWER_WATTS] ?? row.production),
         battery: parseToFloatOrNull(row[SDK.BATTERY_POWER_WATTS] ?? row.battery),
         load: parseToFloatOrNull(row[SDK.LOAD_TOTAL_POWER_WATTS] ?? row.load),
         grid: -parseToFloatOrNull(row[SDK.GRID_TOTAL_ACTIVE_POWER_WATTS] ?? row.grid)
      })).sort((a, b) => a.timestamp - b.timestamp);
      lastPowerChartDataTimestamp = allPowerHistoryData.length > 0 ? allPowerHistoryData[allPowerHistoryData.length - 1].timestamp : 0;
   } else {
      const dataToProcess = clientState;
      if (dataToProcess && Object.keys(dataToProcess).length > 0) {
         const liveTimestamp = parseToFloatOrNull(dataToProcess[SDK.SERVER_TIMESTAMP_MS_UTC]);
         if (liveTimestamp && liveTimestamp > lastPowerChartDataTimestamp) {
            allPowerHistoryData.push({
               timestamp: liveTimestamp,
               soc: parseToFloatOrNull(dataToProcess[SDK.BATTERY_STATE_OF_CHARGE_PERCENT]),
               production: parseToFloatOrNull(dataToProcess[SDK.PV_TOTAL_DC_POWER_WATTS]),
               battery: parseToFloatOrNull(dataToProcess[SDK.BATTERY_POWER_WATTS]),
               load: parseToFloatOrNull(dataToProcess[SDK.LOAD_TOTAL_POWER_WATTS]),
               grid: -parseToFloatOrNull(dataToProcess[SDK.GRID_TOTAL_ACTIVE_POWER_WATTS])
            });
            lastPowerChartDataTimestamp = liveTimestamp;
            const oldestAllowed = nowClientTime - ((currentPowerChartHistoryDays + 1) * 24 * 60 * 60 * 1000);
            allPowerHistoryData = allPowerHistoryData.filter(p => p.timestamp >= oldestAllowed);
         }
      }
   }

   const datasets = {
      'SOC': [], 'Production': [], 'Battery': [], 'Load': [], 'Grid': []
   };
   allPowerHistoryData.forEach(r => {
      const t = r.timestamp;
      if (isValidNumber(r.soc)) datasets['SOC'].push({ x: t, y: r.soc });
      if (isValidNumber(r.production)) datasets['Production'].push({ x: t, y: r.production });
      if (isValidNumber(r.battery)) datasets['Battery'].push({ x: t, y: r.battery });
      if (isValidNumber(r.load)) datasets['Load'].push({ x: t, y: r.load });
      if (isValidNumber(r.grid)) datasets['Grid'].push({ x: t, y: r.grid });
   });

   chartInstance.data.datasets.forEach(ds => {
      ds.data = datasets[ds.label] || [];
   });
   
   if (isFullHistoryReplacement) {
      chartInstance.options.scales.x.max = nowServerTime;
      chartInstance.options.scales.x.min = nowServerTime - (24 * 60 * 60 * 1000);
   }

   chartInstance.update('none');
}

/**
 * Updates the historical energy bar chart based on the server response.
 * It handles different data structures for daily, monthly, and yearly summaries.
 * @param {Chart} chartInstance - The Chart.js instance for the historical chart.
 * @param {object} response - The data object from the server, containing summary data.
 */
export function updateHistoryChart(chartInstance, response) {
    if (!chartInstance || !response) return;
    const { request_type, summaries, monthly_summaries, yearly_summaries } = response;
    
    let labels = [];
    const datasetsData = {};
    chartInstance.data.datasets.forEach(ds => {
        datasetsData[ds.key] = [];
    });
    let sourceData = [];

    if (request_type === 'daily' || request_type === 'current_month_daily') {
        chartInstance.options.scales.x.type = 'time';
        chartInstance.options.scales.x.time = { unit: 'day', tooltipFormat: 'MMM d, yyyy', displayFormats: { day: 'MMM d' } };
        chartInstance.options.scales.x.title.text = 'Date';
        sourceData = summaries || [];
        labels = sourceData.map(s => s.date);
    } else if (request_type === 'yearly_by_month') {
        chartInstance.options.scales.x.type = 'category';
        delete chartInstance.options.scales.x.time;
        chartInstance.options.scales.x.title.text = `Month (${response.query_year || ''})`;
        sourceData = monthly_summaries || [];
        labels = sourceData.map(s => new Date(s.month + '-02').toLocaleString('default', { month: 'short' }));
    } else if (request_type === 'yearly_summary') {
        chartInstance.options.scales.x.type = 'category';
        delete chartInstance.options.scales.x.time;
        chartInstance.options.scales.x.title.text = 'Year';
        sourceData = yearly_summaries || [];
        labels = sourceData.map(s => s.year);
    }

    sourceData.forEach(summary => {
        for (const key in datasetsData) {
            datasetsData[key].push(parseToFloatOrNull(summary[key]) ?? 0);
        }
    });

    chartInstance.data.labels = labels;
    chartInstance.data.datasets.forEach(dataset => {
        dataset.data = datasetsData[dataset.key];
    });
    chartInstance.update();
}

/**
 * Updates the hourly energy summary chart.
 * It processes hourly data, making consumption values positive and production-to-grid/battery negative
 * to create a stacked chart centered on the zero-axis.
 * @param {Chart} chartInstance - The Chart.js instance for the hourly chart.
 * @param {object} response - The data object from the server containing the hourly summary.
 */
export function updateHourlyChart(chartInstance, response) {
    if (!chartInstance || !response || !response.summary) return;

    const hourlyData = response.summary;
    const returnKeys = ['grid_export_kwh', 'battery_charge_kwh'];

    chartInstance.data.datasets.forEach(dataset => {
        dataset.data = hourlyData.map(hourData => {
            const val = hourData[dataset.key] || 0;
            const isReturn = returnKeys.includes(dataset.key);
            // Make the 'return' values negative so they draw below the axis
            return isReturn ? -val : val;
        });
    });
    chartInstance.update();
}

/**
 * Handles the change event from the history period dropdown.
 * It determines the correct request type and parameters to send to the server via WebSocket.
 * @param {string} period - The selected value from the dropdown (e.g., 'last_7_days').
 * @param {object} socket - The Socket.IO instance to emit the request.
 */
export function handleHistoryPeriodChange(period, socket) {
    let type, queryParam;
    switch (period) {
        case 'last_7_days':
            type = 'daily';
            queryParam = 7;
            break;
        case 'current_month_daily':
            type = 'current_month_daily';
            queryParam = null;
            break;
        case 'yearly_by_month':
            type = 'yearly_by_month';
            queryParam = new Date().getFullYear();
            break;
        case 'yearly_summary':
            type = 'yearly_summary';
            queryParam = null;
            break;
        default:
            type = 'daily';
            queryParam = 7;
    }
    showToast(`Loading ${period.replace(/_/g, ' ')}...`, 'info');
    socket.emit('request_daily_summary', {
        type,
        value: queryParam
    });
}

/**
 * Exports the data from a given chart to a CSV file.
 * Handles different data structures for the power chart vs. the energy charts.
 * @param {Chart} chart - The Chart.js instance to export data from.
 * @param {string} filenameBase - The base name for the downloaded CSV file.
 */
export function exportChartDataToCSV(chart, filenameBase) {
   if (!chart) {
      showToast('Chart not available for export.', 'error');
      return;
   }
   let csvContent = "";
   let headers = [];
   const now = new Date();
   const timestamp = now.toISOString().split('T')[0];
   const filename = `${filenameBase}_${timestamp}.csv`;

   if (chart.canvas.id === 'powerChart') {
      if (!allPowerHistoryData || allPowerHistoryData.length === 0) {
         showToast('No power history data to export.', 'warning');
         return;
      }
      headers = ['Timestamp', 'DateTime (Local)', 'SOC (%)', 'Production (W)', 'Battery (W)', 'Load (W)', 'Grid (W)'];
      csvContent += headers.join(',') + '\r\n';
      allPowerHistoryData.forEach(row => {
         const localDateTime = new Date(row.timestamp).toLocaleString();
         const values = [row.timestamp, `"${localDateTime}"`, formatNum(row.soc, 1, ''), formatNum(row.production, 0, ''), formatNum(row.battery, 0, ''), formatNum(row.load, 0, ''), formatNum(row.grid, 0, '')];
         csvContent += values.join(',') + '\r\n';
      });
   } else if (chart.canvas.id === 'historicalEnergyChart' || chart.canvas.id === 'hourlyEnergyChart') {
      headers = ['Time', ...chart.data.datasets.map(ds => `"${ds.label.replace(/"/g, '""')} (kWh)"`)];
      csvContent += headers.join(',') + '\r\n';
      chart.data.labels.forEach((label, index) => {
         const rowData = [`"${label}"`, ...chart.data.datasets.map(ds => formatNum(Math.abs(ds.data[index]), 3, ''))];
         csvContent += rowData.join(',') + '\r\n';
      });
   } else {
      showToast('Unknown chart type for export.', 'error');
      return;
   }

   const blob = new Blob([csvContent], {
      type: 'text/csv;charset=utf-8;'
   });
   const link = document.createElement("a");
   if (link.download !== undefined) {
      const url = URL.createObjectURL(blob);
      link.setAttribute("href", url);
      link.setAttribute("download", filename);
      link.style.visibility = 'hidden';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      showToast(`Exported data to ${filename}`, 'success');
   } else {
      showToast('Export failed: Browser not supported.', 'error');
   }
}

/**
 * Updates the colors of a chart's axes and legend to match the current UI theme (light/dark).
 * @param {Chart} chart - The Chart.js instance to update.
 */
export function updateChartTheme(chart) {
    if (!chart) return;
    chart.options.scales.x.title.color = getThemeColor('title');
    chart.options.scales.x.ticks.color = getThemeColor('text');
    chart.options.scales.x.grid.color = getThemeColor('grid');
    chart.options.scales.y.title.color = getThemeColor('title');
    chart.options.scales.y.ticks.color = getThemeColor('text');
    chart.options.scales.y.grid.color = getThemeColor('grid');
    if (chart.options.scales.y1) {
        chart.options.scales.y1.title.color = getThemeColor('title');
        chart.options.scales.y1.ticks.color = getThemeColor('text');
    }
    chart.options.plugins.legend.labels.color = getThemeColor('text');
    chart.update();
}