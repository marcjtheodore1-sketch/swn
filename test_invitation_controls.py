"""Regression checks for attendance exclusions and reviewed invitation lists."""
import os
import tempfile
import unittest
from datetime import date
from unittest.mock import patch

_test_dir = tempfile.TemporaryDirectory()
os.environ['DATABASE_URL'] = f'sqlite:///{_test_dir.name}/invitations.db'
os.environ['ENABLE_EMAIL'] = 'false'

from app import app, db, WalkEvent, Registration, get_invite_recipients, purge_banned_attendee_data


class InvitationControlsTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, INVITE_TEST_MODE=False, ENABLE_EMAIL=True,
                          SMTP_USER='test', SMTP_PASSWORD='test', SMTP_FROM='test@example.com')
        with app.app_context():
            db.drop_all()
            db.create_all()
            past = WalkEvent(location_id='greenwich', walk_date=date(2026, 9, 13),
                             start_time='11:10', end_time='13:10', meeting_point='Test', is_advertised=True)
            future = WalkEvent(location_id='greenwich', walk_date=date(2026, 10, 11),
                               start_time='11:10', end_time='13:10', meeting_point='Test', is_advertised=True)
            db.session.add_all([past, future]); db.session.flush()
            self.target = future.id
            self.past = past.id
            for email in ('one@example.com', 'two@example.com', ' Salih.Zara@gmail.com ', 'ZARA.LAGC@gmail.com'):
                db.session.add(Registration(event_id=past.id, email=email, name='Test', phone='07000000000'))
            db.session.commit()
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session['admin_logged_in'] = True

    def payload(self, **overrides):
        value = {'audience': 'all', 'subject': 'Join us', 'body': 'Hello'}
        value.update(overrides)
        return value

    def test_purge_removes_both_addresses_and_preserves_everyone_else(self):
        with app.app_context():
            self.assertEqual(purge_banned_attendee_data(), 2)
            self.assertEqual(Registration.query.count(), 2)
            self.assertEqual(purge_banned_attendee_data(), 0)

    def test_preview_excludes_both_addresses_before_purge(self):
        response = self.client.get(f'/admin/event/{self.target}/invite-preview?audience=all')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['recipients'], ['one@example.com', 'two@example.com'])

    def test_banned_addresses_cannot_register_again(self):
        for email in (' Salih.Zara@gmail.com ', 'ZARA.LAGC@gmail.com'):
            response = self.client.post(f'/register/{self.target}', data={'email': email})
            self.assertEqual(response.status_code, 302)
        with app.app_context():
            self.assertEqual(Registration.query.filter_by(event_id=self.target).count(), 0)

    def test_banned_address_cannot_be_manually_added(self):
        with patch('app.smtplib.SMTP') as smtp:
            response = self.client.post(f'/admin/event/{self.target}/invite',
                                        json=self.payload(extra_emails=[' SALIH.ZARA@GMAIL.COM ']))
        self.assertEqual(response.status_code, 400)
        smtp.assert_not_called()

    def test_send_uses_only_the_reviewed_list(self):
        with patch('threading.Thread') as thread, patch('app.send_email_batch', create=True, return_value=(1, 0)) as batch:
            response = self.client.post(f'/admin/event/{self.target}/invite',
                                        json=self.payload(recipient_emails=[' ONE@EXAMPLE.COM ', 'unknown@example.com']))
        self.assertEqual(response.status_code, 200)
        if thread.called:
            self.assertEqual(thread.call_args.kwargs['args'][0], ['one@example.com'])
        else:
            self.assertEqual(batch.call_args.args[0], ['one@example.com'])

    def test_empty_reviewed_list_does_not_send_even_in_test_mode(self):
        app.config['INVITE_TEST_MODE'] = True
        with patch('app.smtplib.SMTP') as smtp:
            response = self.client.post(f'/admin/event/{self.target}/invite',
                                        json=self.payload(recipient_emails=[]))
        self.assertEqual(response.status_code, 400)
        smtp.assert_not_called()

    def test_invalid_selection_is_rejected(self):
        for selection in ('one@example.com', [None], None):
            response = self.client.post(f'/admin/event/{self.target}/invite',
                                        json=self.payload(recipient_emails=selection))
            self.assertEqual(response.status_code, 400)

    def test_manually_added_address_can_be_selected_or_removed(self):
        for selection, expected in [(['extra@example.com'], ['extra@example.com']),
                                    (['one@example.com'], ['one@example.com'])]:
            with patch('threading.Thread') as thread, patch('app.send_email_batch', create=True, return_value=(1, 0)) as batch:
                response = self.client.post(f'/admin/event/{self.target}/invite',
                    json=self.payload(extra_emails=['extra@example.com'], recipient_emails=selection))
            self.assertEqual(response.status_code, 200)
            actual = thread.call_args.kwargs['args'][0] if thread.called else batch.call_args.args[0]
            self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
