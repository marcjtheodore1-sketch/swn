# This is the WSGI file for PythonAnywhere
# Copy the contents of this file into:
# /var/www/swn-londonautismgroupcharity_pythonanywhere_com_wsgi.py

import sys
import os

# Add your project directory to the sys.path
path = '/home/londonautismgroupcharity/SwN-flask'
if path not in sys.path:
    sys.path.insert(0, path)

# Set environment variables for email (PythonAnywhere free tier doesn't have env vars)
os.environ['ENABLE_EMAIL'] = 'true'
os.environ['SMTP_HOST'] = 'smtp.gmail.com'
os.environ['SMTP_PORT'] = '587'
os.environ['SMTP_USER'] = 'miles.lagc@gmail.com'
os.environ['SMTP_PASSWORD'] = 'gidxqeqyvdifqzqs'
os.environ['SMTP_FROM'] = 'londonautismgroupcharity@gmail.com'

# Import your Flask app
from app import app as application
