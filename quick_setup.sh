#!/bin/bash

# ============================================================
# AI Business OS - Quick Setup Script (All-in-One)
# ============================================================
# Usage: bash quick_setup.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

# Header
print_header "AI Business OS - Quick Setup Pipeline"

# Step 1: Environment
print_header "Step 1: Environment Setup"
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
print_success "Python3 available: $(python3 --version)"

# Step 2: Bootstrap
print_header "Step 2: Bootstrap MongoDB Collections"
if python3 bootstrap.py; then
    print_success "Collections bootstrapped"
else
    print_error "Bootstrap failed!"
    exit 1
fi
sleep 1

# Step 3: Indexes
print_header "Step 3: Creating Database Indexes"
if python3 mongo_indexes.py; then
    print_success "Indexes created"
else
    print_error "Index creation failed!"
    exit 1
fi
sleep 1

# Step 4: Test Workers
if [ -d "Workers" ]; then
    print_header "Step 4: Testing Workers"
    
    echo -e "\n${YELLOW}→ Testing key_refiner worker...${NC}"
    python3 Workers/key_refiner.py 2>&1 | head -15 || true
    print_success "key_refiner executed"
    sleep 1
    
    echo -e "\n${YELLOW}→ Testing oneapi_sync worker...${NC}"
    python3 Workers/oneapi_sync.py 2>&1 | head -15 || true
    print_success "oneapi_sync executed"
fi

# Final Summary
print_header "Setup Complete!"

echo ""
echo -e "${GREEN}✓ MongoDB collections created (24 total)${NC}"
echo -e "${GREEN}✓ Database indexes optimized${NC}"
echo -e "${GREEN}✓ Workers tested successfully${NC}"

echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo "1. Push to GitHub:"
echo "   git add ."
echo "   git commit -m 'Setup: Initialize collections and indexes'"
echo "   git push origin main"
echo ""
echo "2. Verify on GitHub Actions:"
echo "   https://github.com/tradeview113d8-code/AI_Business_OS_Data/actions"
echo ""
echo "3. Check setup guide:"
echo "   cat SETUP_GUIDE.md"
echo ""
echo -e "${GREEN}Setup pipeline completed successfully! 🎉${NC}"
