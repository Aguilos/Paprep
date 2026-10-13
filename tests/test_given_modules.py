import os
import tempfile
import unittest

db_file = tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False)
db_file.close()
os.environ['DATABASE_URL'] = f'sqlite:///{db_file.name}'

from app import create_app, db
from models import User
from routes.modules import given_module_registry


class GivenModuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['WTF_CSRF_ENABLED'] = False
        with cls.app.app_context():
            db.drop_all()
            db.create_all()
            user = User(
                email='given-modules-parent@example.com',
                first_name='Given',
                last_name='Parent',
            )
            user.set_password('password123')
            db.session.add(user)
            db.session.commit()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        os.remove(db_file.name)

    def setUp(self):
        self.client = self.app.test_client()
        response = self.client.post(
            '/auth/login',
            data={
                'email': 'given-modules-parent@example.com',
                'password': 'password123',
            },
        )
        self.assertEqual(response.status_code, 302)

    def test_section_and_viewer_are_separate_from_database_modules(self):
        response = self.client.get('/modules/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Given Modules', response.data)
        self.assertIn(b'Parenting Guide', response.data)
        self.assertIn(b'data-given-id="parenting"', response.data)
        self.assertIn(b'/modules/given/parenting', response.data)

    def test_viewer_and_every_slide_are_available_to_parent(self):
        response = self.client.get('/modules/given/nutrition')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Start presentation', response.data)
        with self.app.app_context():
            manifest = given_module_registry()
        for given_id, module in manifest.items():
            for slide_number in range(1, module['slide_count'] + 1):
                response = self.client.get(
                    f'/modules/given/{given_id}/slide/{slide_number}'
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.mimetype, 'image/jpeg')
                response.close()

    def test_logged_out_slide_request_redirects_to_login(self):
        self.client.get('/auth/logout')
        response = self.client.get('/modules/given/safety/slide/1')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/auth/login', response.headers['Location'])

    def test_invalid_registry_and_slide_values_return_not_found(self):
        self.assertEqual(
            self.client.get('/modules/given/not-a-real-module').status_code,
            404,
        )
        self.assertEqual(
            self.client.get('/modules/given/safety/slide/0').status_code,
            404,
        )
        self.assertEqual(
            self.client.get('/modules/given/safety/slide/999').status_code,
            404,
        )
        response = self.client.get('/modules/given/safety/slide/1?path=../../secret')
        self.assertEqual(response.status_code, 200)
        response.close()

    def test_given_modules_have_no_edit_or_delete_route(self):
        clinic_list = self.client.get('/clinic/modules')
        self.assertNotIn(b'Given Modules', clinic_list.data)
        self.assertNotEqual(
            self.client.get('/clinic/modules/given/parenting/edit').status_code,
            200,
        )
        self.assertNotEqual(
            self.client.post('/clinic/modules/given/parenting/delete').status_code,
            200,
        )
        self.assertNotEqual(
            self.client.post('/modules/given/parenting/delete').status_code,
            200,
        )

    def test_given_modules_survive_app_restart(self):
        restarted = create_app()
        restarted.config['WTF_CSRF_ENABLED'] = False
        with restarted.test_client() as client:
            response = client.post(
                '/auth/login',
                data={
                    'email': 'given-modules-parent@example.com',
                    'password': 'password123',
                },
            )
            self.assertEqual(response.status_code, 302)
            self.assertEqual(client.get('/modules/given/parenting').status_code, 200)
        with restarted.app_context():
            db.session.remove()
            db.engine.dispose()


if __name__ == '__main__':
    unittest.main()
