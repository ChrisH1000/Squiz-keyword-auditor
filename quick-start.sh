#!/bin/bash

# Squiz Keyword Auditor - Quick Start Script

echo "==================================="
echo "Squiz Keyword Auditor - Quick Start"
echo "==================================="
echo ""

# Check Python version
echo "Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | grep -oP '\d+\.\d+')
REQUIRED_VERSION="3.11"

if (( $(echo "$PYTHON_VERSION < $REQUIRED_VERSION" | bc -l) )); then
    echo "❌ Python 3.11+ required. You have Python $PYTHON_VERSION"
    exit 1
fi
echo "✓ Python $PYTHON_VERSION detected"
echo ""

# Check if Ollama is running
echo "Checking Ollama..."
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "✓ Ollama is running"
else
    echo "⚠️  Ollama is not running. Please start it:"
    echo "   ollama serve"
    echo ""
fi

# Check if models are available
echo ""
echo "Checking Ollama models..."
if ollama list | grep -q "llama3.1:8b-instruct"; then
    echo "✓ llama3.1:8b-instruct model found"
else
    echo "⚠️  llama3.1:8b-instruct not found. Run:"
    echo "   ollama pull llama3.1:8b-instruct"
fi

if ollama list | grep -q "bge-small"; then
    echo "✓ bge-small model found"
else
    echo "⚠️  bge-small not found. Run:"
    echo "   ollama pull bge-small"
fi

echo ""
echo "Setup virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment exists"
fi

echo ""
echo "Activating virtual environment..."
source venv/bin/activate

echo ""
echo "Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "✓ Dependencies installed"

echo ""
echo "==================================="
echo "Setup Complete!"
echo "==================================="
echo ""
echo "To run a test audit:"
echo "  python main.py --codebase test-templates --no-llm"
echo ""
echo "For full audit with AI summary (requires Ollama running):"
echo "  python main.py --codebase test-templates"
echo ""
