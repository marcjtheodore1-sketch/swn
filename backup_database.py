#!/usr/bin/env python3
"""
Database Backup Script for SwN
Creates a timestamped backup and emails it to miles.lagc@gmail.com
This script is READ-ONLY - it does not modify your database in any way.
"""

import os
import smtplib
import zipfile
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import shutil

# Configuration
DB_PATH = 'instance/swn_bookings.db'
BACKUP_DIR = 'backups'
RECIPIENT_EMAIL = 'miles.lagc@gmail.com'

# Email settings (using same config as your app)
SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_USER = os.environ.get('SMTP_USER', '')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
SMTP_FROM = os.environ.get('SMTP_FROM', 'bookings@example.com')


def create_backup():
    """Create a timestamped backup of the database"""
    # Ensure backup directory exists
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    backup_filename = f'swn_bookings-backup-{timestamp}.db'
    backup_path = os.path.join(BACKUP_DIR, backup_filename)
    zip_filename = f'swn_bookings-backup-{timestamp}.zip'
    zip_path = os.path.join(BACKUP_DIR, zip_filename)
    
    # Copy database file (read-only operation)
    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database not found at {DB_PATH}")
        return None, None
    
    shutil.copy2(DB_PATH, backup_path)
    print(f"✓ Database copied to {backup_path}")
    
    # Create zip file
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(backup_path, backup_filename)
    print(f"✓ Backup zipped to {zip_path}")
    
    # Remove the uncompressed copy
    os.remove(backup_path)
    
    return zip_path, timestamp


def send_backup_email(zip_path, timestamp):
    """Email the backup file"""
    if not SMTP_USER or not SMTP_PASSWORD:
        print("WARNING: Email not configured. Backup saved locally only.")
        print(f"Backup location: {zip_path}")
        return False
    
    try:
        msg = MIMEMultipart()
        msg['Subject'] = f'SwN Database Backup - {timestamp}'
        msg['From'] = SMTP_FROM
        msg['To'] = RECIPIENT_EMAIL
        
        # Email body
        body = f"""Hello,

This is your automated SwN database backup.

Backup Date: {timestamp}
File: {os.path.basename(zip_path)}

This backup contains all your registration data and can be used to restore your database if needed.

To restore:
1. Unzip the attached file
2. Place the .db file in your instance/ folder
3. Rename it to swn_bookings.db (backup the old one first!)

Best regards,
SwN Backup System
"""
        msg.attach(MIMEText(body, 'plain'))
        
        # Attach the zip file
        with open(zip_path, 'rb') as f:
            part = MIMEBase('application', 'zip')
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename="{os.path.basename(zip_path)}"'
            )
            msg.attach(part)
        
        # Send email
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        
        print(f"✓ Backup emailed to {RECIPIENT_EMAIL}")
        return True
        
    except Exception as e:
        print(f"ERROR: Failed to send email: {e}")
        print(f"Backup saved locally at: {zip_path}")
        return False


def main():
    print("=" * 50)
    print("SwN Database Backup Tool")
    print("=" * 50)
    print(f"Database: {DB_PATH}")
    print(f"Backup will be emailed to: {RECIPIENT_EMAIL}")
    print("-" * 50)
    
    # Create backup
    zip_path, timestamp = create_backup()
    if not zip_path:
        print("ERROR: Backup failed")
        return
    
    # Send email
    send_backup_email(zip_path, timestamp)
    
    print("-" * 50)
    print(f"✓ Backup complete: {zip_path}")
    print("=" * 50)


if __name__ == '__main__':
    main()
