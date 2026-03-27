from app import app
with app.app_context():
    from app import WalkEvent, Registration
    # Test getting a location
    event = WalkEvent.query.first()
    if event:
        print(f"Event found: {event.location_id}")
        print(f"Registered count: {event.registered_count}")
    else:
        print("No events found")
