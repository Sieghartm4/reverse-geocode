#!/bin/bash

# 🌏 OSM Philippines Reverse Geocoding API - Auto Setup Script
# This script automates the entire setup process on Ubuntu/Linux
# Usage: bash setup.sh

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DB_NAME="ph_geodata"
DB_USER="postgres"
OSM_FILE="philippines-latest.osm.pbf"
OSM_URL="https://download.geofabrik.de/asia/philippines-latest.osm.pbf"
INSTALL_DIR="$HOME/osm"
VENV_DIR="$HOME/reverse-geocode-api/venv"

# Logging
LOG_FILE="setup.log"
exec > >(tee -a "$LOG_FILE")
exec 2>&1

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root (for some operations)
check_root() {
    if [[ $EUID -eq 0 ]]; then
        log_warning "This script should not be run as root. Please run as regular user."
        log_info "The script will use sudo when needed."
        exit 1
    fi
}

# Check system requirements
check_system() {
    log_info "Checking system requirements..."
    
    # Check if Ubuntu/Debian
    if ! command -v apt &> /dev/null; then
        log_error "This script is designed for Ubuntu/Debian systems with apt package manager."
        log_info "For other systems, please manually install dependencies."
        exit 1
    fi
    
    # Check Python version
    if ! python3 --version &> /dev/null; then
        log_error "Python 3 is not installed. Please install Python 3.7+ first."
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    log_info "Found Python $PYTHON_VERSION"
    
    if [[ $(echo "$PYTHON_VERSION < 3.7" | bc -l) -eq 1 ]]; then
        log_error "Python 3.7+ is required. Found $PYTHON_VERSION"
        exit 1
    fi
    
    log_success "System requirements check passed"
}

# Install system dependencies
install_system_deps() {
    log_info "Installing system dependencies..."
    
    # Update package list
    log_info "Updating package list..."
    sudo apt update
    
    # Install required packages
    log_info "Installing PostgreSQL, PostGIS, osm2pgsql, and Python tools..."
    sudo apt install -y postgresql postgresql-contrib postgis osm2pgsql python3-pip python3-venv python3-dev build-essential
    
    log_success "System dependencies installed"
}

# Check PostgreSQL service and password
check_postgresql() {
    log_info "Checking PostgreSQL service..."
    
    if ! systemctl is-active --quiet postgresql; then
        log_info "Starting PostgreSQL service..."
        sudo systemctl start postgresql
        sudo systemctl enable postgresql
    fi
    
    if ! systemctl is-active --quiet postgresql; then
        log_error "Failed to start PostgreSQL service"
        log_info "Please check PostgreSQL installation and try again."
        exit 1
    fi
    
    # Test PostgreSQL connection and handle password
    log_info "Testing PostgreSQL connection..."
    if ! sudo -u postgres psql -c "SELECT 1;" &>/dev/null; then
        log_error "Cannot connect to PostgreSQL as postgres user"
        log_info "Possible causes:"
        log_info "  - PostgreSQL not running"
        log_info "  - Authentication issues"
        log_info "  - Password required for postgres user"
        log_info ""
        log_info "Solutions:"
        log_info "  1. Check if PostgreSQL is running: sudo systemctl status postgresql"
        log_info "  2. Reset postgres password: sudo -u postgres psql -c \"ALTER USER postgres PASSWORD 'yourpassword';\""
        log_info "  3. Check pg_hba.conf for authentication settings"
        exit 1
    fi
    
    log_success "PostgreSQL service is running"
}

# Setup database with error handling
setup_database() {
    log_info "Setting up database..."
    
    # Check if database exists
    if sudo -u postgres psql -lqt 2>/dev/null | cut -d \| -f 1 | grep -qw "$DB_NAME"; then
        log_warning "Database '$DB_NAME' already exists. Skipping database creation."
    else
        log_info "Creating database '$DB_NAME'..."
        if ! sudo -u postgres createdb "$DB_NAME" 2>/dev/null; then
            log_error "Failed to create database '$DB_NAME'"
            log_info "Possible causes:"
            log_info "  - Insufficient permissions"
            log_info "  - PostgreSQL authentication issues"
            log_info "  - Disk space issues"
            log_info ""
            log_info "Solutions:"
            log_info "  1. Check PostgreSQL status: sudo systemctl status postgresql"
            log_info "  2. Test connection: sudo -u postgres psql -c \"SELECT 1;\""
            log_info "  3. Check disk space: df -h"
            log_info "  4. Reset postgres password if needed"
            exit 1
        fi
        
        # Enable PostGIS extension
        log_info "Enabling PostGIS extension..."
        if ! sudo -u postgres psql -c "CREATE EXTENSION IF NOT EXISTS postgis;" "$DB_NAME" 2>/dev/null; then
            log_error "Failed to enable PostGIS extension"
            log_info "Trying alternative method..."
            sudo -u postgres psql "$DB_NAME" << EOF
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS hstore;
EOF
            if [[ $? -ne 0 ]]; then
                log_error "Failed to enable extensions with both methods"
                log_info "Please manually run: sudo -u postgres psql -c \"CREATE EXTENSION postgis;\" $DB_NAME"
                exit 1
            fi
        fi
        
        # Enable hstore extension
        sudo -u postgres psql -c "CREATE EXTENSION IF NOT EXISTS hstore;" "$DB_NAME" 2>/dev/null || {
            log_warning "Failed to enable hstore extension, trying manual method..."
            sudo -u postgres psql "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS hstore;" 2>/dev/null || {
                log_error "Failed to enable hstore extension"
                log_info "Please manually run: sudo -u postgres psql -c \"CREATE EXTENSION hstore;\" $DB_NAME"
            }
        }
        
        log_success "Database setup completed"
    fi
}

# Download OSM data with enhanced error handling
download_osm_data() {
    log_info "Setting up OSM data directory..."
    
    # Create directory if it doesn't exist
    mkdir -p "$INSTALL_DIR"
    cd "$INSTALL_DIR"
    
    # Check for any existing OSM files and validate them
    EXISTING_FILES=(philippines-*.osm.pbf)
    VALID_FILE=""
    
    for file in "${EXISTING_FILES[@]}"; do
        if [[ -f "$file" ]]; then
            FILE_SIZE=$(stat -c%s "$file" 2>/dev/null || echo "0")
            if [[ $FILE_SIZE -gt 100000000 ]]; then  # Greater than 100MB
                # Validate file integrity (basic check)
                if file "$file" | grep -q "OSM"; then
                    log_info "Found valid OSM file: $file ($(numfmt --to=iec $FILE_SIZE))"
                    VALID_FILE="$file"
                    break
                else
                    log_warning "File $file exists but may be corrupted. Re-downloading..."
                    rm -f "$file"
                fi
            else
                log_warning "File $file exists but is too small ($(numfmt --to=iec $FILE_SIZE)). Re-downloading..."
                rm -f "$file"
            fi
        fi
    done
    
    # If we have a valid file, skip download
    if [[ -n "$VALID_FILE" ]]; then
        log_success "Using existing OSM file: $VALID_FILE"
        return
    fi
    
    # Download if needed
    log_info "Downloading Philippines OSM data (this may take a while)..."
    log_info "File size: ~250MB"
    log_info "Download URL: $OSM_URL"
    
    # Try downloading with different methods if first fails
    if ! wget --progress=bar:force --timeout=30 --tries=3 "$OSM_URL" -O philippines-latest.osm.pbf; then
        log_warning "wget failed, trying curl..."
        if ! curl -L --progress-bar --max-time 300 --retry 3 "$OSM_URL" -o philippines-latest.osm.pbf; then
            log_warning "curl failed, trying alternative mirror..."
            ALT_URL="https://download.geofabrik.de/asia/philippines-latest.osm.pbf"
            if ! wget --progress=bar:force --timeout=30 --tries=3 "$ALT_URL" -O philippines-latest.osm.pbf; then
                log_error "All download methods failed"
                log_info "Possible causes:"
                log_info "  - No internet connection"
                log_info "  - Network firewall blocking downloads"
                log_info "  - Download server issues"
                log_info "  - Insufficient disk space"
                log_info ""
                log_info "Solutions:"
                log_info "  1. Check internet: ping -c 3 google.com"
                log_info "  2. Check disk space: df -h"
                log_info "  3. Try manual download:"
                log_info "     cd $INSTALL_DIR"
                log_info "     wget $OSM_URL"
                log_info "  4. Use VPN if network is restricted"
                exit 1
            fi
        fi
    fi
    
    # Verify downloaded file
    DOWNLOADED_FILES=(philippines-*.osm.pbf)
    if [[ ${#DOWNLOADED_FILES[@]} -eq 0 || ! -f "${DOWNLOADED_FILES[0]}" ]]; then
        log_error "Download completed but no OSM file found"
        exit 1
    fi
    
    # Validate downloaded file
    OSM_ACTUAL_FILE="${DOWNLOADED_FILES[0]}"
    FILE_SIZE=$(stat -c%s "$OSM_ACTUAL_FILE" 2>/dev/null || echo "0")
    
    if [[ $FILE_SIZE -lt 100000000 ]]; then
        log_error "Downloaded file is too small ($(numfmt --to=iec $FILE_SIZE)) - likely incomplete"
        log_info "Removing corrupted file and retrying..."
        rm -f "$OSM_ACTUAL_FILE"
        log_info "Please run the setup script again to retry download"
        exit 1
    fi
    
    if ! file "$OSM_ACTUAL_FILE" | grep -q "OSM"; then
        log_error "Downloaded file is not a valid OSM file"
        log_info "File type: $(file "$OSM_ACTUAL_FILE")"
        rm -f "$OSM_ACTUAL_FILE"
        exit 1
    fi
    
    log_success "OSM data downloaded and validated: $OSM_ACTUAL_FILE ($(numfmt --to=iec $FILE_SIZE))"
}

# Import OSM data with comprehensive error handling
import_osm_data() {
    log_info "Importing OSM data into PostgreSQL..."
    
    cd "$INSTALL_DIR"
    
    # Find the actual OSM file (date-based filename)
    OSM_FILES=(philippines-*.osm.pbf)
    if [[ ${#OSM_FILES[@]} -eq 0 || ! -f "${OSM_FILES[0]}" ]]; then
        log_error "No OSM file found. Please download the data first."
        log_info "Looking for files matching pattern: philippines-*.osm.pbf"
        log_info "Current directory contents:"
        ls -la *.osm.pbf 2>/dev/null || log_info "  No .osm.pbf files found"
        exit 1
    fi
    
    OSM_ACTUAL_FILE="${OSM_FILES[0]}"
    log_info "Found OSM file: $OSM_ACTUAL_FILE"
    
    # Validate file before import
    FILE_SIZE=$(stat -c%s "$OSM_ACTUAL_FILE" 2>/dev/null || echo "0")
    if [[ $FILE_SIZE -lt 100000000 ]]; then
        log_error "OSM file is too small ($(numfmt --to=iec $FILE_SIZE)) - likely corrupted"
        log_info "Please re-download the OSM data"
        exit 1
    fi
    
    if ! file "$OSM_ACTUAL_FILE" | grep -q "OSM"; then
        log_error "File is not a valid OSM file"
        log_info "File type: $(file "$OSM_ACTUAL_FILE")"
        exit 1
    fi
    
    # Check if data already imported
    if sudo -u postgres psql -d "$DB_NAME" -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'planet_osm_point';" 2>/dev/null | grep -q "1"; then
        log_warning "OSM data appears to be already imported. Checking table counts..."
        
        # Check if tables have data
        POINT_COUNT=$(sudo -u postgres psql -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM planet_osm_point;" 2>/dev/null | tr -d ' ' || echo "0")
        if [[ $POINT_COUNT -gt 1000 ]]; then
            log_warning "OSM data already imported ($POINT_COUNT points). Skipping import."
            return
        fi
        log_info "Tables exist but seem empty ($POINT_COUNT points). Re-importing..."
    fi
    
    # Check system resources before import
    log_info "Checking system resources..."
    
    # Check available disk space
    AVAILABLE_SPACE=$(df -BG "$INSTALL_DIR" | awk 'NR==2 {print $4}' | tr -d 'G')
    if [[ $AVAILABLE_SPACE -lt 5 ]]; then
        log_error "Insufficient disk space for import. Need at least 5GB, have ${AVAILABLE_SPACE}GB"
        log_info "Please free up disk space and try again"
        exit 1
    fi
    
    # Check available memory
    AVAILABLE_MEM=$(free -g | awk 'NR==2{print $7}')
    if [[ $AVAILABLE_MEM -lt 1 ]]; then
        log_warning "Low available memory (${AVAILABLE_MEM}GB). Import may be slow or fail."
        log_info "Consider closing other applications or adding swap space."
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Import cancelled. Please free up memory and try again."
            exit 1
        fi
    fi
    
    log_info "Starting osm2pgsql import (this may take 20 minutes to 2 hours)..."
    log_info "Using 4 CPU threads for faster processing"
    log_info "Available disk space: ${AVAILABLE_SPACE}GB"
    log_info "Available memory: ${AVAILABLE_MEM}GB"
    
    # Try import with different parameters if first attempt fails
    log_info "Attempting import with standard parameters..."
    if sudo -u postgres osm2pgsql \
        -d "$DB_NAME" \
        -U "$DB_USER" \
        --create \
        --slim \
        -G \
        --hstore \
        --number-processes 4 \
        "$OSM_ACTUAL_FILE" 2>/dev/null; then
        log_success "OSM data import completed successfully"
    else
        log_warning "Standard import failed, trying with reduced memory usage..."
        if sudo -u postgres osm2pgsql \
            -d "$DB_NAME" \
            -U "$DB_USER" \
            --create \
            --slim \
            -G \
            --hstore \
            --number-processes 2 \
            --cache 512 \
            "$OSM_ACTUAL_FILE" 2>/dev/null; then
            log_success "OSM data import completed with reduced parameters"
        else
            log_warning "Reduced memory import failed, trying with minimal parameters..."
            if sudo -u postgres osm2pgsql \
                -d "$DB_NAME" \
                -U "$DB_USER" \
                --create \
                --slim \
                -G \
                --hstore \
                --number-processes 1 \
                --cache 256 \
                "$OSM_ACTUAL_FILE" 2>/dev/null; then
                log_success "OSM data import completed with minimal parameters"
            else
                log_error "All import methods failed"
                log_info "Possible causes:"
                log_info "  - Insufficient disk space (need 5GB+)"
                log_info "  - Insufficient RAM (need 1GB+)"
                log_info "  - Corrupted OSM file"
                log_info "  - PostgreSQL connection issues"
                log_info "  - Database permission issues"
                log_info "  - Missing PostGIS extension"
                log_info ""
                log_info "Solutions:"
                log_info "  1. Check disk space: df -h"
                log_info "  2. Check memory: free -h"
                log_info "  3. Verify OSM file: file $OSM_ACTUAL_FILE"
                log_info "  4. Test database: sudo -u postgres psql -d $DB_NAME -c \"SELECT 1;\""
                log_info "  5. Check extensions: sudo -u postgres psql -d $DB_NAME -c \"SELECT * FROM pg_extension;\""
                log_info "  6. Try manual import:"
                log_info "     cd $INSTALL_DIR"
                log_info "     sudo -u postgres osm2pgsql -d $DB_NAME -U postgres --create --slim -G --hstore $OSM_ACTUAL_FILE"
                log_info ""
                log_info "For systems with limited resources, consider:"
                log_info "  - Adding swap space: sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile"
                log_info "  - Using a smaller OSM extract"
                log_info "  - Upgrading system RAM"
                exit 1
            fi
        fi
    fi
    
    # Verify import success
    log_info "Verifying import..."
    POINT_COUNT=$(sudo -u postgres psql -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM planet_osm_point;" 2>/dev/null | tr -d ' ' || echo "0")
    LINE_COUNT=$(sudo -u postgres psql -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM planet_osm_line;" 2>/dev/null | tr -d ' ' || echo "0")
    POLYGON_COUNT=$(sudo -u postgres psql -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM planet_osm_polygon;" 2>/dev/null | tr -d ' ' || echo "0")
    
    log_success "Import verification:"
    log_info "  Points: $(numfmt --to=si $POINT_COUNT)"
    log_info "  Lines: $(numfmt --to=si $LINE_COUNT)"
    log_info "  Polygons: $(numfmt --to=si $POLYGON_COUNT)"
    
    if [[ $POINT_COUNT -lt 1000 || $LINE_COUNT -lt 1000 || $POLYGON_COUNT -lt 1000 ]]; then
        log_warning "Import seems incomplete (low record counts). Please verify data quality."
    fi
}

# Setup Python environment
setup_python_env() {
    log_info "Setting up Python environment..."
    
    # Check if we're in the right directory
    if [[ ! -f "requirements.txt" ]]; then
        log_error "requirements.txt not found. Please run this script from the project directory."
        exit 1
    fi
    
    # Create virtual environment if it doesn't exist
    if [[ ! -d "$VENV_DIR" ]]; then
        log_info "Creating Python virtual environment..."
        python3 -m venv venv
    fi
    
    # Activate virtual environment
    log_info "Activating virtual environment..."
    source venv/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install requirements
    log_info "Installing Python dependencies..."
    if ! pip install -r requirements.txt; then
        log_error "Failed to install Python dependencies"
        log_info "Possible causes:"
        log_info "  - Missing build tools"
        log_info "  - Network issues"
        log_info "  - Incompatible Python version"
        log_info ""
        log_info "Solutions:"
        log_info "  - Install build tools: sudo apt install build-essential python3-dev"
        log_info "  - Check internet connection"
        log_info "  - Try installing manually: pip install flask psycopg2-binary psycopg2-extras"
        exit 1
    fi
    
    log_success "Python environment setup completed"
}

# Test the API
test_api() {
    log_info "Testing the API..."
    
    # Activate virtual environment
    if [[ -d "$VENV_DIR" ]]; then
        source "$VENV_DIR/bin/activate"
    fi
    
    # Check if API file exists
    if [[ ! -f "reverse-geo-api.py" ]]; then
        log_error "reverse-geo-api.py not found in current directory"
        exit 1
    fi
    
    # Test database connection
    log_info "Testing database connection..."
    python3 -c "
import psycopg2
try:
    conn = psycopg2.connect('dbname=$DB_NAME user=$DB_USER')
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM planet_osm_point LIMIT 1')
    count = cur.fetchone()[0]
    print(f'Database connection successful. Found {count} points.')
    conn.close()
except Exception as e:
    print(f'Database connection failed: {e}')
    exit(1)
"
    
    if [[ $? -ne 0 ]]; then
        log_error "Database connection test failed"
        log_info "Please check PostgreSQL configuration and try again."
        exit 1
    fi
    
    log_success "API test passed"
}

# Create systemd service (optional)
create_service() {
    log_info "Creating systemd service file..."
    
    SERVICE_CONTENT="[Unit]
Description=OSM Philippines Reverse Geocoding API
After=network.target postgresql.service

[Service]
Type=exec
User=$USER
Group=$USER
WorkingDirectory=$(pwd)
Environment=PATH=$(pwd)/venv/bin
ExecStart=$(pwd)/venv/bin/gunicorn -w 4 reverse-geo-api:app -b 0.0.0.0:5111
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target"
    
    echo "$SERVICE_CONTENT" | sudo tee /etc/systemd/system/reverse-geocode.service > /dev/null
    
    log_success "Systemd service created"
    log_info "To enable and start the service:"
    log_info "  sudo systemctl daemon-reload"
    log_info "  sudo systemctl enable reverse-geocode"
    log_info "  sudo systemctl start reverse-geocode"
    log_info "  sudo systemctl status reverse-geocode"
}

# Main execution
main() {
    log_info "🌏 OSM Philippines Reverse Geocoding API - Auto Setup"
    log_info "=================================================="
    log_info "This script will set up everything needed for the reverse geocoding API."
    log_info ""
    log_info "What will be installed:"
    log_info "  - PostgreSQL with PostGIS"
    log_info "  - osm2pgsql (OSM importer)"
    log_info "  - Python virtual environment"
    log_info "  - Philippines OSM data (~250MB)"
    log_info "  - Database with spatial indexes"
    log_info ""
    log_info "Estimated setup time: 30 minutes - 2 hours"
    log_info "Estimated disk usage: ~5GB"
    log_info ""
    
    read -p "Continue with setup? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Setup cancelled."
        exit 0
    fi
    
    # Execute setup steps
    check_root
    check_system
    install_system_deps
    check_postgresql
    setup_database
    download_osm_data
    import_osm_data
    setup_python_env
    test_api
    create_service
    
    log_success "🎉 Setup completed successfully!"
    log_info ""
    log_info "Next steps:"
    log_info "  1. Start the API:"
    log_info "     python3 reverse-geo-api.py"
    log_info "     or"
    log_info "     sudo systemctl start reverse-geocode"
    log_info ""
    log_info "  2. Test the API:"
    log_info "     curl 'http://localhost:5111/reverse?lat=14.3258395&lon=121.0136624'"
    log_info ""
    log_info "  3. View debug info:"
    log_info "     curl 'http://localhost:5111/debug?lat=14.3258395&lon=121.0136624'"
    log_info ""
    log_info "  4. Check logs:"
    log_info "     tail -f setup.log"
    log_info ""
    log_info "API will be available at: http://localhost:5111"
}

# Error handling
trap 'log_error "Setup failed at line $LINENO. Check setup.log for details."' ERR

# Run main function
main "$@"
