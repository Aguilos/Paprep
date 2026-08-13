import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app import create_app, db
from models import User, ClinicAccount, Clinic, ClinicMessage
from flask_wtf.csrf import generate_csrf

app = create_app()

with app.app_context():
    # Ensure DB schema is up-to-date for tests
    # For tests: remove existing sqlite file to ensure a clean schema, and disable CSRF
    import os
    db_file = os.path.join(os.path.dirname(__file__), '..', 'paprep.db')
    db_file = os.path.abspath(db_file)
    try:
        if os.path.exists(db_file):
            os.remove(db_file)
    except Exception:
        pass
    # Ensure CSRF remains enabled for realistic testing
    # Drop existing clinic_messages table via model if present, then recreate schema
    try:
        from models import ClinicMessage as _CM
        _CM.__table__.drop(db.engine, checkfirst=True)
    except Exception:
        pass
    db.create_all()
    # Create or reuse test user and clinic
    from models import ChildProfile
    from datetime import date
    u = User.query.filter_by(email='testparent@example.com').first()
    if not u:
        u = User(email='testparent@example.com', first_name='Test', last_name='Parent')
        u.set_password('password123')
        c = ChildProfile(name='Test Child', date_of_birth=date(2022, 1, 1), gender='boy')
        u.children.append(c)
        db.session.add(u)
        db.session.commit()

    ca = ClinicAccount.query.filter_by(email='clinic@example.com').first()
    if not ca:
        ca = ClinicAccount(email='clinic@example.com', contact_name='Clinic Staff')
        ca.set_password('clinicpass')
        db.session.add(ca)
        db.session.commit()

    clinic = Clinic.query.filter_by(name='Test Clinic').first()
    if not clinic:
        clinic = Clinic(name='Test Clinic', clinic_account_id=ca.id)
        db.session.add(clinic)
        db.session.commit()

    client = app.test_client()

    import re
    # Fetch login page to obtain form CSRF, then perform login
    login_page = client.get('/auth/login')
    m_login = re.search(r'name="csrf_token" value="([^"]+)"', login_page.get_data(as_text=True))
    login_csrf = m_login.group(1) if m_login else None
    res_login = client.post('/auth/login', data={'email': u.email, 'password': 'password123', 'csrf_token': login_csrf}, follow_redirects=True)
    print('login status', res_login.status_code)

    # After login, fetch a page that includes span#csrfToken to get the token for AJAX
    clinics_page = client.get('/clinics', follow_redirects=True)
    m = re.search(r'id="csrfToken" data-token="([^"]+)"', clinics_page.get_data(as_text=True))
    token = m.group(1) if m else None
    if not token:
        print('ERROR: could not find csrf token in page after login')

    # Parent sends message
    res = client.post('/chat/send', json={'clinic_id': clinic.id, 'text': 'Hello Clinic'}, headers={'X-CSRFToken': token})
    print('parent send status', res.status_code, res.get_json())
    if res.status_code != 200:
        print('parent send body:', res.get_data(as_text=True))

    # Verify message saved
    # Print DB schema for clinic_messages to help debug
    try:
        from sqlalchemy import text
        cols = db.session.execute(text("PRAGMA table_info('clinic_messages')")).fetchall()
        print('clinic_messages schema:', cols)
    except Exception as e:
        print('pragma error', e)
    msgs = ClinicMessage.query.filter_by(clinic_id=clinic.id, user_id=u.id).all()
    print('messages count after parent send:', len(msgs))

    # Clinic reply: set clinic_account_id in session and csrf
    # Get fresh CSRF token from page for clinic session
    res1 = client.get('/clinics', follow_redirects=True)
    m2 = re.search(r'id="csrfToken" data-token="([^"]+)"', res1.get_data(as_text=True))
    token2 = m2.group(1) if m2 else None
    with client.session_transaction() as sess:
        sess.pop('_user_id', None)
        sess['clinic_account_id'] = ca.id

    res2 = client.post('/chat/reply', json={'user_id': u.id, 'text': 'Hello Parent'}, headers={'X-CSRFToken': token2})
    print('clinic reply status', res2.status_code, res2.get_json())
    if res2.status_code != 200:
        print('clinic reply body:', res2.get_data(as_text=True))

    # Verify reply saved
    msgs_all = ClinicMessage.query.filter_by(clinic_id=clinic.id, user_id=u.id).order_by(ClinicMessage.created_at.asc()).all()
    print('all messages for thread:', [(m.sender, m.text) for m in msgs_all])

    # Re-login as parent user
    login_page = client.get('/auth/login')
    m_login = re.search(r'name="csrf_token" value="([^"]+)"', login_page.get_data(as_text=True))
    login_csrf = m_login.group(1) if m_login else None
    client.post('/auth/login', data={'email': u.email, 'password': 'password123', 'csrf_token': login_csrf}, follow_redirects=True)

    dash_page = client.get('/dashboard', follow_redirects=True)
    m3 = re.search(r'id="csrfToken" data-token="([^"]+)"', dash_page.get_data(as_text=True))
    token3 = m3.group(1) if m3 else None

    # Test PaPrep Assistant Bot Endpoint
    res_bot = client.post('/chat/bot', json={'text': 'fever guidance'}, headers={'X-CSRFToken': token3})
    print('bot status', res_bot.status_code, 'bot ok:', res_bot.get_json().get('ok'))

    # Test Mark Notifications Read Endpoint
    res_notif = client.post('/api/notifications/mark-read', json={'id': 'msg_1'}, headers={'X-CSRFToken': token3})
    print('mark read status', res_notif.status_code, 'notif ok:', res_notif.get_json().get('ok'))




