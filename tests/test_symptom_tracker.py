import os
import tempfile
import unittest
from datetime import date

_db_file = tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False)
_db_file.close()
os.environ['DATABASE_URL'] = f'sqlite:///{_db_file.name}'

from app import create_app, db
from models import ChildProfile, DiarrheaEpisode, RespiratoryEpisode, User
from routes.symptoms import _diarrhea_guidance, _respiratory_guidance


class SymptomTrackerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['WTF_CSRF_ENABLED'] = False
        with cls.app.app_context():
            db.drop_all()
            db.create_all()
            user = User(email='symptoms@example.com', first_name='Test', last_name='Parent')
            user.set_password('password123')
            user.children.extend([
                ChildProfile(name='Child One', date_of_birth=date(2022, 1, 1)),
                ChildProfile(name='Child Two', date_of_birth=date(2023, 1, 1)),
            ])
            db.session.add(user)
            db.session.commit()
            cls.user_id = user.id
            cls.child_one_id = user.children[0].id
            cls.child_two_id = user.children[1].id

    def setUp(self):
        self.client = self.app.test_client()
        self.client.post('/auth/login', data={'email': 'symptoms@example.com', 'password': 'password123'})
        with self.client.session_transaction() as session:
            session['active_child_id'] = self.child_one_id

    def test_cough_cold_entry_creation_and_emergency_guidance(self):
        response = self.client.post('/fever-tracker', data={
            '_form_type': 'cough',
            'symptom_type': 'cough', 'severity': 'moderate', 'duration_days': '1',
            'difficulty_breathing': 'on',
        })
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            episode = RespiratoryEpisode.query.one()
            self.assertEqual(episode.child_id, self.child_one_id)
            self.assertEqual(_respiratory_guidance(episode)['severity'], 'emergency')

    def test_diarrhea_entry_creation_and_emergency_guidance(self):
        response = self.client.post('/fever-tracker', data={
            '_form_type': 'diarrhea',
            'episodes_per_day': '2', 'consistency': 'watery',
            'dehydration_signs': 'none', 'duration_days': '1', 'blood_present': 'on',
        })
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            episode = DiarrheaEpisode.query.one()
            self.assertEqual(episode.child_id, self.child_one_id)
            self.assertEqual(_diarrhea_guidance(episode)['severity'], 'emergency')

    def test_guidance_thresholds(self):
        with self.app.app_context():
            respiratory = RespiratoryEpisode(severity='mild', duration_days=1, difficulty_breathing=False, wheezing=False, fever_present=False)
            self.assertEqual(_respiratory_guidance(respiratory)['severity'], 'general')
            respiratory.wheezing = True
            self.assertEqual(_respiratory_guidance(respiratory)['severity'], 'high')
            diarrhea = DiarrheaEpisode(episodes_per_day=3, consistency='loose', dehydration_signs='none', duration_days=1, blood_present=False)
            self.assertEqual(_diarrhea_guidance(diarrhea)['severity'], 'monitor')
            diarrhea.dehydration_signs = 'moderate'
            self.assertEqual(_diarrhea_guidance(diarrhea)['severity'], 'high')

    def test_entries_are_isolated_to_active_child(self):
        with self.app.app_context():
            db.session.add(RespiratoryEpisode(
                child_id=self.child_one_id, symptom_type='cough', severity='mild', duration_days=1,
            ))
            db.session.commit()
        with self.client.session_transaction() as session:
            session['active_child_id'] = self.child_two_id
        # /cough-cold-tracker now redirects to /fever-tracker?tab=cough
        response = self.client.get('/fever-tracker', query_string={'tab': 'cough'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'No cough/cold episodes yet', response.data)
        with self.app.app_context():
            self.assertEqual(RespiratoryEpisode.query.filter_by(child_id=self.child_two_id).count(), 0)


if __name__ == '__main__':
    unittest.main()
