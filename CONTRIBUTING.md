# Contributing to Solar Monitoring Framework

Thank you for your interest in contributing to the Solar Monitoring Framework! This document provides guidelines and information for contributors.

## 🤝 How to Contribute

### Reporting Issues
- **Bug Reports**: Use the GitHub issue tracker with detailed information
- **Feature Requests**: Describe the feature and its use case
- **Hardware Support**: Request support for new inverters or BMS devices

### Code Contributions
1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

## 🔧 Development Setup

### Prerequisites
- Python 3.9 or newer
- Git
- Virtual environment (recommended)

### Local Development
```bash
# Clone your fork
git clone https://github.com/yourusername/solar-monitoring.git
cd solar-monitoring

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy example config
cp config.ini.example config.ini
# Edit config.ini with your device settings

# Run the application
python main.py
```

## 🔌 Adding New Plugin Support

### Plugin Development
The framework uses a plugin architecture that makes adding new device support straightforward:

1. **Create Plugin File**: `plugins/category/your_device_plugin.py`
2. **Inherit from DevicePlugin**: Implement required methods
3. **Add Constants**: Create constants file if needed
4. **Test Thoroughly**: Use the test framework
5. **Document**: Add configuration examples

### Plugin Structure
```python
from plugins.plugin_interface import DevicePlugin, StandardDataKeys

class YourDevicePlugin(DevicePlugin):
    def connect(self) -> bool:
        # Implement connection logic
        pass
    
    def read_static_data(self) -> Dict[str, Any]:
        # Read device info (model, serial, etc.)
        pass
    
    def read_dynamic_data(self) -> Dict[str, Any]:
        # Read real-time data
        pass
    
    def disconnect(self) -> None:
        # Clean disconnection
        pass
```

### Testing Your Plugin
Use the test framework in `test_plugins/`:
```bash
python test_plugins/your_device_test.py
```

## 📋 Code Standards

### Python Style
- Follow PEP 8 style guidelines
- Use type hints where appropriate
- Add docstrings for classes and methods
- Keep functions focused and small

### Documentation
- Update README.md for new features
- Add configuration examples
- Include troubleshooting information
- Document breaking changes

### Testing
- Test with real hardware when possible
- Use the standalone test scripts
- Verify error handling
- Test edge cases and failure scenarios

## 🐛 Bug Reports

When reporting bugs, please include:

### Required Information
- **Configuration**: Your `config.ini` (remove sensitive data)
- **Logs**: Relevant sections from `solar_monitoring.log`
- **Environment**: OS, Python version, hardware details
- **Steps to Reproduce**: Clear reproduction steps
- **Expected vs Actual**: What should happen vs what happens

### Log Collection
Set `LOG_LEVEL = DEBUG` in config.ini for detailed logs:
```ini
[LOGGING]
LOG_LEVEL = DEBUG
LOG_TO_FILE = True
```

## 🚀 Feature Requests

### Good Feature Requests Include
- **Use Case**: Why is this feature needed?
- **Description**: What should the feature do?
- **Implementation Ideas**: Any thoughts on how to implement
- **Hardware Requirements**: What devices would this support?

### Priority Areas
- New inverter/BMS support
- Enhanced monitoring features
- Performance improvements
- User experience enhancements
- Documentation improvements

## 📝 Documentation

### Areas Needing Help
- Hardware compatibility lists
- Configuration examples
- Troubleshooting guides
- Installation instructions for different platforms
- Video tutorials

### Documentation Standards
- Clear, step-by-step instructions
- Include screenshots where helpful
- Test all procedures before submitting
- Keep language accessible to non-technical users

## 🏷️ Pull Request Guidelines

### Before Submitting
- [ ] Code follows project style guidelines
- [ ] Tests pass (if applicable)
- [ ] Documentation updated
- [ ] No sensitive data in commits
- [ ] Commit messages are clear

### Pull Request Template
```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Performance improvement

## Testing
- [ ] Tested with real hardware
- [ ] Used standalone test scripts
- [ ] Verified no regressions

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No sensitive data included
```

## 🤔 Questions?

### Getting Help
- **GitHub Discussions**: For general questions
- **GitHub Issues**: For bugs and feature requests
- **Documentation**: Check README.md first

### Response Times
This is a personal project maintained by [@jcvsite](https://github.com/jcvsite). While I aim to respond promptly, please be patient as this is maintained in my spare time.

## 📄 License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for helping make the Solar Monitoring Framework better! 🌟