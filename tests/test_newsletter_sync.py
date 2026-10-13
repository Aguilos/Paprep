import os
import sys
import tempfile
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app, db
from config import Config
from models import (
    ChildProfile,
    Clinic,
    ClinicAccount,
    ClinicRegistration,
    NewsletterComment,
    NewsletterLike,
    Newsletter,
    NewsletterMedia,
    User,
)


class NewsletterSyncTests(unittest.TestCase):
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
            cls.parent = User(
                email='newsletter-parent@example.com',
                first_name='Newsletter',
                last_name='Parent',
            )
            cls.parent.set_password('password123')
            cls.child = ChildProfile(
                name='Newsletter Child',
                date_of_birth=date(2022, 1, 1),
            )
            cls.parent.children.append(cls.child)
            cls.account = ClinicAccount(
                email='newsletter-clinic@example.com',
                contact_name='Newsletter Clinic',
            )
            cls.account.set_password('password123')
            db.session.add_all([cls.parent, cls.account])
            db.session.flush()
            cls.clinic = Clinic(
                name='Newsletter Clinic',
                clinic_account_id=cls.account.id,
            )
            db.session.add(cls.clinic)
            db.session.flush()
            db.session.add(ClinicRegistration(
                clinic_id=cls.clinic.id,
                user_id=cls.parent.id,
                child_id=cls.child.id,
            ))
            db.session.commit()
            cls.parent_id = cls.parent.id
            cls.child_id = cls.child.id
            cls.account_id = cls.account.id
            cls.clinic_id = cls.clinic.id

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        os.remove(cls.db_path)
        Config.SQLALCHEMY_DATABASE_URI = cls.original_uri
        Config.SQLALCHEMY_ENGINE_OPTIONS = cls.original_options

    def setUp(self):
        with self.app.app_context():
            db.session.query(NewsletterMedia).delete()
            db.session.query(Newsletter).delete()
            db.session.commit()

    def clinic_client(self):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['clinic_account_id'] = self.account_id
        return client

    def parent_client(self):
        client = self.app.test_client()
        response = client.post('/auth/login', data={
            'email': 'newsletter-parent@example.com',
            'password': 'password123',
        })
        self.assertEqual(response.status_code, 302)
        return client

    def test_create_and_parent_display_share_newsletter_fields(self):
        response = self.clinic_client().post('/clinic/newsletters/add', data={
            'child_id': str(self.child_id),
            'title': 'First update',
            'body': 'The child is doing well.',
            'target_age_min_years': '3',
            'target_age_max_years': '5',
            'action': 'publish',
            'media_type': ['image'],
            'media_source': ['https://example.com/update.jpg'],
            'media_caption': ['Update image'],
        })
        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            newsletter = Newsletter.query.filter_by(title='First update').one()
            self.assertEqual(newsletter.target_age_min_years, 3)
            self.assertEqual(newsletter.target_age_max_years, 5)

        parent_page = self.parent_client().get('/dashboard')
        self.assertEqual(parent_page.status_code, 200)
        self.assertIn(b'First update', parent_page.data)
        self.assertIn(b'The child is doing well.', parent_page.data)
        self.assertIn(b'https://example.com/update.jpg', parent_page.data)

        clinic_page = self.clinic_client().get('/clinic/newsletters')
        self.assertEqual(clinic_page.status_code, 200)
        self.assertIn(b'First update', clinic_page.data)
        self.assertIn(b'The child is doing well.', clinic_page.data)

    def test_edit_updates_parent_display_and_preserves_media_relationship(self):
        with self.app.app_context():
            newsletter = Newsletter(
                title='Before edit',
                body='Old body',
                child_id=self.child_id,
                clinic_id=self.clinic_id,
                is_published=True,
            )
            newsletter.media.append(NewsletterMedia(
                media_type='image',
                source='https://example.com/old.jpg',
            ))
            db.session.add(newsletter)
            db.session.commit()
            newsletter_id = newsletter.id

        response = self.clinic_client().post(
            f'/clinic/newsletters/{newsletter_id}/edit',
            data={
                'title': 'After edit',
                'body': 'New body',
                'action': 'publish',
                'media_type': ['image'],
                'media_source': ['https://example.com/new.jpg'],
                'media_caption': ['New image'],
            },
        )
        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            newsletter = db.session.get(Newsletter, newsletter_id)
            self.assertEqual(newsletter.title, 'After edit')
            self.assertEqual(newsletter.body, 'New body')
            self.assertEqual(len(newsletter.media), 1)
            self.assertEqual(newsletter.media[0].source, 'https://example.com/new.jpg')

        parent_page = self.parent_client().get('/dashboard')
        self.assertIn(b'After edit', parent_page.data)
        self.assertIn(b'New body', parent_page.data)
        self.assertNotIn(b'Before edit', parent_page.data)

    def test_invalid_media_edit_does_not_replace_existing_media(self):
        with self.app.app_context():
            newsletter = Newsletter(
                title='Stable newsletter',
                body='Stable body',
                child_id=self.child_id,
                clinic_id=self.clinic_id,
                is_published=True,
            )
            newsletter.media.append(NewsletterMedia(
                media_type='image',
                source='https://example.com/keep.jpg',
            ))
            db.session.add(newsletter)
            db.session.commit()
            newsletter_id = newsletter.id

        response = self.clinic_client().post(
            f'/clinic/newsletters/{newsletter_id}/edit',
            data={
                'title': 'Should not save',
                'body': 'Should not save',
                'action': 'publish',
                'media_type': ['video'],
                'media_source': ['https://example.com/not-youtube'],
                'media_caption': ['Invalid video'],
            },
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            newsletter = db.session.get(Newsletter, newsletter_id)
            self.assertEqual(newsletter.title, 'Stable newsletter')
            self.assertEqual(newsletter.media[0].source, 'https://example.com/keep.jpg')

    def test_clinic_list_uses_updated_date_consistently(self):
        with self.app.app_context():
            newsletter = Newsletter(
                title='Dated update',
                body='Body',
                child_id=self.child_id,
                clinic_id=self.clinic_id,
                is_published=True,
            )
            db.session.add(newsletter)
            db.session.commit()
            newsletter_id = newsletter.id
            newsletter.created_at = newsletter.created_at.replace(year=2020)
            newsletter.updated_at = newsletter.updated_at.replace(year=2024)
            db.session.commit()

        clinic_page = self.clinic_client().get('/clinic/newsletters')
        self.assertIn(b'2024', clinic_page.data)
        parent_page = self.parent_client().get('/dashboard')
        self.assertIn(b'Dated update', parent_page.data)
        self.assertIn(b'Updated ', parent_page.data)

    def test_clinic_list_shows_parent_likes_and_comments(self):
        with self.app.app_context():
            newsletter = Newsletter(
                title='Engagement update',
                body='Engagement body',
                child_id=self.child_id,
                clinic_id=self.clinic_id,
                is_published=True,
            )
            db.session.add(newsletter)
            db.session.flush()
            db.session.add(NewsletterLike(
                user_id=self.parent_id,
                newsletter_id=newsletter.id,
            ))
            db.session.add(NewsletterComment(
                user_id=self.parent_id,
                newsletter_id=newsletter.id,
                text='Thank you for sharing this update.',
            ))
            db.session.commit()

        clinic_page = self.clinic_client().get('/clinic/newsletters')
        self.assertEqual(clinic_page.status_code, 200)
        self.assertIn(b'1 helpful', clinic_page.data)
        self.assertIn(b'1 comments', clinic_page.data)
        self.assertIn(b'Thank you for sharing this update.', clinic_page.data)
        self.assertIn(b'Newsletter Parent', clinic_page.data)

    def test_parent_sees_newsletters_for_active_child_age_not_child_id(self):
        with self.app.app_context():
            matching = Newsletter(
                title='Age-matched update',
                body='For children in this age range.',
                child_id=None,
                clinic_id=self.clinic_id,
                target_age_min_years=3,
                target_age_max_years=5,
                is_published=True,
            )
            excluded = Newsletter(
                title='Older-child update',
                body='For older children.',
                child_id=None,
                clinic_id=self.clinic_id,
                target_age_min_years=6,
                target_age_max_years=10,
                is_published=True,
            )
            db.session.add_all([matching, excluded])
            db.session.commit()

        parent_page = self.parent_client().get('/dashboard')
        self.assertIn(b'Age-matched update', parent_page.data)
        self.assertNotIn(b'Older-child update', parent_page.data)

    def test_dashboard_provides_child_tabs_for_age_filtered_newsletters(self):
        with self.app.app_context():
            older_child = ChildProfile(
                user_id=self.parent_id,
                name='Older Child',
                date_of_birth=date(2017, 1, 1),
            )
            db.session.add(older_child)
            db.session.add(Newsletter(
                title='Younger-child update',
                body='For the younger child age range.',
                child_id=None,
                clinic_id=self.clinic_id,
                target_age_min_years=0,
                target_age_max_years=5,
                is_published=True,
            ))
            db.session.add(Newsletter(
                title='Older-child update',
                body='For the older child age range.',
                child_id=None,
                clinic_id=self.clinic_id,
                target_age_min_years=6,
                target_age_max_years=10,
                is_published=True,
            ))
            db.session.commit()

        parent_page = self.parent_client().get('/dashboard')
        self.assertIn(b'class="btn btn-sm btn-primary newsletter-child-tab"', parent_page.data)
        self.assertIn(b'Older Child', parent_page.data)
        self.assertIn(b'Younger-child update', parent_page.data)
        self.assertNotIn(b'Older-child update', parent_page.data)


if __name__ == '__main__':
    unittest.main()
