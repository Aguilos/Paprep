import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

_db_file = tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False)
_db_file.close()
os.environ['DATABASE_URL'] = f'sqlite:///{_db_file.name}'

from app import create_app, db
from models import LearningModule, User
from routes.chat import match_bot_intent
from routes.clinic_portal import CATEGORY_META as CLINIC_CATEGORY_META
from routes.forum import FORUM_CATEGORIES
from routes.modules import CATEGORY_META


class RemovedFeaturesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['WTF_CSRF_ENABLED'] = False
        with cls.app.app_context():
            db.drop_all()
            db.create_all()
            user = User(email='removed-features@example.com', first_name='Test', last_name='Parent')
            user.set_password('password123')
            db.session.add_all([
                user,
                LearningModule(title='Parenting Basics', category='parenting'),
                LearningModule(title='Legacy Child Health', category='health'),
                LearningModule(title='Safety at Home', category='safety'),
            ])
            db.session.commit()
            cls.user_id = user.id
            cls.health_module_id = LearningModule.query.filter_by(category='health').one().id

    def setUp(self):
        self.client = self.app.test_client()
        response = self.client.post(
            '/auth/login',
            data={'email': 'removed-features@example.com', 'password': 'password123'},
        )
        self.assertEqual(response.status_code, 302)

    def test_preparedness_assessment_route_and_entry_points_are_removed(self):
        response = self.client.get('/modules/assessment')
        self.assertEqual(response.status_code, 404)

        dashboard = self.client.get('/dashboard', follow_redirects=True)
        self.assertEqual(dashboard.status_code, 200)
        self.assertNotIn(b'Preparedness Assessment', dashboard.data)

        modules_page = self.client.get('/modules/')
        self.assertEqual(modules_page.status_code, 200)
        self.assertNotIn(b'Preparedness Assessment', modules_page.data)

    def test_legacy_child_health_modules_are_hidden_from_public_module_surfaces(self):
        modules_page = self.client.get('/modules/')
        self.assertEqual(modules_page.status_code, 200)
        self.assertIn(b'Parenting Basics', modules_page.data)
        self.assertIn(b'Safety at Home', modules_page.data)
        self.assertNotIn(b'Legacy Child Health', modules_page.data)
        self.assertNotIn(b'Child Health', modules_page.data)

        detail = self.client.get(f'/modules/{self.health_module_id}')
        self.assertEqual(detail.status_code, 404)

    def test_remaining_category_metadata_excludes_child_health(self):
        for metadata in (CATEGORY_META, FORUM_CATEGORIES, CLINIC_CATEGORY_META):
            self.assertNotIn('health', metadata)
            self.assertNotIn('Child Health', {value.get('label') for value in metadata.values()})

    def test_chat_does_not_offer_removed_category_shortcut(self):
        with self.app.test_request_context('/'):
            _, shortcuts, _ = match_bot_intent('show me child health modules')
        self.assertFalse(any(shortcut['label'] == 'Child Health Modules' for shortcut in shortcuts))
        self.assertFalse(any('category=health' in shortcut['url'] for shortcut in shortcuts))


if __name__ == '__main__':
    unittest.main()
