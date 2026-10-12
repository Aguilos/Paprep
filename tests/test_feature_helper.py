import os
import sys
import tempfile
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import Config
from app import create_app, db
from models import ChildProfile, User
from routes.chat import FEATURE_REGISTRY, match_feature_request


class FeatureHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        file_descriptor, cls.db_path = tempfile.mkstemp(suffix='.sqlite')
        os.close(file_descriptor)
        cls.original_database_uri = Config.SQLALCHEMY_DATABASE_URI
        cls.original_engine_options = Config.SQLALCHEMY_ENGINE_OPTIONS
        Config.SQLALCHEMY_DATABASE_URI = f'sqlite:///{cls.db_path}'
        Config.SQLALCHEMY_ENGINE_OPTIONS = {
            key: value for key, value in cls.original_engine_options.items()
            if key != 'connect_args'
        }
        cls.app = create_app()
        cls.app.config['WTF_CSRF_ENABLED'] = False
        with cls.app.app_context():
            db.drop_all()
            db.create_all()
            user = User(
                email='feature-helper@example.com',
                first_name='Feature',
                last_name='Helper',
            )
            user.set_password('password123')
            user.children.append(
                ChildProfile(name='Test Child', date_of_birth=date(2022, 1, 1))
            )
            db.session.add(user)
            db.session.commit()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        if os.path.exists(cls.db_path):
            os.remove(cls.db_path)
        Config.SQLALCHEMY_DATABASE_URI = cls.original_database_uri
        Config.SQLALCHEMY_ENGINE_OPTIONS = cls.original_engine_options

    def test_chat_bot_redirect_urls_and_help_panel(self):
        client = self.app.test_client()
        response = client.post(
            '/auth/login',
            data={'email': 'feature-helper@example.com', 'password': 'password123'},
        )
        self.assertEqual(response.status_code, 302)

        for message in ('help me with the fever tracker', 'temperature log'):
            response = client.post('/chat/bot', json={'text': message})
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(
                payload['shortcuts'][0]['url'],
                '/fever-tracker?help=common-ailments',
            )
            self.assertTrue(payload['auto_redirect'])

        page = client.get('/fever-tracker?help=common-ailments')
        self.assertIn(b'Common Ailments Tracker help', page.data)
        self.assertIn(b'Choose Fever, Cough &amp; Colds, or Diarrhea.', page.data)

    def test_unknown_help_value_does_not_render_a_panel(self):
        client = self.app.test_client()
        response = client.get('/?help=%3Cscript%3Ealert(1)%3C%2Fscript%3E')
        self.assertNotIn(b'featureHelpPanel', response.data)
        self.assertNotIn(b'alert(1)', response.data)

    def test_help_for_another_page_does_not_render_a_panel(self):
        client = self.app.test_client()
        response = client.get('/?help=common-ailments')
        self.assertNotIn(b'featureHelpPanel', response.data)

    def test_several_plausible_matches_do_not_redirect(self):
        client = self.app.test_client()
        client.post(
            '/auth/login',
            data={'email': 'feature-helper@example.com', 'password': 'password123'},
        )
        response = client.post('/chat/bot', json={'text': 'help me with a tracker'})
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertFalse(payload['auto_redirect'])
        self.assertGreaterEqual(len(payload['shortcuts']), 2)

    def test_no_match_lists_available_features(self):
        client = self.app.test_client()
        client.post(
            '/auth/login',
            data={'email': 'feature-helper@example.com', 'password': 'password123'},
        )
        response = client.post('/chat/bot', json={'text': 'tell me a joke about gardening'})
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertFalse(payload['auto_redirect'])
        self.assertIn("couldn't match", payload['text'])
        self.assertEqual(
            {shortcut['label'] for shortcut in payload['shortcuts']},
            {feature['name'] for feature in FEATURE_REGISTRY.values()},
        )

    def test_common_ailments_request_matches_tracker(self):
        result = match_feature_request('help me with the fever tracker')
        self.assertEqual(result['match'], 'common-ailments')

    def test_temperature_log_matches_tracker(self):
        result = match_feature_request('where can I add a temperature log')
        self.assertEqual(result['match'], 'common-ailments')

    def test_typo_matches_tracker(self):
        result = match_feature_request('help with the fever trakcer')
        self.assertEqual(result['match'], 'common-ailments')

    def test_unknown_request_has_no_match(self):
        result = match_feature_request('tell me a joke about gardening')
        self.assertIsNone(result['match'])
        self.assertEqual(result['matches'], [])

    def test_registry_contains_instructions_for_every_feature(self):
        self.assertGreaterEqual(len(FEATURE_REGISTRY), 1)
        for feature in FEATURE_REGISTRY.values():
            self.assertTrue(feature['url'])
            self.assertGreaterEqual(len(feature['steps']), 3)
            self.assertLessEqual(len(feature['steps']), 6)


if __name__ == '__main__':
    unittest.main()