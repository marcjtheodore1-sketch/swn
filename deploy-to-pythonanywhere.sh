#!/bin/bash
# PythonAnywhere Deployment Script

echo "=== Setting up Strolling with Neurokin on PythonAnywhere ==="

# 1. Create virtual environment
echo "Creating virtual environment..."
mkvirtualenv --python=/usr/bin/python3.10 swn-venv

# 2. Install requirements
echo "Installing requirements..."
pip install -r requirements.txt

# 3. Initialize database
echo "Initializing database..."
python -c "from app import app, db, init_events; app.app_context().push(); db.create_all(); init_events()"

echo "=== Setup complete! Now configure the Web tab ==="
echo "1. Source code: /home/londonautismgroupcharity/SwN-flask"
echo "2. Working directory: /home/londonautismgroupcharity/SwN-flask"
echo "3. Virtualenv: /home/londonautismgroupcharity/.virtualenvs/swn-venv"
echo "4. Update WSGI file (see wsgi-pythonanywhere.py)"
