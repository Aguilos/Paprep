import os
import sys
import tempfile
import unittest
from datetime import date, datetime
from datetime import timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app, db
from config import Config
from models import (
    ChildProfile,
    Clinic,
    ClinicAccount,
    ClinicRegistration,
    DiarrheaEpisode,
    FeverReading,
    HealthChecklist,
    RespiratoryEpisode,
    User,
)


class ClinicPatientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fd, cls.db_path = tempfile.mkstemp(suffix='.sqlite')
        os.close(fd)
        cls.original_uri = Config.SQLALCHEMY_DATABASE_URI
        cls.original_options = Config.SQLALCHEMY_ENGINE_OPTIONS
        Config.SQLALCHEMY_DATABASE_URI = f'sqlite:///{cls.db_path}'
        Config.SQLALCHEMY_ENGINE_OPTIONS = {
            key: value for key, value in cls.original_options.items()
            if key != 'connect_args'
        }
        cls.app = create_app()
        cls.app.config['WTF_CSRF_ENABLED'] = False
        with cls.app.app_context():
            db.drop_all()
            db.create_all()
            owner = ClinicAccount(email='patients-clinic@example.com', contact_name='Clinic')
            owner.set_password('password123')
            parent = User(email='patients-parent@example.com', first_name='Maria', last_name='Santos')
            parent.set_password('password123')
            child = ChildProfile(name='Lia', date_of_birth=date(2022, 1, 1))
            sibling = ChildProfile(name='Mia', date_of_birth=date(2023, 1, 1))
            parent.children.extend([child, sibling])
            db.session.add_all([owner, parent])
            db.session.flush()
            clinic = Clinic(name='Patients Clinic', clinic_account_id=owner.id)
            db.session.add(clinic)
            db.session.flush()
            db.session.add(ClinicRegistration(
                clinic_id=clinic.id, user_id=parent.id, child_id=child.id
            ))
            db.session.add(FeverReading(
                child_id=child.id, value=38.5, unit='C', value_celsius=38.5,
                recorded_at=datetime(2026, 1, 2, 10, 0),
            ))
            db.session.commit()
            cls.owner_id = owner.id
            cls.clinic_id = clinic.id
            cls.child_id = child.id
            cls.sibling_id = sibling.id
            cls.parent_id = parent.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        os.remove(cls.db_path)
        Config.SQLALCHEMY_DATABASE_URI = cls.original_uri
        Config.SQLALCHEMY_ENGINE_OPTIONS = cls.original_options

    def clinic_client(self):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['clinic_account_id'] = self.owner_id
        return client

    def test_patient_search_and_health_details(self):
        client = self.clinic_client()
        response = client.get('/clinic/patients?q=lia')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Lia', response.data)
        self.assertIn(f'/clinic/patients/{self.child_id}'.encode(), response.data)
        self.assertIn(f'/clinic/patients/{self.sibling_id}'.encode(), response.data)

        details = client.get(f'/clinic/patients/{self.child_id}')
        self.assertEqual(details.status_code, 200)
        self.assertIn(b'Lia Health Details', details.data)
        self.assertIn(b'38.5', details.data)
        self.assertIn(b'Temperature history', details.data)
        self.assertIn(b'Manila time', details.data)

    def test_manila_time_format_works_without_tzdata(self):
        with self.app.app_context():
            from routes.clinic_portal import _format_manila_time
            formatted = _format_manila_time(datetime(2026, 1, 2, 10, 0))
        self.assertIn('Jan 02, 2026 18:00 Manila time', formatted)

    def test_all_children_of_registered_parent_are_visible(self):
        response = self.clinic_client().get(f'/clinic/patients/{self.sibling_id}')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Mia Health Details', response.data)

    def test_unknown_child_is_not_visible_to_clinic(self):
        response = self.clinic_client().get('/clinic/patients/99999')
        self.assertEqual(response.status_code, 404)

    def test_non_get_methods_are_rejected(self):
        client = self.clinic_client()
        for method in ('post', 'put', 'delete'):
            response = getattr(client, method)(f'/clinic/patients/{self.child_id}')
            self.assertEqual(response.status_code, 405)

    def test_parent_and_logged_out_visitors_cannot_see_details(self):
        logged_out = self.app.test_client().get(f'/clinic/patients/{self.child_id}')
        self.assertEqual(logged_out.status_code, 302)
        self.assertIn('/clinic/login', logged_out.location)

        parent = self.app.test_client()
        parent.post('/auth/login', data={
            'email': 'patients-parent@example.com',
            'password': 'password123',
        })
        response = parent.get(f'/clinic/patients/{self.child_id}')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/clinic/login', response.location)

    def test_parent_entered_text_is_escaped(self):
        with self.app.app_context():
            reading = db.session.get(FeverReading, 1)
            reading.method = '<script>alert(1)</script>'
            db.session.add(HealthChecklist(
                child_id=self.child_id,
                date=date(2026, 1, 3),
                checked_items='["one"]',
                notes='<script>alert(2)</script>',
            ))
            db.session.commit()
        response = self.clinic_client().get(f'/clinic/patients/{self.child_id}')
        self.assertNotIn(b'<script>alert(1)</script>', response.data)
        self.assertNotIn(b'<script>alert(2)</script>', response.data)
        self.assertIn(b'&lt;script&gt;', response.data)

    def test_empty_states_are_shown_for_a_child_without_history(self):
        with self.app.app_context():
            parent = User(
                email='empty-patient@example.com',
                first_name='Empty',
                last_name='Patient',
            )
            parent.set_password('password123')
            child = ChildProfile(
                name='Empty Child',
                date_of_birth=date(2024, 1, 1),
            )
            parent.children.append(child)
            db.session.add(parent)
            db.session.flush()
            db.session.add(ClinicRegistration(
                clinic_id=self.clinic_id,
                user_id=parent.id,
                child_id=child.id,
            ))
            db.session.commit()
            empty_child_id = child.id
        response = self.clinic_client().get(f'/clinic/patients/{empty_child_id}')
        self.assertIn(b'No temperature readings recorded.', response.data)
        self.assertIn(b'No cough or cold episodes recorded.', response.data)
        self.assertIn(b'No diarrhea episodes recorded.', response.data)
        self.assertIn(b'No health checklist history recorded.', response.data)

    def test_histories_show_values_newest_first_and_cap_notice(self):
        with self.app.app_context():
            db.session.add(RespiratoryEpisode(
                child_id=self.child_id, symptom_type='cough', severity='mild',
                duration_days=2, recorded_at=datetime(2026, 2, 1, 1, 0),
            ))
            db.session.add(DiarrheaEpisode(
                child_id=self.child_id, episodes_per_day=3, consistency='loose',
                dehydration_signs='none', duration_days=1,
                recorded_at=datetime(2026, 2, 2, 1, 0),
            ))
            db.session.add(HealthChecklist(
                child_id=self.child_id, date=date(2026, 2, 3),
                checked_items='["one", "two", "three", "four", "five"]',
            ))
            for index in range(31):
                db.session.add(FeverReading(
                    child_id=self.child_id, value=36 + index / 10, unit='C',
                    value_celsius=36 + index / 10,
                    recorded_at=datetime(2026, 3, 1, 1, index),
                ))
            db.session.commit()
        response = self.clinic_client().get(f'/clinic/patients/{self.child_id}')
        self.assertIn(b'Cough', response.data)
        self.assertIn(b'3 episode(s)/day', response.data)
        self.assertIn(b'5 completed', response.data)
        self.assertIn(b'Showing the newest 30 of 32 entries.', response.data)
        self.assertLess(response.data.index(b'39.0'), response.data.index(b'36.1'))


if __name__ == '__main__':
    unittest.main()
