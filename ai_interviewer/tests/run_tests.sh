#!/bin/bash

# Exit on error
set -e

# Get the absolute path to the project root directory
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

# Function to print error messages
error() {
    echo "ERROR: $1" >&2
    exit 1
}

# Function to print status messages
status() {
    echo ">>> $1"
}

# Change to project root directory
cd "$PROJECT_ROOT" || error "Failed to change to project root directory"

# Create and activate virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    status "Creating virtual environment..."
    python -m venv venv || error "Failed to create virtual environment"
fi

# Activate virtual environment
status "Activating virtual environment..."
source venv/bin/activate || error "Failed to activate virtual environment"

# Upgrade pip
status "Upgrading pip..."
python -m pip install --upgrade pip || error "Failed to upgrade pip"

# Install test requirements
status "Installing test requirements..."
pip install -r ai_interviewer/tests/requirements-test.txt || error "Failed to install test requirements"

# Install the package in editable mode with test dependencies
status "Installing package in development mode..."
pip install -e . || error "Failed to install package"

# Create coverage directory if it doesn't exist
if [ ! -d "coverage" ]; then
    mkdir coverage
fi

# Run tests with coverage
status "Running tests..."
python -m pytest ai_interviewer/tests/ \
    --verbose \
    --cov=ai_interviewer \
    --cov-report=term-missing \
    --cov-report=html:coverage/html \
    --cov-branch \
    --no-cov-on-fail || error "Tests failed"

# Run linting if tests pass
status "Running linting..."
python -m pylint ai_interviewer/ || true  # Don't fail on linting errors for now

# Format code
status "Formatting code..."
python -m black ai_interviewer/ || true  # Don't fail on formatting errors for now

# Print coverage report location
status "Coverage report available at: coverage/html/index.html"

# Deactivate virtual environment
deactivate

status "Testing completed successfully!" 