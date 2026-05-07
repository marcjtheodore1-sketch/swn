#!/usr/bin/env python3
"""
Fix Greenwich walk dates in existing database
Updates incorrect dates to correct Sundays
"""

from datetime import date
from app import app, db, WalkEvent

# Map of old incorrect dates to new correct dates
# (keeping 10 May 2026 as is since it's correct)
date_corrections = {
    date(2026, 6, 13): date(2026, 6, 14),   # Sat → Sun
    date(2026, 7, 11): date(2026, 7, 12),   # Sat → Sun
    date(2026, 8, 8):  date(2026, 8, 9),    # Sat → Sun
    date(2026, 9, 12): date(2026, 9, 13),   # Sat → Sun
    date(2026, 10, 10): date(2026, 10, 11), # Sat → Sun
}

# New date to add (if not exists)
new_date = date(2027, 4, 11)

with app.app_context():
    print("=" * 60)
    print("Fixing Greenwich Walk Dates")
    print("=" * 60)
    
    # Get all Greenwich events
    greenwich_events = WalkEvent.query.filter_by(location_id='greenwich').order_by(WalkEvent.walk_date).all()
    
    print(f"\nFound {len(greenwich_events)} Greenwich events")
    print("-" * 60)
    
    updated_count = 0
    
    for event in greenwich_events:
        old_date = event.walk_date
        
        if old_date in date_corrections:
            new_date_corrected = date_corrections[old_date]
            
            # Check if the correct date already exists (to avoid duplicates)
            existing = WalkEvent.query.filter_by(
                location_id='greenwich',
                walk_date=new_date_corrected
            ).first()
            
            if existing:
                print(f"⚠️  Skipping {old_date} → {new_date_corrected} (target date already exists)")
                continue
            
            # Update the date
            print(f"✅ Updating: {old_date} ({old_date.strftime('%A')}) → {new_date_corrected} ({new_date_corrected.strftime('%A')})")
            event.walk_date = new_date_corrected
            updated_count += 1
        else:
            print(f"✓  Keeping: {old_date} ({old_date.strftime('%A')})")
    
    # Check if we need to add the April 2027 event
    april_2027 = WalkEvent.query.filter_by(
        location_id='greenwich',
        walk_date=new_date
    ).first()
    
    if not april_2027:
        print(f"\n➕ Adding new event: {new_date} ({new_date.strftime('%A')})")
        new_event = WalkEvent(
            location_id='greenwich',
            walk_date=new_date,
            start_time='11:10',
            end_time='13:10',
            meeting_point='Route to be confirmed - details will be sent upon registration',
            max_participants=20,
            is_advertised=False,
            is_archived=False
        )
        db.session.add(new_event)
        updated_count += 1
    else:
        print(f"\n✓  April 2027 event already exists")
    
    # Commit changes
    if updated_count > 0:
        db.session.commit()
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
    final_events = WalkEvent.query.filter_by(location_id='greenwich').order_by(WalkEvent.walk_date).all()
    for event in final_events:
        print(f"  {event.walk_date} ({event.walk_date.strftime('%A')})")
    print("-" * 60)
