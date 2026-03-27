# Strolling with Neurokin - Flask Version

Python/Flask version for PythonAnywhere hosting.

## PythonAnywhere Setup Instructions

### 1. Upload Files
Upload all files to your PythonAnywhere account via Files tab or Git.

### 2. Create Virtual Environment
In PythonAnywhere Bash console:
```bash
cd ~
mkvirtualenv --python=/usr/bin/python3.10 swn-env
pip install -r requirements.txt
```

### 3. Web App Configuration
- Go to Web tab
- Click "Add a new web app"
- Select **"Manual configuration (including virtualenvs)"**
- Select **Python 3.10**

### 4. Configure WSGI File
In the WSGI configuration file, set:
```python
import sys
path = '/home/YOUR_USERNAME/SwN-flask'
if path not in sys.path:
    sys.path.append(path)

from app import app as application
```

### 5. Set Virtual Environment
In Web tab:
- Virtualenv: `/home/YOUR_USERNAME/.virtualenvs/swn-env`

### 6. Static Files (Optional)
Add static file mapping:
- URL: `/static/`
- Directory: `/home/YOUR_USERNAME/SwN-flask/static`

### 7. Environment Variables
In Web tab, set environment variables:
- `ADMIN_PASSWORD` = your chosen password (default: Moonlight)
- `SECRET_KEY` = a random secret key

### 8. Reload
Click the **Reload** button to start the app.

### 9. Initialize Database
Open a PythonAnywhere Bash console:
```bash
cd ~/SwN-flask
workon swn-env
python -c "from app import app, db, init_events; app.app_context().push(); db.create_all(); init_events()"
```

## Admin Access
- URL: `/admin`
- Password: `Moonlight` (or your custom password)

## Walks Configured
- **Greenwich**: 2nd Sunday monthly, 11:10am-1:10pm (Eoin Little)
- **City of London**: 1st Sunday monthly, 1:30pm-3:30pm (Hazel East)
- **Ealing**: Specific dates, 2:00pm-4:00pm (Zara Salih)
