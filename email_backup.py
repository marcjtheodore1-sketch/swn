#!/usr/bin/env python3
"""
Simple database backup emailer
Run this to email yourself a backup of your database
"""

import os
import sys
import zipfile
from datetime import datetime
from app import app, db


def create_and_email_backup():
    """Create backup and email it"""
    
    # Check if email is enabled
    if not app.config.get('ENABLE_EMAIL'):
        print("WARNING: Email is not enabled in your configuration.")
        print("Set ENABLE_EMAIL=true in your environment to enable email backups.")
        print("")
        print("To manually download your database:")
        print("  File location: instance/swn_bookings.db")
        print("  Use PythonAnywhere Files tab to download it")
        return
    
    # Create backup
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    backup_dir = 'backups'
    
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    db_path = 'instance/swn_bookings.db'
    backup_name = f'swn_bookings-backup-{timestamp}.db'
    zip_path = f'{backup_dir}/swn_bookings-backup-{timestamp}.zip'
    
    # Create zip
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(db_path, backup_name)
    
    print(f"✓ Backup created: {zip_path}")
    
    # Import email function from app
    from app import send_email
    
    # Read zip file
    with open(zip_path, 'rb') as f:
        zip_data = f.read()
    
    # Send email with attachment using MIME
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from email.mime.base import MIMEBase
    from email import encoders
    
    msg = MIMEMultipart()
    msg['Subject'] = f'SwN Database Backup - {timestamp}'
    msg['From'] = app.config['SMTP_FROM']
    msg['To'] = 'miles.lagc@gmail.com'
    
    body = f"""Hello,

Your SwN database backup is attached.

Backup created: {timestamp}
File: {os.path.basename(zip_path)}

This file can restore your entire database if needed.
Keep it safe!

SwN Backup System
"""
    msg.attach(MIMEText(body, 'plain'))
    
    # Attach file
    part = MIMEBase('application', 'zip')
    part.set_payload(zip_data)
    encoders.encode_base64(part)
    part.add_header(
        'Content-Disposition',
        f'attachment; filename="{os.path.basename(zip_path)}"'
    )
    msg.attach(part)
    
    # Send
    with smtplib.SMTP(app.config['SMTP_HOST'], app.config['SMTP_PORT']) as server:
        server.starttls()
        server.login(app.config['SMTP_USER'], app.config['SMTP_PASSWORD'])
        server.send_message(msg)
    
    print(f"✓ Backup emailed to miles.lagc@gmail.com")
    print(f"✓ Backup also saved locally at: {zip_path}")


if __name__ == '__main__':
    print("=" * 50)
    print("SwN Database Backup Tool")
    print("=" * 50)
    print("")
    
    with app.app_context():
        create_and_email_backup()
    
    print("")
    print("=" * 50)
    print("Backup complete!")
    print("=" * 50)
