#!/usr/bin/env bash
# =============================================================================
# Langly Automated Linting Pipeline
# =============================================================================
# This script runs all linting and code quality checks for the Langly project.
# Usage: ./scripts/lint.sh [--fix] [--strict]
#
# Options:
#   --fix     Auto-fix issues where possible
#   --strict  Fail on warnings (for CI)
# =============================================================================

set -e  # Exit on first error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
FIX_MODE=false
STRICT_MODE=false
for arg in "$@"; do
    case $arg in
        --fix)
            FIX_MODE=true
            shift
            ;;
        --strict)
            STRICT_MODE=true
            shift
            ;;
    esac
done

# Track overall status
OVERALL_STATUS=0

# Function to print section headers
print_header() {
    echo ""
    echo -e "${BLUE}================================================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}================================================================${NC}"
}

# Function to print success
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

# Function to print warning
print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Function to print error
print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Function to run a check
run_check() {
    local name=$1
    local command=$2
    local fix_command=${3:-$command}
    
    if $FIX_MODE && [ -n "$fix_command" ]; then
        echo -e "Running: ${YELLOW}$fix_command${NC}"
        if eval "$fix_command"; then
            print_success "$name passed (with fixes applied)"
        else
            print_error "$name failed"
            OVERALL_STATUS=1
        fi
    else
        echo -e "Running: ${YELLOW}$command${NC}"
        if eval "$command"; then
            print_success "$name passed"
        else
            print_error "$name failed"
            OVERALL_STATUS=1
        fi
    fi
}

# Ensure we're in the project root
cd "$(dirname "$0")/.."

print_header "Langly Linting Pipeline"
echo "Fix mode: $FIX_MODE"
echo "Strict mode: $STRICT_MODE"

# =============================================================================
# 1. Ruff Linting (fast Python linter)
# =============================================================================
print_header "1. Ruff Linting"
if $FIX_MODE; then
    run_check "Ruff linting" "uv run ruff check app tests" "uv run ruff check app tests --fix"
else
    run_check "Ruff linting" "uv run ruff check app tests"
fi

# =============================================================================
# 2. Ruff Formatting Check
# =============================================================================
print_header "2. Ruff Formatting"
if $FIX_MODE; then
    run_check "Ruff formatting" "uv run ruff format --check app tests" "uv run ruff format app tests"
else
    run_check "Ruff formatting" "uv run ruff format --check app tests"
fi

# =============================================================================
# 3. Black Formatting Check
# =============================================================================
print_header "3. Black Formatting"
if $FIX_MODE; then
    run_check "Black formatting" "uv run black --check app tests" "uv run black app tests"
else
    run_check "Black formatting" "uv run black --check app tests"
fi

# =============================================================================
# 4. isort Import Sorting
# =============================================================================
print_header "4. isort Import Sorting"
if $FIX_MODE; then
    run_check "isort" "uv run isort --check-only app tests" "uv run isort app tests"
else
    run_check "isort" "uv run isort --check-only app tests"
fi

# =============================================================================
# 5. MyPy Type Checking
# =============================================================================
print_header "5. MyPy Type Checking"
# MyPy doesn't have a fix mode, run in check mode only
if $STRICT_MODE; then
    run_check "MyPy type checking" "uv run mypy app --strict"
else
    run_check "MyPy type checking" "uv run mypy app --ignore-missing-imports" || true
fi

# =============================================================================
# 6. Bandit Security Scanning
# =============================================================================
print_header "6. Bandit Security Scanning"
run_check "Bandit security scan" "uv run bandit -r app -c pyproject.toml -q" || true

# =============================================================================
# 7. Safety Dependency Check
# =============================================================================
print_header "7. Safety Dependency Check"
# Safety checks for known vulnerabilities in dependencies
echo "Checking dependencies for known vulnerabilities..."
if command -v safety &> /dev/null; then
    run_check "Safety dependency check" "uv run safety check --json 2>/dev/null || true"
else
    print_warning "Safety not installed, skipping dependency vulnerability check"
fi

# =============================================================================
# Summary
# =============================================================================
print_header "Linting Summary"

if [ $OVERALL_STATUS -eq 0 ]; then
    print_success "All linting checks passed!"
    echo ""
    echo -e "${GREEN}Your code is ready for commit.${NC}"
else
    print_error "Some linting checks failed."
    echo ""
    echo -e "${RED}Please fix the issues above before committing.${NC}"
    if ! $FIX_MODE; then
        echo -e "${YELLOW}Tip: Run './scripts/lint.sh --fix' to auto-fix issues.${NC}"
    fi
fi

exit $OVERALL_STATUS
