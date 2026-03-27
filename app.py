"""
Strolling with Neurokin (SwN) - Registration System
London Autism Group Charity
"""

from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta, date
from functools import wraps
import secrets
import os
import uuid
import smtplib
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from ics import Calendar, Event as ICSEvent
from ics.alarm import DisplayAlarm

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(16))

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///swn_bookings.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Email configuration
app.config['SMTP_HOST'] = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
app.config['SMTP_PORT'] = int(os.environ.get('SMTP_PORT', 587))
app.config['SMTP_USER'] = os.environ.get('SMTP_USER', '')
app.config['SMTP_PASSWORD'] = os.environ.get('SMTP_PASSWORD', '')
app.config['SMTP_FROM'] = os.environ.get('SMTP_FROM', 'bookings@example.com')
app.config['ENABLE_EMAIL'] = os.environ.get('ENABLE_EMAIL', 'false').lower() == 'true'

# Admin password
app.config['ADMIN_PASSWORD'] = os.environ.get('ADMIN_PASSWORD', 'Moonlight')

# Admin notification email
app.config['ADMIN_EMAIL'] = 'londonautismgroupcharity@gmail.com'

db = SQLAlchemy(app)

# ============================================================================
# WALK LOCATIONS CONFIGURATION
# ============================================================================

WALK_LOCATIONS = [
    {
        'id': 'city-of-london',
        'name': 'City of London',
        'description': 'Explore the historic heart of London with its iconic architecture, hidden gardens, and fascinating history. A gentle stroll through centuries of stories.',
        'facilitator': 'Hazel East',
        'color': 'bg-purple-600',
        'text_color': 'text-white',
    },
    {
        'id': 'ealing',
        'name': 'Ealing',
        'description': 'Discover the leafy borough of Ealing with its beautiful parks, tree-lined streets, and charming neighbourhoods. Perfect for a relaxed afternoon stroll.',
        'facilitator': 'Zara Salih',
        'color': 'bg-teal-500',
        'text_color': 'text-white',
    },
    {
        'id': 'greenwich',
        'name': 'Greenwich',
        'description': 'Wander through maritime history and stunning Royal Park views. From the Observatory to the Thames, experience Greenwich at a gentle pace.',
        'facilitator': 'Eoin Little',
        'color': 'bg-pink-400',
        'text_color': 'text-gray-900',
    },
]

# ============================================================================
# DATABASE MODELS
# ============================================================================

class WalkEvent(db.Model):
    """Available walk events"""
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    location_id = db.Column(db.String(50), nullable=False)
    walk_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.String(10), nullable=False)
    end_time = db.Column(db.String(10), nullable=False)
    meeting_point = db.Column(db.Text, nullable=False)
    max_participants = db.Column(db.Integer, default=20)
    status = db.Column(db.String(20), default='open')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Walk details (for group leaders to fill in)
    meet_when_where = db.Column(db.Text, nullable=True)  # When and where to meet
    route_description = db.Column(db.Text, nullable=True)  # Description of route and sights
    break_plan = db.Column(db.Text, nullable=True)  # Plan for break midway
    finish_details = db.Column(db.Text, nullable=True)  # When and where it finishes
    visual_story_url = db.Column(db.String(500), nullable=True)  # Link to visual story (optional)
    
    @property
    def full_description(self):
        """Generate full description from walk details"""
        parts = []
        if self.meet_when_where:
            parts.append(f"MEETING POINT:\n{self.meet_when_where}")
        if self.route_description:
            parts.append(f"\nTHE ROUTE:\n{self.route_description}")
        if self.break_plan:
            parts.append(f"\nBREAK:\n{self.break_plan}")
        if self.finish_details:
            parts.append(f"\nFINISH:\n{self.finish_details}")
        
        if parts:
            return "\n\n".join(parts)
        return self.meeting_point  # Fallback to default meeting point

    @property
    def registered_count(self):
        return Registration.query.filter_by(event_id=self.id, cancelled_at=None).count()
    
    @property
    def is_full(self):
        return self.registered_count >= self.max_participants

class Registration(db.Model):
    """Walk registrations"""
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = db.Column(db.String(36), db.ForeignKey('walk_event.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    
    # Accessibility and dietary
    access_needs = db.Column(db.Text, nullable=True)
    dietary_needs = db.Column(db.Text, nullable=True)
    
    # Additional info
    attending_with = db.Column(db.Text, nullable=True)
    additional_info = db.Column(db.Text, nullable=True)
    
    # WhatsApp consent
    whatsapp_consent = db.Column(db.Boolean, default=False)
    
    # Cancel token for self-service cancellation
    cancel_token = db.Column(db.String(64), unique=True, nullable=False, default=lambda: secrets.token_urlsafe(32))
    
    # Tracking
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    
    event = db.relationship('WalkEvent', backref='registrations')

# ============================================================================
# EMAIL FUNCTIONS
# ============================================================================

def send_email(to_email, subject, body, html_body=None, calendar_ics=None):
    """Send an email notification with optional calendar attachment"""
    if not app.config['ENABLE_EMAIL']:
        print(f"[EMAIL DISABLED] Would send to {to_email}: {subject}")
        return True
    
    try:
        # Create outer multipart/mixed for attachments
        msg = MIMEMultipart('mixed')
        msg['Subject'] = subject
        msg['From'] = app.config['SMTP_FROM']
        msg['To'] = to_email
        
        # Create inner multipart/alternative for text/html
        msg_alt = MIMEMultipart('alternative')
        msg.attach(msg_alt)
        
        # Add plain text part
        msg_alt.attach(MIMEText(body, 'plain'))
        
        # Add HTML part if provided
        if html_body:
            msg_alt.attach(MIMEText(html_body, 'html'))
        
        # Add calendar attachment if provided
        if calendar_ics:
            from email.mime.base import MIMEBase
            from email import encoders
            
            part = MIMEBase('text', 'calendar', method='REQUEST', name='event.ics')
            part.set_payload(calendar_ics.encode('utf-8'))
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', 'attachment; filename="event.ics"')
            part.add_header('Content-Class', 'urn:content-classes:calendarmessage')
            msg.attach(part)
        
        with smtplib.SMTP(app.config['SMTP_HOST'], app.config['SMTP_PORT']) as server:
            server.starttls()
            server.login(app.config['SMTP_USER'], app.config['SMTP_PASSWORD'])
            server.send_message(msg)
        
        return True
    except Exception as e:
        print(f"[ERROR] Failed to send email: {e}")
        return False

def generate_calendar_invite(event, location, registration, is_update=False):
    """Generate a Google Calendar (.ics) invite for a walk"""
    try:
        import traceback
        from ics import Calendar, Event as ICSEvent
        from ics.alarm import DisplayAlarm
        
        # Create calendar
        cal = Calendar()
        
        # Create event
        ics_event = ICSEvent()
        
        # Set event name
        status_prefix = "UPDATED: " if is_update else ""
        ics_event.name = f"{status_prefix}Strolling with Neurokin - {location['name']}"
        
        # Set description
        description_parts = [
            f"Strolling with Neurokin walk in {location['name']}",
            f"",
            f"Walk Leader: {location['facilitator']}",
            f"",
        ]
        
        # Add walk details if available - prioritize detailed fields, fall back to meeting_point
        meeting_info = event.meet_when_where or event.meeting_point
        if meeting_info and meeting_info != "TBC":
            description_parts.append("MEETING:")
            description_parts.append(meeting_info)
            description_parts.append("")
        
        if event.route_description:
            description_parts.append("ROUTE:")
            description_parts.append(event.route_description)
            description_parts.append("")
        
        if event.break_plan:
            description_parts.append("BREAK:")
            description_parts.append(event.break_plan)
            description_parts.append("")
        
        if event.finish_details:
            description_parts.append("FINISH:")
            description_parts.append(event.finish_details)
            description_parts.append("")
        
        # Add visual story link if available
        if event.visual_story_url:
            description_parts.append("VISUAL STORY:")
            description_parts.append(event.visual_story_url)
            description_parts.append("")
        
        # If no detailed info available yet, add a note
        if not meeting_info or meeting_info == "TBC":
            description_parts.append("NOTE:")
            description_parts.append("Detailed walk information will be sent closer to the date.")
            description_parts.append("")
        
        # Add what to bring
        description_parts.append("WHAT TO BRING:")
        description_parts.append("- Comfortable footwear")
        description_parts.append("- Water bottle")
        description_parts.append("- Weather-appropriate clothing")
        description_parts.append("- Money for breaktime drinks/snacks")
        description_parts.append("- Phone (for WhatsApp group)")
        
        ics_event.description = "\n".join(description_parts)
        
        # Set location (use meeting point or location name)
        if event.meet_when_where:
            # Try to extract location from meeting details
            ics_event.location = event.meet_when_where.split('\n')[0][:200]  # First line, max 200 chars
        else:
            ics_event.location = f"{location['name']}, London"
        
        # Set start and end times with timezone
        from datetime import timezone
        year = event.walk_date.year
        month = event.walk_date.month
        day = event.walk_date.day
        
        # Parse start time
        start_hour, start_minute = map(int, event.start_time.split(':'))
        start_dt = datetime(year, month, day, start_hour, start_minute, 0, tzinfo=timezone.utc)
        ics_event.begin = start_dt
        
        # Parse end time
        end_hour, end_minute = map(int, event.end_time.split(':'))
        end_dt = datetime(year, month, day, end_hour, end_minute, 0, tzinfo=timezone.utc)
        ics_event.end = end_dt
        
        # Add reminder (1 day before)
        alarm = DisplayAlarm(trigger=timedelta(days=-1))
        alarm.description = "Strolling with Neurokin walk tomorrow!"
        ics_event.alarms.append(alarm)
        
        # Add another reminder (1 hour before)
        alarm2 = DisplayAlarm(trigger=timedelta(hours=-1))
        alarm2.description = "Walk starts in 1 hour!"
        ics_event.alarms.append(alarm2)
        
        # Set UID for updates
        ics_event.uid = f"swn-walk-{event.id}-{registration.id}@swn-londonautismgroupcharity.pythonanywhere.com"
        
        # Add to calendar
        cal.events.add(ics_event)
        
        calendar_string = cal.serialize()
        print(f"[INFO] Generated calendar invite for {registration.name} - {event.walk_date}")
        return calendar_string
    except Exception as e:
        print(f"[ERROR] Failed to generate calendar invite: {e}")
        traceback.print_exc()
        return None

def send_registration_confirmation(registration):
    """Send confirmation email to registrant"""
    location = next((l for l in WALK_LOCATIONS if l['id'] == registration.event.location_id), None)
    
    subject = f"Strolling with Neurokin - Registration Confirmed ({location['name']})"
    
    cancel_url = url_for('cancel_registration', token=registration.cancel_token, _external=True)
    my_bookings_url = url_for('my_bookings', _external=True)
    
    body = f"""Hello {registration.name},

Thank you for registering for the Strolling with Neurokin walk!

WALK DETAILS:
Location: {location['name']}
Date: {registration.event.walk_date.strftime('%A, %d %B %Y')}
Time: {registration.event.start_time} - {registration.event.end_time}
Meeting Point: {registration.event.meeting_point}
Walk Leader: {location['facilitator']}

WHAT TO BRING:
- Comfortable footwear
- Water bottle
- Weather-appropriate clothing
- Money for breaktime drinks/snacks
- Phone (for WhatsApp group if you consented)

MANAGE YOUR BOOKING:
You can view or cancel your booking at any time:
{my_bookings_url}

📅 A calendar invite is attached to this email. Please add it to your calendar so you don't miss the walk!

To cancel this specific registration, use this link:
{cancel_url}

If you have any questions, please reply to this email or contact us at londonautismgroupcharity@gmail.com

We look forward to seeing you there!

Best regards,
Strolling with Neurokin Team
London Autism Group Charity
"""

    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2 style="color: #6B46C1;">Hello {registration.name},</h2>
        
        <p>Thank you for registering for the <strong>Strolling with Neurokin</strong> walk!</p>
        
        <div style="background: #f5f5f5; padding: 15px; border-radius: 8px; margin: 20px 0;">
            <h3 style="color: #6B46C1; margin-top: 0;">WALK DETAILS</h3>
            <p><strong>Location:</strong> {location['name']}</p>
            <p><strong>Date:</strong> {registration.event.walk_date.strftime('%A, %d %B %Y')}</p>
            <p><strong>Time:</strong> {registration.event.start_time} - {registration.event.end_time}</p>
            <p><strong>Meeting Point:</strong> {registration.event.meeting_point}</p>
            <p><strong>Walk Leader:</strong> {location['facilitator']}</p>
        </div>
        
        <h3 style="color: #6B46C1;">WHAT TO BRING</h3>
        <ul>
            <li>Comfortable footwear</li>
            <li>Water bottle</li>
            <li>Weather-appropriate clothing</li>
            <li>Money for breaktime drinks/snacks</li>
            <li>Phone (for WhatsApp group if you consented)</li>
        </ul>
        
        <div style="background: #f0f9ff; padding: 15px; border-radius: 8px; margin: 20px 0;">
            <h3 style="color: #0369a1; margin-top: 0;">MANAGE YOUR BOOKING</h3>
            <p>You can view or cancel your booking at any time:</p>
            <a href="{my_bookings_url}" style="display: inline-block; background: #6B46C1; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">View My Bookings</a>
        </div>
        
        <div style="background: #f5f5f5; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #6B46C1;">
            <p style="margin: 0;"><strong>📅 Calendar invite attached.</strong> Please add it to your calendar so you don't miss the walk!</p>
        </div>
        
        <p style="margin-top: 30px;">
            <a href="{cancel_url}" style="color: #999;">Cancel this registration</a>
        </p>
        
        <p>If you have any questions, please reply to this email or contact us at <a href="mailto:londonautismgroupcharity@gmail.com">londonautismgroupcharity@gmail.com</a></p>
        
        <p>We look forward to seeing you there!</p>
        
        <p>Best regards,<br>
        <strong>Strolling with Neurokin Team</strong><br>
        London Autism Group Charity</p>
    </body>
    </html>
    """
    
    # Generate calendar invite
    calendar_ics = generate_calendar_invite(registration.event, location, registration, is_update=False)
    
    return send_email(registration.email, subject, body, html_body, calendar_ics=calendar_ics)

def send_admin_notification(registration, event_type='new'):
    """Send notification to admin when someone registers or cancels"""
    location = next((l for l in WALK_LOCATIONS if l['id'] == registration.event.location_id), None)
    
    if event_type == 'new':
        subject = f"New SwN Registration - {location['name']} ({registration.event.walk_date.strftime('%d %b')})"
        body = f"""A new registration has been received:

Name: {registration.name}
Email: {registration.email}
Phone: {registration.phone}
Location: {location['name']}
Date: {registration.event.walk_date.strftime('%A, %d %B %Y')}
Time: {registration.event.start_time} - {registration.event.end_time}
Walk Leader: {location['facilitator']}

Attending with: {registration.attending_with or 'N/A'}
Access needs: {registration.access_needs or 'None'}
Dietary needs: {registration.dietary_needs or 'None'}
WhatsApp consent: {'Yes' if registration.whatsapp_consent else 'No'}
Additional info: {registration.additional_info or 'None'}

Total registered for this walk: {registration.event.registered_count}

View admin dashboard:
https://swn-londonautismgroupcharity.pythonanywhere.com/admin
"""
    else:  # cancelled
        subject = f"Cancelled SwN Registration - {location['name']} ({registration.event.walk_date.strftime('%d %b')})"
        body = f"""A registration has been cancelled:

Name: {registration.name}
Email: {registration.email}
Location: {location['name']}
Date: {registration.event.walk_date.strftime('%A, %d %B %Y')}

Total now registered for this walk: {registration.event.registered_count}

View admin dashboard:
https://swn-londonautismgroupcharity.pythonanywhere.com/admin
"""
    
    return send_email(app.config['ADMIN_EMAIL'], subject, body)

def send_admin_cancellation_notification(registration, admin_note=''):
    """Send notification to user when admin cancels their registration"""
    location = next((l for l in WALK_LOCATIONS if l['id'] == registration.event.location_id), None)
    
    subject = f"Strolling with Neurokin - Registration Cancelled ({location['name']})"
    
    my_bookings_url = url_for('my_bookings', _external=True)
    
    note_section = f"\nAdditional note: {admin_note}\n" if admin_note else ""
    
    body = f"""Hello {registration.name},

Your registration for the Strolling with Neurokin walk has been cancelled by the walk leader.

CANCELLED REGISTRATION:
Location: {location['name']}
Date: {registration.event.walk_date.strftime('%A, %d %B %Y')}
Time: {registration.event.start_time} - {registration.event.end_time}
Walk Leader: {location['facilitator']}
{note_section}
If you believe this was cancelled in error, or if you have any questions, please contact us at londonautismgroupcharity@gmail.com

You can view your other bookings at:
{my_bookings_url}

Best regards,
Strolling with Neurokin Team
London Autism Group Charity
"""
    
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2 style="color: #6B46C1;">Hello {registration.name},</h2>
        
        <p>Your registration for the <strong>Strolling with Neurokin</strong> walk has been <strong>cancelled</strong> by the walk leader.</p>
        
        <div style="background: #fef2f2; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #dc2626;">
            <h3 style="color: #dc2626; margin-top: 0;">CANCELLED REGISTRATION</h3>
            <p><strong>Location:</strong> {location['name']}</p>
            <p><strong>Date:</strong> {registration.event.walk_date.strftime('%A, %d %B %Y')}</p>
            <p><strong>Time:</strong> {registration.event.start_time} - {registration.event.end_time}</p>
            <p><strong>Walk Leader:</strong> {location['facilitator']}</p>
            {f"<p style='margin-top: 10px;'><strong>Additional note:</strong> {admin_note}</p>" if admin_note else ""}
        </div>
        
        <p>If you believe this was cancelled in error, or if you have any questions, please contact us at <a href="mailto:londonautismgroupcharity@gmail.com">londonautismgroupcharity@gmail.com</a></p>
        
        <div style="background: #e8f5e9; padding: 15px; border-radius: 8px; margin: 20px 0;">
            <h3 style="color: #2e7d32; margin-top: 0;">VIEW YOUR OTHER BOOKINGS</h3>
            <a href="{my_bookings_url}" style="display: inline-block; background: #6B46C1; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">My Bookings</a>
        </div>
        
        <p>Best regards,<br>
        <strong>Strolling with Neurokin Team</strong><br>
        London Autism Group Charity</p>
    </body>
    </html>
    """
    
    return send_email(registration.email, subject, body, html_body)

def send_update_notifications(event, updated_fields):
    """Send updated calendar invites to all registered participants when walk details change"""
    location = next((l for l in WALK_LOCATIONS if l['id'] == event.location_id), None)
    if not location:
        return
    
    # Get all active registrations
    registrations = Registration.query.filter_by(
        event_id=event.id, 
        cancelled_at=None
    ).all()
    
    if not registrations:
        return
    
    # Build a summary of what was updated
    updates_summary = []
    if 'meet_when_where' in updated_fields:
        updates_summary.append("Meeting point details")
    if 'route_description' in updated_fields:
        updates_summary.append("Route description")
    if 'break_plan' in updated_fields:
        updates_summary.append("Break plan")
    if 'finish_details' in updated_fields:
        updates_summary.append("Finish details")
    if 'visual_story_url' in updated_fields:
        updates_summary.append("Visual story link")
    
    if not updates_summary:
        updates_summary.append("Walk details")
    
    updates_text = ", ".join(updates_summary)
    
    subject = f"UPDATED: Strolling with Neurokin Walk Details - {location['name']}"
    
    success_count = 0
    fail_count = 0
    
    for registration in registrations:
        body = f"""Hello {registration.name},

The walk details for your upcoming Strolling with Neurokin walk have been updated.

WALK DETAILS:
Location: {location['name']}
Date: {event.walk_date.strftime('%A, %d %B %Y')}
Time: {event.start_time} - {event.end_time}
Walk Leader: {location['facilitator']}

UPDATED INFORMATION:
{updates_text}

A new calendar invite with the updated details is attached to this email. Please save it to your calendar to replace the previous version.

To view or cancel your booking:
https://swn-londonautismgroupcharity.pythonanywhere.com/my-bookings

If you have any questions, please reply to this email or contact us at londonautismgroupcharity@gmail.com

Best regards,
Strolling with Neurokin Team
London Autism Group Charity
"""
        
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2 style="color: #6B46C1;">Hello {registration.name},</h2>
            
            <p>The walk details for your upcoming <strong>Strolling with Neurokin</strong> walk have been updated.</p>
            
            <div style="background: #f5f5f5; padding: 15px; border-radius: 8px; margin: 20px 0;">
                <h3 style="color: #6B46C1; margin-top: 0;">WALK DETAILS</h3>
                <p><strong>Location:</strong> {location['name']}</p>
                <p><strong>Date:</strong> {event.walk_date.strftime('%A, %d %B %Y')}</p>
                <p><strong>Time:</strong> {event.start_time} - {event.end_time}</p>
                <p><strong>Walk Leader:</strong> {location['facilitator']}</p>
            </div>
            
            <div style="background: #fff3e0; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #ff9800;">
                <h3 style="color: #e65100; margin-top: 0;">UPDATED INFORMATION</h3>
                <p>{updates_text}</p>
            </div>
            
            <p>A new calendar invite with the updated details is <strong>attached to this email</strong>. Please save it to your calendar to replace the previous version.</p>
            
            <div style="background: #e8f5e9; padding: 15px; border-radius: 8px; margin: 20px 0;">
                <h3 style="color: #2e7d32; margin-top: 0;">MANAGE YOUR BOOKING</h3>
                <p>You can view or cancel your booking at any time:</p>
                <a href="https://swn-londonautismgroupcharity.pythonanywhere.com/my-bookings" style="display: inline-block; background: #6B46C1; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">View My Bookings</a>
            </div>
            
            <p>If you have any questions, please reply to this email or contact us at <a href="mailto:londonautismgroupcharity@gmail.com">londonautismgroupcharity@gmail.com</a></p>
            
            <p>Best regards,<br>
            <strong>Strolling with Neurokin Team</strong><br>
            London Autism Group Charity</p>
        </body>
        </html>
        """
        
        # Generate updated calendar invite
        calendar_ics = generate_calendar_invite(event, location, registration, is_update=True)
        
        if send_email(registration.email, subject, body, html_body, calendar_ics=calendar_ics):
            success_count += 1
        else:
            fail_count += 1
    
    print(f"[INFO] Update notifications sent: {success_count} successful, {fail_count} failed")

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def init_events():
    """Initialize walk events if none exist"""
    if WalkEvent.query.first() is None:
        # Greenwich sessions - 2nd Sunday of every month starting May 2026
        greenwich_dates = [
            ('2026-05-10', '11:10', '13:10', "St Alfege's Church (Greenwich Church St, London SE10 8NA). Arrive from 10:50am for an 11:10am departure. The walk goes towards the O2 via Greenwich town centre, Cutty Sark and Old Royal Naval College. Route is wheelchair accessible with one small cobbled section and a ramped footbridge over Blackwall Tunnel approach (can be noisy - bring ear defenders if sound-sensitive). The walk finishes at Charlton Station between 1:10pm-1:30pm, with option to leave earlier at North Greenwich (O2) if preferred."),
            ('2026-06-13', '11:10', '13:10', 'Route to be confirmed - details will be sent upon registration'),
            ('2026-07-11', '11:10', '13:10', 'Route to be confirmed - details will be sent upon registration'),
            ('2026-08-08', '11:10', '13:10', 'Route to be confirmed - details will be sent upon registration'),
            ('2026-09-12', '11:10', '13:10', 'Route to be confirmed - details will be sent upon registration'),
            ('2026-10-10', '11:10', '13:10', 'Route to be confirmed - details will be sent upon registration'),
            ('2026-11-08', '11:10', '13:10', 'Route to be confirmed - details will be sent upon registration'),
            ('2026-12-13', '11:10', '13:10', 'Route to be confirmed - details will be sent upon registration'),
            ('2027-01-10', '11:10', '13:10', 'Route to be confirmed - details will be sent upon registration'),
            ('2027-02-14', '11:10', '13:10', 'Route to be confirmed - details will be sent upon registration'),
            ('2027-03-14', '11:10', '13:10', 'Route to be confirmed - details will be sent upon registration'),
            ('2027-04-10', '11:10', '13:10', 'Route to be confirmed - details will be sent upon registration'),
        ]
        
        for date_str, start, end, meeting in greenwich_dates:
            year, month, day = map(int, date_str.split('-'))
            event = WalkEvent(
                location_id='greenwich',
                walk_date=date(year, month, day),
                start_time=start,
                end_time=end,
                meeting_point=meeting,
                max_participants=20
            )
            db.session.add(event)
        
        # City of London sessions - 1st Sunday of every month starting May 2026
        city_dates = [
            '2026-05-03', '2026-06-06', '2026-07-04', '2026-08-01',
            '2026-09-05', '2026-10-03', '2026-11-01', '2026-12-06',
            '2027-01-03', '2027-02-07', '2027-03-07', '2027-04-03'
        ]
        
        for date_str in city_dates:
            year, month, day = map(int, date_str.split('-'))
            event = WalkEvent(
                location_id='city-of-london',
                walk_date=date(year, month, day),
                start_time='13:30',
                end_time='15:30',
                meeting_point='To be confirmed upon registration',
                max_participants=20
            )
            db.session.add(event)
        
        # Ealing sessions - specific dates
        ealing_dates = [
            ('2026-05-16', False),
            ('2026-06-20', False),
            ('2026-07-18', True),
            ('2026-08-15', True),
            ('2026-09-19', False),
        ]
        
        for date_str, tbc in ealing_dates:
            year, month, day = map(int, date_str.split('-'))
            meeting = 'To be confirmed (TBC)' if tbc else 'To be confirmed upon registration'
            event = WalkEvent(
                location_id='ealing',
                walk_date=date(year, month, day),
                start_time='14:00',
                end_time='16:00',
                meeting_point=meeting,
                max_participants=20
            )
            db.session.add(event)
        
        db.session.commit()
        print("Events initialized!")

def admin_required(f):
    """Decorator to require admin login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# ============================================================================
# ROUTES
# ============================================================================

@app.route('/')
def landing():
    """Home page"""
    return render_template('landing.html', locations=WALK_LOCATIONS)

@app.route('/location/<location_id>')
def location(location_id):
    """Location detail page"""
    location = next((l for l in WALK_LOCATIONS if l['id'] == location_id), None)
    if not location:
        return "Location not found", 404
    
    today = date.today()
    
    # Get upcoming events for this location (limit to first 2)
    events = WalkEvent.query.filter(
        WalkEvent.location_id == location_id,
        WalkEvent.walk_date >= today,
        WalkEvent.status != 'closed'
    ).order_by(WalkEvent.walk_date).limit(2).all()
    
    selected_event_id = request.args.get('event')
    selected_event = None
    if selected_event_id:
        selected_event = WalkEvent.query.get(selected_event_id)
    
    return render_template(
        'location.html',
        location=location,
        events=events,
        selected_event=selected_event
    )

@app.route('/register/<event_id>', methods=['POST'])
def register(event_id):
    """Handle registration"""
    event = WalkEvent.query.get_or_404(event_id)
    
    # Check if event is full
    if event.is_full:
        flash('This walk is fully booked', 'error')
        return redirect(url_for('location', location_id=event.location_id))
    
    # Check if email already registered for this event
    email = request.form.get('email')
    existing = Registration.query.filter_by(event_id=event_id, email=email, cancelled_at=None).first()
    if existing:
        flash('You have already registered for this walk with this email address', 'error')
        return redirect(url_for('location', location_id=event.location_id, event=event_id))
    
    # Create registration
    registration = Registration(
        event_id=event_id,
        name=request.form.get('name'),
        email=email,
        phone=request.form.get('phone'),
        access_needs=request.form.get('access_needs'),
        dietary_needs=request.form.get('dietary_needs'),
        attending_with=request.form.get('attending_with'),
        additional_info=request.form.get('additional_info'),
        whatsapp_consent=request.form.get('whatsapp_consent') == 'true'
    )
    
    db.session.add(registration)
    db.session.commit()
    
    # Update event status if now full
    if event.is_full:
        event.status = 'full'
        db.session.commit()
    
    # Send confirmation emails
    send_registration_confirmation(registration)
    send_admin_notification(registration, 'new')
    
    flash('Registration successful! Check your email for confirmation.', 'success')
    return redirect(url_for('success', registration_id=registration.id))

@app.route('/success/<registration_id>')
def success(registration_id):
    """Registration success page"""
    registration = Registration.query.get_or_404(registration_id)
    return render_template('success.html', registration=registration)

@app.route('/about')
def about():
    """About page"""
    return render_template('about.html', locations=WALK_LOCATIONS)

# ============================================================================
# MY BOOKINGS ROUTES
# ============================================================================

@app.route('/my-bookings', methods=['GET', 'POST'])
def my_bookings():
    """View and manage my bookings"""
    bookings = []
    email = ''
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        if email:
            # Get upcoming registrations for this email
            bookings = Registration.query.join(WalkEvent).filter(
                Registration.email == email,
                Registration.cancelled_at.is_(None),
                WalkEvent.walk_date >= date.today()
            ).order_by(WalkEvent.walk_date).all()
    
    return render_template('my_bookings.html', bookings=bookings, email=email, locations=WALK_LOCATIONS)

@app.route('/cancel/<token>')
def cancel_registration(token):
    """Cancel a registration using the cancel token"""
    registration = Registration.query.filter_by(cancel_token=token).first()
    
    if not registration:
        flash('Registration not found', 'error')
        return redirect(url_for('landing'))
    
    if registration.cancelled_at:
        flash('This registration has already been cancelled', 'error')
        return redirect(url_for('landing'))
    
    # Mark as cancelled
    registration.cancelled_at = datetime.utcnow()
    
    # Update event status if it was full
    if registration.event.status == 'full':
        registration.event.status = 'open'
    
    db.session.commit()
    
    # Send admin notification
    send_admin_notification(registration, 'cancelled')
    
    flash('Your registration has been cancelled successfully', 'success')
    return redirect(url_for('landing'))

# ============================================================================
# ADMIN ROUTES
# ============================================================================

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    """Admin login"""
    if request.method == 'POST':
        password = request.form.get('password')
        if password == app.config['ADMIN_PASSWORD']:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Incorrect password', 'error')
    
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    """Admin dashboard"""
    today = date.today()
    
    # Get stats (only count non-cancelled registrations)
    total_events = WalkEvent.query.count()
    upcoming_events = WalkEvent.query.filter(WalkEvent.walk_date >= today).count()
    total_registrations = Registration.query.filter(Registration.cancelled_at.is_(None)).count()
    
    # Get all events
    events = WalkEvent.query.order_by(WalkEvent.walk_date).all()
    
    # Get all registrations (excluding cancelled)
    registrations = Registration.query.filter(Registration.cancelled_at.is_(None)).join(WalkEvent).order_by(
        WalkEvent.walk_date.desc(),
        Registration.created_at.desc()
    ).all()
    
    # Group registrations by event (for walk leader view)
    from collections import OrderedDict
    registrations_by_event = OrderedDict()
    for reg in registrations:
        event_id = reg.event.id
        if event_id not in registrations_by_event:
            registrations_by_event[event_id] = {
                'event': reg.event,
                'location': next((l for l in WALK_LOCATIONS if l['id'] == reg.event.location_id), None),
                'registrations': []
            }
        registrations_by_event[event_id]['registrations'].append(reg)
    
    return render_template(
        'admin.html',
        locations=WALK_LOCATIONS,
        events=events,
        registrations=registrations,
        registrations_by_event=registrations_by_event,
        stats={
            'total_events': total_events,
            'upcoming_events': upcoming_events,
            'total_registrations': total_registrations,
            'locations': len(WALK_LOCATIONS)
        }
    )

@app.route('/admin/logout')
def admin_logout():
    """Admin logout"""
    session.pop('admin_logged_in', None)
    return redirect(url_for('landing'))

@app.route('/admin/edit-walk/<event_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_walk(event_id):
    """Edit walk details (for group leaders)"""
    event = WalkEvent.query.get_or_404(event_id)
    location = next((l for l in WALK_LOCATIONS if l['id'] == event.location_id), None)
    
    if request.method == 'POST':
        # Track which fields changed
        updated_fields = []
        
        new_meet_when_where = request.form.get('meet_when_where')
        new_route_description = request.form.get('route_description')
        new_break_plan = request.form.get('break_plan')
        new_finish_details = request.form.get('finish_details')
        new_visual_story_url = request.form.get('visual_story_url')
        
        if new_meet_when_where != event.meet_when_where:
            updated_fields.append('meet_when_where')
            event.meet_when_where = new_meet_when_where
        
        if new_route_description != event.route_description:
            updated_fields.append('route_description')
            event.route_description = new_route_description
        
        if new_break_plan != event.break_plan:
            updated_fields.append('break_plan')
            event.break_plan = new_break_plan
        
        if new_finish_details != event.finish_details:
            updated_fields.append('finish_details')
            event.finish_details = new_finish_details
        
        if new_visual_story_url != event.visual_story_url:
            updated_fields.append('visual_story_url')
            event.visual_story_url = new_visual_story_url
        
        # Also update the meeting_point with the full description for display
        event.meeting_point = event.full_description
        
        db.session.commit()
        
        # Send update notifications if any details changed and there are registrations
        if updated_fields:
            # Run in background to not block the response
            import threading
            def send_updates():
                with app.app_context():
                    send_update_notifications(event, updated_fields)
            
            thread = threading.Thread(target=send_updates)
            thread.daemon = True
            thread.start()
            flash(f'Walk details updated successfully! Update notifications are being sent to {event.registered_count} registered participant(s).', 'success')
        else:
            flash('Walk details updated successfully!', 'success')
        
        return redirect(url_for('admin_dashboard'))
    
    return render_template(
        'admin_edit_walk.html',
        event=event,
        location=location
    )

@app.route('/admin/event/<event_id>/registrations')
@admin_required
def admin_event_registrations(event_id):
    """View registrations for a specific event"""
    event = WalkEvent.query.get_or_404(event_id)
    location = next((l for l in WALK_LOCATIONS if l['id'] == event.location_id), None)
    
    # Get all active registrations for this event
    registrations = Registration.query.filter_by(
        event_id=event.id,
        cancelled_at=None
    ).order_by(Registration.created_at.desc()).all()
    
    return render_template(
        'admin_event_registrations.html',
        event=event,
        location=location,
        registrations=registrations
    )

@app.route('/admin/event/<event_id>/registrations.csv')
@admin_required
def admin_event_registrations_csv(event_id):
    """Download registrations for a specific event as CSV"""
    import csv
    import io
    from flask import Response
    
    event = WalkEvent.query.get_or_404(event_id)
    location = next((l for l in WALK_LOCATIONS if l['id'] == event.location_id), None)
    
    # Get all active registrations for this event
    registrations = Registration.query.filter_by(
        event_id=event.id,
        cancelled_at=None
    ).order_by(Registration.created_at.desc()).all()
    
    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header row
    writer.writerow([
        'Name', 'Email', 'Phone', 'Attending With', 
        'Access Needs', 'Dietary Needs', 'Additional Info',
        'WhatsApp Consent', 'Registered At'
    ])
    
    # Data rows
    for reg in registrations:
        writer.writerow([
            reg.name,
            reg.email,
            reg.phone,
            reg.attending_with or '',
            reg.access_needs or '',
            reg.dietary_needs or '',
            reg.additional_info or '',
            'Yes' if reg.whatsapp_consent else 'No',
            reg.created_at.strftime('%Y-%m-%d %H:%M') if reg.created_at else ''
        ])
    
    # Generate filename
    filename = f"registrations-{location['id']}-{event.walk_date.strftime('%Y%m%d')}.csv"
    
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename={filename}'
        }
    )

@app.route('/admin/registration/<registration_id>/cancel', methods=['POST'])
@admin_required
def admin_cancel_registration(registration_id):
    """Cancel a registration by admin (walk leader)"""
    registration = Registration.query.get_or_404(registration_id)
    event = registration.event
    location = next((l for l in WALK_LOCATIONS if l['id'] == event.location_id), None)
    
    # Check if already cancelled
    if registration.cancelled_at:
        flash('This registration is already cancelled.', 'error')
        return redirect(url_for('admin_event_registrations', event_id=event.id))
    
    # Get optional admin note
    admin_note = request.form.get('admin_note', '').strip()
    
    # Cancel the registration
    registration.cancelled_at = datetime.utcnow()
    db.session.commit()
    
    # Send cancellation email to user
    try:
        send_admin_cancellation_notification(registration, admin_note)
        flash(f'Registration for {registration.name} has been cancelled and they have been notified by email.', 'success')
    except Exception as e:
        print(f"[ERROR] Failed to send cancellation email: {e}")
        flash(f'Registration cancelled but failed to send email notification: {e}', 'warning')
    
    # Also notify admin (the walk leader)
    try:
        send_admin_notification(registration, event_type='cancelled')
    except Exception as e:
        print(f"[ERROR] Failed to notify admin of cancellation: {e}")
    
    return redirect(url_for('admin_event_registrations', event_id=event.id))

# ============================================================================
# INITIALIZATION
# ============================================================================

with app.app_context():
    db.create_all()
    init_events()

if __name__ == '__main__':
    app.run(debug=True)
