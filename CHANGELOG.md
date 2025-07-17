# Changelog

All notable changes to the Solar Monitoring Framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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