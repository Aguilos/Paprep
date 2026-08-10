import os, sys, re
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app import create_app, db
from models import User, ClinicAccount, Clinic
from sqlalchemy import text

app = create_app()

with app.app_context():
    app = create_app()


    def _setup_client_and_fixture():
        with app.app_context():
            # fresh DB for csrf tests
            db_file = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'paprep.db'))
            try:
                if os.path.exists(db_file):
                    os.remove(db_file)
            except Exception:
                pass
            db.create_all()

            # fixtures
            u = User.query.filter_by(email='csrf_test_parent@example.com').first()
            if not u:
                u = User(email='csrf_test_parent@example.com', first_name='CSRF', last_name='Parent')
                u.set_password('password123')
                db.session.add(u)
                db.session.commit()

            ca = ClinicAccount.query.filter_by(email='csrf_test_clinic@example.com').first()
            if not ca:
                ca = ClinicAccount(email='csrf_test_clinic@example.com', contact_name='Clinic')
                ca.set_password('clinicpass')
                db.session.add(ca)
                db.session.commit()

            clinic = Clinic.query.filter_by(name='CSRF Test Clinic').first()
            if not clinic:
                clinic = Clinic(name='CSRF Test Clinic', clinic_account_id=ca.id)
                db.session.add(clinic)
                db.session.commit()

        client = app.test_client()
        # fetch login page to get login form CSRF token, then submit login
        login_page = client.get('/auth/login')
        m_login = re.search(r'name="csrf_token" value="([^"]+)"', login_page.get_data(as_text=True))
        login_token = m_login.group(1) if m_login else None
        client.post('/auth/login', data={'email': u.email, 'password': 'password123', 'csrf_token': login_token}, follow_redirects=True)

        # After login, fetch page that contains span#csrfToken and extract token
        clinics_page = client.get('/clinics', follow_redirects=True)
        m = re.search(r'id="csrfToken" data-token="([^"]+)"', clinics_page.get_data(as_text=True))
        token = m.group(1) if m else None
        return client, clinic, token


    def test_chat_send_rejected_without_csrf():
        client, clinic, token = _setup_client_and_fixture()
        res_no = client.post('/chat/send', json={'clinic_id': clinic.id, 'text': 'No token'})
        assert res_no.status_code in (400, 403)


    def test_chat_send_succeeds_with_csrf():
        client, clinic, token = _setup_client_and_fixture()
        headers = {'X-CSRFToken': token} if token else {}
        res_with = client.post('/chat/send', json={'clinic_id': clinic.id, 'text': 'With token'}, headers=headers)
        assert res_with.status_code == 200
        # confirm message persisted
        from models import ClinicMessage
        msgs = ClinicMessage.query.filter_by(clinic_id=clinic.id).all()
        assert any(m.text == 'With token' for m in msgs)


    if __name__ == '__main__':
        test_chat_send_rejected_without_csrf()
        test_chat_send_succeeds_with_csrf()
        print('CSRF tests ran OK')
