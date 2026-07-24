# Changelog

All notable changes to the Solar Monitoring Framework will be documented in this file.

## [Unreleased]

## [1.4.0] - 2026-07-24

### Added
- **First-run console setup wizard** (`core/setup_wizard.py`, `core/plugin_catalog.py`)
  - Runs when `config.ini` is missing/incomplete, or with `python main.py --setup`
  - Selects inverter/BMS, writes `config.ini` (`setup_completed=true`), enables console dashboard by default
- **New local-only inverter plugins (testing):** GoodWe, Sofar, Sungrow, Felicity (Modbus), Voltronic PI30
- **New local-only BMS plugins (testing):** JBD/Xiaoxiang, Daly Smart BMS, Pylontech console RS485
- **Shared Modbus inverter base** (`plugins/inverter/modbus_inverter_base.py`) built on `modbus_helper`
- **Decoder unit tests** for JBD/Daly/Pylontech/Voltronic (`test_plugins/test_jbd_daly_decoders.py`)
- **Multi-BMS capacity-weighted aggregation** (`core/bms_aggregator.py`)
  - Combined SOC weighted by pack `full_ah`; summed Ah/power/current; mean pack voltage
  - Publishes `bms_packs_list`, `bms_pack_count`, `bms_aggregation_mode`
  - Web pack strip + BMS iframe pack selector; console per-pack rows; MQTT pack-count sensor
  - Optional `PRIMARY_BMS_INSTANCE` for detail default (does not override combined SOC)
- **Plugin capability metadata (`PLUGIN_META`)** on all inverter/BMS plugins with `get_plugin_meta()`
- **Startup config validator** (`core/config_validator.py`): importable `plugin_type`, rejects known-bad types (e.g. `powmr_modbus_plugin`), connection-key checks
- **Shared Modbus helper** (`plugins/modbus_helper.py`) with Solis as reference migration
- **Broader web first-paint readiness** (inverter status, BMS SOC, or connected + static identity)
- **Plugin health surface** in `shared_data` and UI (web Plugins panel + console age/fail lines)
- **Firmware badges** on flow-board inverter/battery tiles
- **Web UI density** cookie (`ui_density=comfortable|compact`) and console `FONT_SCALE=normal|large`
- **Prometheus metrics service** (`services/metrics_service.py`, `[METRICS]`, default port `9108`)
- **SQLite auto-vacuum / optimize** and optional `DAILY_SUMMARY_MAX_AGE_DAYS` prune
- **Vendored offline dashboard assets** under `static/vendor/` + service worker precache
- **HA discovery coverage test** (`test_plugins/test_ha_discovery_coverage.py`); AC power + lifetime energy sensors added
- **Deye `deye_model_series=auto`** fingerprint probe; **Growatt `has_storage=auto`** storage-block probe
- **Golden capture replay tests** (`test_plugins/test_capture_replay.py` + fixtures)

### Fixed
- **Solis working_status (33121) bit labels**: bits 8–10 are “is load/grid/battery normal?” (1=OK). They were shown as Load/Battery Failure; decoder now inverts those bits and uses corrected Appendix-6 names
- Deye default series in example config is `auto`
- Growatt storage block probing defaults toward `auto` session behavior
- POWMR plugin type remains `inverter.powmr_rs232_plugin` (legacy `powmr_modbus_plugin` rejected by validator)

### Added (prior)
- **EG4 Modbus Plugin**: Complete plugin implementation for EG4 hybrid inverters
  - Dual connection support: Modbus TCP and Serial (RTU) connections
  - Support for EG4 inverter models with comprehensive register mapping
  - Real-time monitoring of PV generation, battery status, and grid interaction
  - Energy statistics tracking (daily and total lifetime values)
  - Temperature monitoring from multiple sensors (inverter, radiator, battery)
  - Comprehensive fault and warning code interpretation
  - Little-endian byte/word order handling as per EG4 protocol specification
  - Operation mode detection with detailed status reporting
  - BMS integration with charge/discharge current limits
  - Standardized data format using StandardDataKeys
- **Growatt Modbus Plugin**: Complete plugin implementation for Growatt inverters
  - Dual connection support: Modbus TCP and Serial (RTU) connections for both standard and storage/hybrid models
  - Support for Growatt MIX and SPH series inverters
  - Dual register block reading (0-124 for inverter data, 1000-1124 for storage data)
  - Real-time monitoring of PV generation, battery management, and grid interaction
  - Energy statistics with comprehensive daily and lifetime tracking
  - Storage system work mode detection and status reporting
  - Temperature monitoring from inverter and battery sensors
  - Standardized data format using StandardDataKeys
- **SRNE Modbus Plugin**: Complete plugin implementation for SRNE solar charge controllers
  - Dual connection support: Modbus TCP and Serial (RTU) connections for SRNE charge controller models
  - Comprehensive register mapping for both static and dynamic data
  - Real-time monitoring of PV charging, battery status, and load management
  - Battery status code interpretation with charging state detection
  - Fault detection with categorized alert reporting (16 low + 16 high fault bits)
  - Temperature monitoring from controller and battery sensors
  - Energy statistics tracking (daily and total lifetime values)
  - DC-only device support with proper MPPT and phase configuration
  - Standardized data format using StandardDataKeys
- **LuxPower Modbus Plugin**: Complete plugin implementation for LuxPower hybrid inverters
  - Dual connection support: Modbus TCP and Serial (RS485) connections
  - Support for LXP-5K, LXP-12K, and LXP-LB-5K inverter models
  - Complete register mapping (90+ operational registers, 50+ configuration registers)
  - Real-time monitoring of PV generation, battery status, and grid interaction
  - Energy statistics tracking (daily and total lifetime values)
  - Temperature monitoring from multiple sensors (inverter and battery)
  - Pre-connection validation for TCP connections (port check + ICMP ping)
  - Comprehensive error handling and connection management
  - Support for lxp-bridge protocol (default port 8000)
  - Automatic retry mechanisms and connection recovery
  - Standardized data format using StandardDataKeys
- **Enhanced Plugin Architecture**: Major improvements to plugin coding standards and consistency
  - **Comprehensive Documentation Standards**: All plugins now follow enterprise-level documentation practices
    - Detailed class docstrings explaining plugin purpose, functionality, and capabilities
    - Complete method documentation with parameter descriptions and return value specifications
    - Inline code comments explaining complex logic and protocol-specific implementations
    - Consistent docstring formatting matching the stable Solis plugin standard
  - **Standardized Coding Practices**: Unified coding style across all inverter plugins
    - Consistent error handling patterns and exception management
    - Unified connection management with pre-connection validation
    - Comprehensive logging with consistent message formatting and plugin instance identification
    - Static methods for register handling and data validation
    - Type safety improvements and data sanitization
    - Enterprise-level coding standards implementation
  - **Plugin Compatibility Analysis**: Detailed analysis of EG4 vs LuxPower compatibility
    - Confirmed EG4 and LuxPower inverters are NOT intercompatible due to fundamental differences
    - Different communication protocols (RTU vs TCP), register mappings, and data encoding
    - Clear documentation preventing configuration errors and compatibility confusion
- **POWMR RS232 Plugin**: Complete rewrite using native inv8851 protocol instead of Modbus
  - Native inv8851 protocol implementation based on header file specification
  - Support for both protocol versions 1 and 2 with automatic packet size handling
  - Complete register mapping with 74+ operational data points
  - Multi-sensor temperature monitoring (4 NTC sensors + battery temperature sensor)
  - BMS integration with individual cell voltage monitoring (up to 16 cells)
  - Comprehensive alert/fault processing with categorized status reporting
  - Dual connection support: direct serial RS232 and TCP via RS232-to-TCP converters
  - Enhanced data standardization with proper scaling and unit conversion
  - Configuration parameter reading for system settings and thresholds
  - Robust error handling with automatic disconnection on communication failures
  - Complete test suite with 30+ unit tests and integration testing
  - Comprehensive documentation with protocol specifications and usage examples
- **Intelligent Decrease Correction**: Advanced filter logic to handle rare cases where sensors self-correct from incorrect spike values
  - Monitors persistent lower values for configurable time period (default: 10 minutes)
  - Requires minimum consistent readings (default: 5 samples) before accepting corrections
  - Prevents filter from getting "stuck" on incorrect spike values
  - Configurable thresholds and monitoring parameters
- **Enhanced Data Filter Service**: Major refactoring and performance improvements
  - Configurable filter parameters via `FilterConfig` dataclass
  - Performance caching for frequently accessed limits (5-minute TTL)
  - Memory management with automatic cleanup of old tracking data
  - Better error handling and graceful degradation
  - Organized key categories for improved maintainability
- **Intelligent Configuration Parsing**: Comprehensive improvements to configuration file handling
  - Smart inline comment detection and removal (`;` and `#` support)
  - Preserves legitimate semicolons in values like crypto keys (TUYA_LOCAL_KEY)
  - Automatic whitespace trimming and quote removal
  - Consistent parsing across main application and all standalone tests
  - Prevents configuration errors from uncommented lines with trailing comments
- **Centralized Test Configuration Loader**: Unified configuration loading for all test plugins ⚠️ **NEEDS TESTING**
  - Single source of truth for configuration parsing logic (`test_plugins/test_config_loader.py`)
  - Eliminates duplicate configuration parsing code across 6 standalone test files
  - Plugin-specific parameter support (POWMR protocol version, Deye model series, Seplos settings)
  - Robust error handling with graceful fallbacks and clear error messages
  - Consistent behavior between test plugins and main application
  - Prevents `invalid literal for int()` errors from malformed configuration values
  - **Status**: Newly implemented - requires testing across all plugin types

### Changed
- **Improved Filter Logging**: Enhanced logging with both current and new values in decrease warnings
- **Filter Performance**: Reduced computational overhead through caching and optimized algorithms
- **Code Organization**: Refactored long methods into focused, single-responsibility functions

### Fixed
- **Data Filter Service**: Fixed attribute reference error (`BATTERY_SOC_PERCENT` → `BATTERY_STATE_OF_CHARGE_PERCENT`)
- **Memory Leaks**: Added automatic cleanup for spike and decrease correction tracking data
- **Filter State Management**: Improved state clearing on daily resets and configuration updates
- **Configuration Parsing**: Fixed inline comment handling in all configuration files
  - Resolved `invalid literal for int()` errors when uncommenting config lines with trailing comments
  - Fixed POWMR plugin baud_rate parsing error: `'2400 ; <-- Common for RS-232'` → `2400`
  - Updated all 6 standalone plugin test files with consistent comment handling
  - Maintains backward compatibility with existing configuration files

## [1.3.1] - 2025-07-17

### Added
- **Multi-threaded Architecture**: Each plugin runs in its own thread for better reliability
- **Advanced Monitoring System**: 3-layer monitoring with watchdog and thread health monitoring
- **Plugin System**: Extensible architecture supporting multiple device types
- **Solis Modbus Plugin**: Full support for Solis inverters via Modbus TCP/RTU (Stable)
- **Deye/Sunsynk Plugin**: Support for Deye and Sunsynk inverters (Need tester)
- **Seplos BMS V2/V3 Plugins**: Battery management system integration (V2 Stable)
- **JK BMS Plugin**: Support for JK BMS devices (Need tester)
- **Web Dashboard**: Real-time monitoring interface with charts and PWA support
- **Console Dashboard**: Text-based live monitoring interface
- **MQTT Integration**: Home Assistant auto-discovery and real-time data publishing
- **Database Logging**: SQLite-based historical data storage
- **Data Filtering**: Intelligent spike detection and data validation
- **Tuya Integration**: Smart plug control based on inverter temperature
- **Weather Widget**: Location-based weather information
- **Test Framework**: Standalone test scripts for plugin development

### Features
- **Real-time Monitoring**: Live data updates every 5 seconds
- **Self-healing**: Automatic recovery from plugin failures
- **Multi-device Support**: Monitor multiple inverters and BMS simultaneously
- **Cross-platform**: Windows, Linux, macOS, and Raspberry Pi support
- **Offline Capable**: Full functionality without internet connection
- **Resource Efficient**: Minimal CPU and memory usage
- **Extensible**: Plugin architecture for adding new device types

### Technical Highlights
- **Thread Safety**: Coordinated multi-threading with conflict prevention
- **Data Standardization**: Unified data format across all plugins
- **Error Handling**: Comprehensive error recovery and logging
- **Configuration Validation**: Built-in configuration checking
- **Performance Optimization**: Efficient data processing and storage
- **Security**: Safe handling of credentials and network communications

### Supported Hardware
- **Inverters**: Solis (hybrid models), Deye/Sunsynk
- **BMS**: Seplos V2/V3, JK BMS
- **Communication**: Modbus TCP, Modbus RTU, Serial, Custom protocols
- **Platforms**: Windows, Linux, macOS, Raspberry Pi

### Initial Release
This is the initial public release of the Solar Monitoring Framework, representing months of development and testing. The framework has been designed from the ground up for reliability, extensibility, and ease of use.

### Contributing
We welcome contributions! Please see our contributing guidelines for more information on how to help improve the Solar Monitoring Framework.
