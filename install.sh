#!/bin/bash
# =============================================================
# Solar Monitoring Framework - Linux/macOS Installation Script
# =============================================================

set -e  # Exit on any error

echo "=========================================="
echo "Solar Monitoring Framework Installation"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Check if Python 3.9+ is available
check_python() {
    print_step "Checking Python version..."
    
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        print_error "Python is not installed. Please install Python 3.9 or newer."
        exit 1
    fi
    
    # Check Python version
    PYTHON_VERSION=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    REQUIRED_VERSION="3.9"
    
    if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" = "$REQUIRED_VERSION" ]; then
        print_status "Python $PYTHON_VERSION found - OK"
    else
        print_error "Python $PYTHON_VERSION found, but Python 3.9+ is required"
        exit 1
    fi
}

# Install system dependencies
install_system_deps() {
    print_step "Installing system dependencies..."
    
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        if command -v apt-get &> /dev/null; then
            # Debian/Ubuntu
            print_status "Detected Debian/Ubuntu system"
            sudo apt-get update
            sudo apt-get install -y python3-pip python3-venv libncursesw5-dev
        elif command -v yum &> /dev/null; then
            # RHEL/CentOS/Fedora
            print_status "Detected RHEL/CentOS/Fedora system"
            sudo yum install -y python3-pip ncurses-devel
        elif command -v pacman &> /dev/null; then
            # Arch Linux
            print_status "Detected Arch Linux system"
            sudo pacman -S --noconfirm python-pip ncurses
        else
            print_warning "Unknown Linux distribution. Please install python3-pip and ncurses development libraries manually."
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        print_status "Detected macOS system"
        if command -v brew &> /dev/null; then
            brew install python@3.9 ncurses
        else
            print_warning "Homebrew not found. Please install Python 3.9+ and ncurses manually."
        fi
    else
        print_warning "Unknown operating system. Please install dependencies manually."
    fi
}

# Create virtual environment
create_venv() {
    print_step "Creating Python virtual environment..."
    
    if [ -d "venv" ]; then
        print_warning "Virtual environment already exists. Removing old one..."
        rm -rf venv
    fi
    
    $PYTHON_CMD -m venv venv
    print_status "Virtual environment created"
}

# Activate virtual environment and install dependencies
install_deps() {
    print_step "Installing Python dependencies..."
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install requirements
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
        print_status "Dependencies installed successfully"
    else
        print_error "requirements.txt not found!"
        exit 1
    fi
}

# Setup configuration
setup_config() {
    print_step "Setting up configuration..."
    
    if [ ! -f "config.ini" ]; then
        if [ -f "config.ini.example" ]; then
            cp config.ini.example config.ini
            print_status "Created config.ini from example template"
            print_warning "Please edit config.ini with your device settings before running the application"
        else
            print_error "config.ini.example not found!"
            exit 1
        fi
    else
        print_status "config.ini already exists - skipping"
    fi
}

# Create startup script
create_startup_script() {
    print_step "Creating startup script..."
    
    cat > start_solar_monitoring.sh << 'EOF'
#!/bin/bash
# Solar Monitoring Framework Startup Script

cd "$(dirname "$0")"

# Activate virtual environment
source venv/bin/activate

# Start the application
python main.py
EOF
    
    chmod +x start_solar_monitoring.sh
    print_status "Created start_solar_monitoring.sh"
}

# Create systemd service (optional)
create_systemd_service() {
    print_step "Creating systemd service (optional)..."
    
    INSTALL_DIR=$(pwd)
    USER=$(whoami)
    
    cat > solar-monitoring.service << EOF
[Unit]
Description=Solar Monitoring Framework
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    print_status "Created solar-monitoring.service"
    print_warning "To install as system service, run:"
    print_warning "  sudo cp solar-monitoring.service /etc/systemd/system/"
    print_warning "  sudo systemctl enable solar-monitoring"
    print_warning "  sudo systemctl start solar-monitoring"
}

# Main installation process
main() {
    print_status "Starting installation process..."
    echo ""
    
    check_python
    install_system_deps
    create_venv
    install_deps
    setup_config
    create_startup_script
    
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        create_systemd_service
    fi
    
    echo ""
    echo "=========================================="
    print_status "Installation completed successfully!"
    echo "=========================================="
    echo ""
    print_status "Next steps:"
    echo "  1. Edit config.ini with your device settings"
    echo "  2. Run: ./start_solar_monitoring.sh"
    echo "  3. Access web dashboard at: http://localhost:8081"
    echo ""
    print_warning "Make sure to configure your inverter and BMS settings in config.ini"
    echo ""
}

# Run main function
main "$@"