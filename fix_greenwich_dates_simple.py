#!/usr/bin/env python3
"""
Fix Greenwich walk dates - Direct SQLite approach
No app imports needed, just raw database updates
"""

import sqlite3
from datetime import date

DB_PATH = 'instance/swn_bookings.db'

# Map of old incorrect dates to new correct dates
# Format: (year, month, day)
date_corrections = {
    (2026, 6, 13): (2026, 6, 14),   # Sat → Sun
    (2026, 7, 11): (2026, 7, 12),   # Sat → Sun
    (2026, 8, 8):  (2026, 8, 9),    # Sat → Sun
    (2026, 9, 12): (2026, 9, 13),   # Sat → Sun
    (2026, 10, 10): (2026, 10, 11), # Sat → Sun
}

# New date to add (April 2027)
new_event_date = (2027, 4, 11)

print("=" * 60)
print("Fixing Greenwich Walk Dates - Direct Database Update")
print("=" * 60)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Show current Greenwich events
print("\nCurrent Greenwich events:")
print("-" * 60)
cursor.execute("SELECT id, walk_date, start_time FROM walk_event WHERE location_id = 'greenwich' ORDER BY walk_date")
events = cursor.fetchall()
for event in events:
    d = date.fromisoformat(event['walk_date'])
    print(f"  ID: {event['id'][:8]}... | {event['walk_date']} ({d.strftime('%A')}) | {event['start_time']}")
print("-" * 60)

updated_count = 0

# Update incorrect dates
for old_tuple, new_tuple in date_corrections.items():
    old_date_str = f"{old_tuple[0]:04d}-{old_tuple[1]:02d}-{old_tuple[2]:02d}"
    new_date_str = f"{new_tuple[0]:04d}-{new_tuple[1]:02d}-{new_tuple[2]:02d}"
    
    # Check if old date exists
    cursor.execute("SELECT id FROM walk_event WHERE location_id = 'greenwich' AND walk_date = ?", (old_date_str,))
    existing = cursor.fetchone()
    
    if existing:
        # Check if new date already exists (avoid duplicates)
        cursor.execute("SELECT id FROM walk_event WHERE location_id = 'greenwich' AND walk_date = ?", (new_date_str,))
        new_exists = cursor.fetchone()
        
        if new_exists:
            print(f"⚠️  Skipping {old_date_str} → {new_date_str} (target already exists)")
        else:
            cursor.execute(
                "UPDATE walk_event SET walk_date = ? WHERE location_id = 'greenwich' AND walk_date = ?",
                (new_date_str, old_date_str)
            )
            old_d = date(*old_tuple)
            new_d = date(*new_tuple)
            print(f"✅ Updated: {old_date_str} ({old_d.strftime('%A')}) → {new_date_str} ({new_d.strftime('%A')})")
            updated_count += 1

# Check if April 2027 exists
new_date_str = f"{new_event_date[0]:04d}-{new_event_date[1]:02d}-{new_event_date[2]:02d}"
cursor.execute("SELECT id FROM walk_event WHERE location_id = 'greenwich' AND walk_date = ?", (new_date_str,))
april_exists = cursor.fetchone()

if not april_exists:
    print(f"\n➕ Adding new event: {new_date_str} (Sunday)")
    cursor.execute("""
        INSERT INTO walk_event (id, location_id, walk_date, start_time, end_time, meeting_point, max_participants, status, is_advertised, is_archived)
        VALUES (lower(hex(randomblob(18))), 'greenwich', ?, '11:10', '13:10', 'Route to be confirmed - details will be sent upon registration', 20, 'open', 0, 0)
    """, (new_date_str,))
    updated_count += 1
else:
    print(f"\n✓  April 2027 event already exists")

# Commit changes
if updated_count > 0:
    conn.commit()
    print(f"\n{'=' * 60}")
    print(f"✅ Successfully updated {updated_count} event(s)")
    print(f"{'=' * 60}")
else:
    print(f"\n{'=' * 60}")
    print("ℹ️  No changes needed")
    print(f"{'=' * 60}")

# Show final list
print("\nFinal Greenwich event dates:")
print("-" * 60)
cursor.execute("SELECT walk_date FROM walk_event WHERE location_id = 'greenwich' ORDER BY walk_date")
final_events = cursor.fetchall()
for event in final_events:
    d = date.fromisoformat(event['walk_date'])
    print(f"  {event['walk_date']} ({d.strftime('%A')})")
print("-" * 60)

# Verify registration counts are unchanged
print("\nRegistration counts (should be unchanged):")
print("-" * 60)
cursor.execute("""
    SELECT w.walk_date, COUNT(r.id) as reg_count 
    FROM walk_event w 
    LEFT JOIN registration r ON w.id = r.event_id AND r.cancelled_at IS NULL
    WHERE w.location_id = 'greenwich'
    GROUP BY w.id
    ORDER BY w.walk_date
""")
for row in cursor.fetchall():
    d = date.fromisoformat(row['walk_date'])
    print(f"  {row['walk_date']} ({d.strftime('%A')}) | {row['reg_count']} registration(s)")
print("-" * 60)

conn.close()
print("\n✅ All done! Registration data is preserved.")
