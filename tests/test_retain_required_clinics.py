import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app, db
from config import Config
from models import (
    Clinic,
    ClinicAccount,
    ClinicMessage,
    LearningModule,
    ParentChildResource,
)
from scripts.retain_required_clinics import cleanup_clinics


class RetainRequiredClinicsTests(unittest.TestCase):
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
        with cls.app.app_context():
            db.drop_all()
            db.create_all()
            keep_demo_account = ClinicAccount(
                email='keep-demo@example.com', contact_name='Demo'
            )
            keep_demo_account.set_password('password123')
            keep_mildred_account = ClinicAccount(
                email='keep-mildred@example.com', contact_name='Mildred'
            )
            keep_mildred_account.set_password('password123')
            remove_account = ClinicAccount(
                email='remove@example.com', contact_name='Remove'
            )
            remove_account.set_password('password123')
            db.session.add_all([
                keep_demo_account, keep_mildred_account, remove_account,
            ])
            db.session.flush()
            db.session.add_all([
                Clinic(
                    name='DEMO', city='SANTA MARIA',
                    clinic_account_id=keep_demo_account.id,
                ),
                Clinic(
                    name="Dra  Mildred Javier Children's Clinic", city='Siniloan',
                    clinic_account_id=keep_mildred_account.id,
                ),
                Clinic(
                    name='Remove Clinic', city='Siniloan',
                    clinic_account_id=remove_account.id,
                ),
            ])
            db.session.flush()
            db.session.add_all([
                LearningModule(
                    title='Keep module', category='parenting',
                    clinic_account_id=keep_demo_account.id,
                ),
                ParentChildResource(
                    title='Keep resource', url='https://example.com/keep',
                    clinic_account_id=keep_demo_account.id,
                ),
                LearningModule(
                    title='Remove module', category='parenting',
                    clinic_account_id=remove_account.id,
                ),
                ParentChildResource(
                    title='Remove resource', url='https://example.com/remove',
                    clinic_account_id=remove_account.id,
                ),
            ])
            remove_clinic = Clinic.query.filter_by(name='Remove Clinic').one()
            db.session.add(ClinicMessage(
                clinic_id=remove_clinic.id, user_id=1,
                sender='user', text='remove me',
            ))
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

    def test_only_named_clinics_and_their_accounts_remain(self):
        with self.app.app_context():
            protected, summary = cleanup_clinics(apply=True)
            self.assertEqual(summary['clinics'], 1)
            self.assertEqual(summary['clinic_accounts'], 1)
            self.assertEqual(
                {(clinic.name, clinic.city) for clinic in protected},
                {
                    ('DEMO', 'SANTA MARIA'),
                    ("Dra  Mildred Javier Children's Clinic", 'Siniloan'),
                },
            )
            self.assertEqual(Clinic.query.count(), 2)
            self.assertEqual(ClinicAccount.query.count(), 2)
            self.assertEqual(LearningModule.query.count(), 1)
            self.assertEqual(ParentChildResource.query.count(), 1)
            self.assertEqual(
                ParentChildResource.query.one().title,
                'Keep resource',
            )
            self.assertEqual(ClinicMessage.query.count(), 0)


if __name__ == '__main__':
    unittest.main()