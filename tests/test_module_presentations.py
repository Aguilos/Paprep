import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

db_file = tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False)
db_file.close()
os.environ['DATABASE_URL'] = f'sqlite:///{db_file.name}'

from app import create_app, db
from models import LearningModule, User


class ModulePresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['WTF_CSRF_ENABLED'] = False
        with cls.app.app_context():
            db.drop_all()
            db.create_all()
            user = User(
                email='module-presentations@example.com',
                first_name='Module',
                last_name='Parent',
            )
            user.set_password('password123')
            db.session.add_all([
                user,
                LearningModule(title='Parenting Guide', category='parenting'),
                LearningModule(title='Nutrition Guide', category='nutrition'),
                LearningModule(title='Safety Guide', category='safety'),
            ])
            db.session.commit()
            cls.user_id = user.id
            cls.module_ids = {
                module.category: module.id
                for module in LearningModule.query.all()
            }

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
                'email': 'module-presentations@example.com',
                'password': 'password123',
            },
        )
        self.assertEqual(response.status_code, 302)

    def test_module_list_exposes_fullscreen_presentation_links(self):
        response = self.client.get('/modules/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'module-fullscreen-btn', response.data)
        presentation_url = (
            f"/modules/{self.module_ids['parenting']}/presentation".encode()
        )
        self.assertIn(presentation_url, response.data)

    def test_presentation_route_serves_the_category_pdf(self):
        response = self.client.get(
            f"/modules/{self.module_ids['nutrition']}/presentation"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'application/pdf')
        self.assertTrue(response.data.startswith(b'%PDF'))
        response.close()
        detail = self.client.get(
            f"/modules/{self.module_ids['nutrition']}"
        )
        self.assertEqual(detail.status_code, 200)
        self.assertIn(b'Presentation Reference', detail.data)
        self.assertIn(
            f"/modules/{self.module_ids['nutrition']}/presentation".encode(),
            detail.data,
        )

    def test_missing_presentation_returns_not_found(self):
        original_folder = self.app.config['UPLOAD_FOLDER']
        with tempfile.TemporaryDirectory() as folder:
            self.app.config['UPLOAD_FOLDER'] = folder
            response = self.client.get(
                f"/modules/{self.module_ids['safety']}/presentation"
            )
        self.app.config['UPLOAD_FOLDER'] = original_folder
        self.assertEqual(response.status_code, 404)


if __name__ == '__main__':
    unittest.main()
