import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app, db
from config import Config
from models import Clinic, ClinicAccount, LearningModule, ModuleProgress, ModuleQuizQuestion, User


class ClinicModuleEditTests(unittest.TestCase):
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
            cls.owner = ClinicAccount(
                email='owner@example.com', contact_name='Owner Clinic'
            )
            cls.owner.set_password('password123')
            cls.other = ClinicAccount(
                email='other@example.com', contact_name='Other Clinic'
            )
            cls.other.set_password('password123')
            cls.parent = User(
                email='parent@example.com',
                first_name='Parent',
                last_name='User',
            )
            cls.parent.set_password('password123')
            db.session.add_all([cls.owner, cls.other, cls.parent])
            db.session.flush()
            db.session.add_all([
                Clinic(name='Owner Clinic', clinic_account_id=cls.owner.id),
                Clinic(name='Other Clinic', clinic_account_id=cls.other.id),
            ])
            db.session.commit()
            cls.module = LearningModule(
                title='Original title',
                description='Original description',
                content='<h2>Original section</h2><p>Original content</p>',
                category='parenting',
                age_group='0-6 months',
                clinic_account_id=cls.owner.id,
            )
            cls.system_module = LearningModule(
                title='System module',
                category='safety',
                clinic_account_id=None,
            )
            db.session.add_all([cls.module, cls.system_module])
            db.session.commit()
            cls.module_id = cls.module.id
            cls.system_module_id = cls.system_module.id
            cls.owner_id = cls.owner.id
            cls.other_id = cls.other.id
            cls.parent_id = cls.parent.id

    def setUp(self):
        with self.app.app_context():
            module = db.session.get(LearningModule, self.module_id)
            module.title = 'Original title'
            module.description = 'Original description'
            module.content = '<h2>Original section</h2><p>Original content</p>'
            module.category = 'parenting'
            module.age_group = '0-6 months'
            db.session.query(ModuleProgress).filter_by(module_id=self.module_id).delete()
            db.session.query(ModuleQuizQuestion).filter_by(module_id=self.module_id).delete()
            db.session.commit()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        os.remove(cls.db_path)
        Config.SQLALCHEMY_DATABASE_URI = cls.original_uri
        Config.SQLALCHEMY_ENGINE_OPTIONS = cls.original_options

    def clinic_client(self, account_id):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['clinic_account_id'] = account_id
        return client

    def test_owner_can_open_prefilled_editor(self):
        response = self.clinic_client(self.owner_id).get(
            f'/clinic/modules/{self.module_id}/editor'
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Original title', response.data)
        self.assertIn(b'Original description', response.data)
        self.assertIn(b'Original section', response.data)
        self.assertIn(b'0-6 months', response.data)

    def test_valid_save_updates_same_record(self):
        client = self.clinic_client(self.owner_id)
        response = client.post(
            f'/clinic/modules/{self.module_id}/editor',
            data={
                'title': 'Updated title',
                'description': 'Updated description',
                'content': '<h2>Updated section</h2>',
                'category': 'nutrition',
                'age_group': '6-12 months',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('/clinic/modules', response.location)
        with self.app.app_context():
            module = db.session.get(LearningModule, self.module_id)
            self.assertEqual(module.title, 'Updated title')
            self.assertEqual(module.category, 'nutrition')
            self.assertEqual(LearningModule.query.count(), 2)

    def test_invalid_save_rerenders_typed_values_and_saves_nothing(self):
        client = self.clinic_client(self.owner_id)
        response = client.post(
            f'/clinic/modules/{self.module_id}/editor',
            data={
                'title': '',
                'description': 'Typed description',
                'content': '<h2>Typed long content</h2>',
                'category': 'not-a-category',
                'age_group': 'Typed age group',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Module title is required.', response.data)
        self.assertIn(b'Please select a valid module category.', response.data)
        self.assertIn(b'Typed description', response.data)
        self.assertIn(b'Typed long content', response.data)
        self.assertIn(b'Typed age group', response.data)
        with self.app.app_context():
            module = db.session.get(LearningModule, self.module_id)
            self.assertEqual(module.title, 'Original title')
            self.assertEqual(module.description, 'Original description')

    def test_invalid_pdf_magic_bytes_rerenders_without_saving(self):
        client = self.clinic_client(self.owner_id)
        response = client.post(
            f'/clinic/modules/{self.module_id}/editor',
            data={
                'title': 'PDF attempt',
                'description': 'Typed description',
                'content': '<p>Typed content</p>',
                'category': 'parenting',
                'age_group': '0-6 months',
                'pdf_file': (tempfile.SpooledTemporaryFile(), 'fake.pdf'),
            },
            content_type='multipart/form-data',
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'uploaded file is not a valid PDF', response.data)
        with self.app.app_context():
            self.assertEqual(db.session.get(LearningModule, self.module_id).title, 'Original title')

    def test_different_clinic_cannot_edit_owned_module(self):
        response = self.clinic_client(self.other_id).get(
            f'/clinic/modules/{self.module_id}/editor'
        )
        self.assertEqual(response.status_code, 404)

    def test_parent_cannot_reach_edit_page(self):
        client = self.app.test_client()
        client.post('/auth/login', data={
            'email': 'parent@example.com', 'password': 'password123'
        })
        response = client.get(f'/clinic/modules/{self.module_id}/editor')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/clinic/login', response.location)

    def test_logged_out_visitor_is_sent_to_clinic_login(self):
        response = self.app.test_client().get(
            f'/clinic/modules/{self.module_id}/editor'
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('/clinic/login', response.location)

    def test_system_module_cannot_be_edited_by_clinic(self):
        response = self.clinic_client(self.owner_id).get(
            f'/clinic/modules/{self.system_module_id}/editor'
        )
        self.assertEqual(response.status_code, 404)

    def test_edit_button_is_visible_only_to_owner(self):
        owner_response = self.clinic_client(self.owner_id).get('/clinic/modules')
        other_response = self.clinic_client(self.other_id).get('/clinic/modules')
        self.assertIn(
            f'/clinic/modules/{self.module_id}/editor'.encode(),
            owner_response.data,
        )
        self.assertNotIn(
            f'/clinic/modules/{self.module_id}/editor'.encode(),
            other_response.data,
        )

    def test_progress_and_quiz_data_survive_edit(self):
        with self.app.app_context():
            progress = ModuleProgress(
                user_id=self.parent_id, module_id=self.module_id,
                status='completed', last_section=3, quiz_score=90, quiz_attempts=2,
            )
            question = ModuleQuizQuestion(
                module_id=self.module_id, question='Original question',
                option_a='A', option_b='B', correct='a', sort_order=1,
            )
            db.session.add_all([progress, question])
            db.session.commit()
            progress_id, question_id = progress.id, question.id

        self.clinic_client(self.owner_id).post(
            f'/clinic/modules/{self.module_id}/edit',
            data={
                'title': 'Final title',
                'description': 'Final description',
                'content': '<p>Final content</p>',
                'category': 'safety',
                'age_group': '12 months',
            },
        )
        with self.app.app_context():
            saved_progress = db.session.get(ModuleProgress, progress_id)
            saved_question = db.session.get(ModuleQuizQuestion, question_id)
            self.assertEqual(saved_progress.status, 'completed')
            self.assertEqual(saved_progress.last_section, 3)
            self.assertEqual(saved_progress.quiz_score, 90)
            self.assertEqual(saved_progress.quiz_attempts, 2)
            self.assertEqual(saved_question.question, 'Original question')


if __name__ == '__main__':
    unittest.main()
