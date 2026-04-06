#!/bin/bash

# AI Workforce Orchestrator - Backend Startup Script

set -e

echo "🚀 Starting AI Workforce Orchestrator Backend"
echo "============================================="
echo ""

cd "$(dirname "$0")"

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "Creating virtual environment..."
    python3 -m venv .venv
    echo "✅ Virtual environment created"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Check if dependencies are installed
if ! .venv/bin/python -c "import fastapi" 2>/dev/null; then
    echo "📦 Installing dependencies..."
    .venv/bin/pip install --upgrade pip
    .venv/bin/pip install -r requirements.txt
    echo "✅ Dependencies installed"
else
    echo "✅ Dependencies already installed"
fi

# Check if database exists
if [ ! -f "app.db" ]; then
    echo "🗄️  Initializing database..."
    .venv/bin/python seed_test_data.py
    echo "✅ Database initialized"
else
    echo "✅ Database exists"
fi

echo ""
echo "🎯 Starting server at http://localhost:8000"
echo "📖 API Docs at http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Start the server
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
