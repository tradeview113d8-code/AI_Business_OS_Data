#!/bin/bash

# ============================================================
# AI Business OS - Complete Setup Script
# ============================================================
# This script automates the full setup process:
# 1. Bootstrap MongoDB collections
# 2. Create database indexes
# 3. Test workers
# 4. Display status
# ============================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo -e "${BLUE}============================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}============================================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Check environment
print_header "Checking Environment"

if [ ! -f ".env" ]; then
    print_error ".env file not found!"
    print_warning "Please create .env with MONGO_URI and DB_NAME"
    exit 1
fi

print_success ".env file found"

if ! command -v python3 &> /dev/null; then
    print_error "Python3 is not installed"
    exit 1
fi

print_success "Python3 is available: $(python3 --version)"

# Check if Core modules exist
if [ ! -d "Core" ]; then
    print_error "Core directory not found!"
    exit 1
fi

if [ ! -f "Core/mongo.py" ]; then
    print_error "Core/mongo.py not found!"
    exit 1
fi

print_success "Core modules found"

# Check dependencies
print_header "Checking Python Dependencies"

required_packages=("pymongo" "python-dotenv" "requests")
for package in "${required_packages[@]}"; do
    if python3 -c "import ${package}" 2>/dev/null; then
        print_success "$package is installed"
    else
        print_warning "$package not found - installing..."
        pip3 install "$package" || pip install "$package"
    fi
done

# Step 1: Bootstrap
print_header "Step 1: Bootstrap MongoDB Collections"
if python3 bootstrap.py; then
    print_success "Bootstrap completed successfully"
else
    print_error "Bootstrap failed!"
    exit 1
fi

sleep 1

# Step 2: Create Indexes
print_header "Step 2: Creating Database Indexes"
if python3 mongo_indexes.py; then
    print_success "Indexes created successfully"
else
    print_error "Index creation failed!"
    exit 1
fi

sleep 1

# Step 3: Test Workers
print_header "Step 3: Testing Workers"

if [ ! -d "Workers" ]; then
    print_warning "Workers directory not found - skipping worker tests"
else
    echo -e "\n${YELLOW}Testing key_refiner worker...${NC}"
    if python3 Workers/key_refiner.py 2>&1 | head -20; then
        print_success "key_refiner worker executed"
    else
        print_warning "key_refiner worker encountered an issue (may be normal if no keys to process)"
    fi

    sleep 1

    echo -e "\n${YELLOW}Testing oneapi_sync worker...${NC}"
    if python3 Workers/oneapi_sync.py 2>&1 | head -20; then
        print_success "oneapi_sync worker executed"
    else
        print_warning "oneapi_sync worker encountered an issue (may be normal if no keys to sync)"
    fi
fi

# Step 4: Summary
print_header "Setup Complete!"

echo -e "\n${BLUE}Next Steps:${NC}"
echo "1. Restart Telegram bot (if running) to enable /apikey command"
echo "2. Push changes to GitHub:"
echo "   git add ."
echo "   git commit -m 'Setup: Bootstrap collections and indexes'"
echo "   git push origin main"
echo ""
echo "3. Verify workflows are triggered on GitHub Actions"
echo ""
echo -e "${GREEN}Setup completed successfully!${NC}"
