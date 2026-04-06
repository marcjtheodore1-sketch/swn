#!/usr/bin/env python3
"""
Export SwN registrations to CSV - READ ONLY, does not modify database
"""

import sqlite3
import csv
from datetime import datetime
import os

# Connect to database (read-only mode for extra safety)
conn = sqlite3.connect('file:instance/swn_bookings.db?mode=ro', uri=True)
conn.row_factory = sqlite3.Row

cursor = conn.cursor()

# Get registrations with event details
cursor.execute("""
    SELECT 
        r.id as registration_id,
        r.name,
        r.email,
        r.phone,
        r.access_needs,
        r.dietary_needs,
        r.attending_with,
        r.additional_info,
        CASE WHEN r.whatsapp_consent = 1 THEN 'Yes' ELSE 'No' END as whatsapp_consent,
        r.created_at as registered_at,
        e.location_id,
        e.walk_date,
        e.start_time,
        e.end_time,
        e.meeting_point
    FROM registration r
    JOIN walk_event e ON r.event_id = e.id
    WHERE r.cancelled_at IS NULL
    ORDER BY e.walk_date, r.created_at
""")

rows = cursor.fetchall()

# Create CSV filename with timestamp
timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
csv_filename = f'registrations-export-{timestamp}.csv'

# Write CSV
with open(csv_filename, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    
    # Write header
    writer.writerow([
        'Registration ID', 'Name', 'Email', 'Phone',
        'Access Needs', 'Dietary Needs', 'Attending With', 'Additional Info',
        'WhatsApp Consent', 'Registered At',
        'Location', 'Walk Date', 'Start Time', 'End Time', 'Meeting Point'
    ])
    
    # Write data
    for row in rows:
        writer.writerow([
            row['registration_id'],
            row['name'],
            row['email'],
            row['phone'],
            row['access_needs'] or '',
            row['dietary_needs'] or '',
            row['attending_with'] or '',
            row['additional_info'] or '',
            row['whatsapp_consent'],
            row['registered_at'],
            row['location_id'],
            row['walk_date'],
            row['start_time'],
            row['end_time'],
            row['meeting_point']
        ])

conn.close()

print("=" * 50)
print("✅ CSV Export Complete!")
print("=" * 50)
print(f"File: {csv_filename}")
print(f"Total registrations exported: {len(rows)}")
print("")
print("Your data is SAFE - this was a read-only export.")
print("=" * 50)
