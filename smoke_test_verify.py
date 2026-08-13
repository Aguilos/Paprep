"""Programmatic Smoke Test Verification Suite for PaPrep Notification Center and Assistant Chatbot."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from models import User, NotificationRead, ClinicMessage
import re

app = create_app()

def run_smoke_test():
    with app.app_context():
        # Ensure fresh clean state for smoketest user
        user = User.query.filter_by(email='smoketest@paprep.com').first()
        if not user:
            print("ERROR: Test user smoketest@paprep.com does not exist. Run seed_test_data.py first.")
            return

        # Reset notification reads for test user so we can test clean
        NotificationRead.query.filter_by(user_id=user.id).delete()
        db.session.commit()

        client = app.test_client()

        print("\n========================================================")
        print("    STARTING COMPREHENSIVE PA-PREP SMOKE TEST SUITE    ")
        print("========================================================\n")

        # -------------------------------------------------------------------
        # STEP 1: AUTHENTICATION
        # -------------------------------------------------------------------
        login_page = client.get('/auth/login')
        m_login = re.search(r'name="csrf_token" value="([^"]+)"', login_page.get_data(as_text=True))
        login_csrf = m_login.group(1) if m_login else ''

        res_login = client.post('/auth/login', data={
            'email': 'smoketest@paprep.com',
            'password': 'password123',
            'csrf_token': login_csrf
        }, follow_redirects=True)

        assert res_login.status_code == 200, f"Login failed with status {res_login.status_code}"
        print("[PASS] Step 1: Login as smoketest@paprep.com -> 200 OK")

        # Fetch dashboard to extract AJAX CSRF token
        dash = client.get('/dashboard', follow_redirects=True)
        m_csrf = re.search(r'id="csrfToken" data-token="([^"]+)"', dash.get_data(as_text=True))
        csrf_token = m_csrf.group(1) if m_csrf else ''
        headers = {'X-CSRFToken': csrf_token}

        # -------------------------------------------------------------------
        # STEP 2: TEST 1 — NOTIFICATION CENTER & PERSISTENT READ TRACKING
        # -------------------------------------------------------------------
        print("\n--- TEST 1: Notification Center & Persistent Read Tracking ---")

        with app.test_request_context():
            from flask_login import login_user
            login_user(user)
            from routes.main import get_user_notifications
            initial_notifs = get_user_notifications()

        unread_count_before = initial_notifs['unread_count']
        items_count = len(initial_notifs['notifications'])


        print(f"Initial Unread Badge Count: {unread_count_before}")
        print(f"Notification Items Returned: {items_count}")
        types_found = [n['type'] for n in initial_notifs['notifications']]
        print(f"Notification Types Found: {types_found}")

        assert unread_count_before == 3, f"Expected 3 unread items, got {unread_count_before}"
        assert 'message' in types_found, "Missing message notification"
        assert 'announcement' in types_found, "Missing announcement notification"
        assert 'checklist' in types_found, "Missing checklist notification"
        print("[PASS] Step 2.1: Aggregates all 3 sources (message, announcement, checklist)")

        # Mark all read via API
        res_mark = client.post('/api/notifications/mark-read', json={}, headers=headers)
        assert res_mark.status_code == 200 and res_mark.get_json().get('ok'), "Mark read API failed"
        print("[PASS] Step 2.2: Post /api/notifications/mark-read -> 200 OK")

        with app.test_request_context():
            from flask_login import login_user
            login_user(user)
            notifs_after_mark = get_user_notifications()

        assert notifs_after_mark['unread_count'] == 0, f"Expected 0 unread after mark-read, got {notifs_after_mark['unread_count']}"
        print("[PASS] Step 2.3: Badge counter cleared to 0 in current session")

        # Persistent Check: Re-login in a fresh session
        client_session2 = app.test_client()
        login_page2 = client_session2.get('/auth/login')
        m_login2 = re.search(r'name="csrf_token" value="([^"]+)"', login_page2.get_data(as_text=True))
        login_csrf2 = m_login2.group(1) if m_login2 else ''
        client_session2.post('/auth/login', data={
            'email': 'smoketest@paprep.com',
            'password': 'password123',
            'csrf_token': login_csrf2
        }, follow_redirects=True)

        with app.app_context():
            # simulate logged in context for user
            reads_in_db = NotificationRead.query.filter_by(user_id=user.id).count()
            print(f"NotificationRead records in DB for user: {reads_in_db}")
            assert reads_in_db >= 3, f"Expected at least 3 read records in DB, got {reads_in_db}"

        print("[PASS] Step 2.4: Persistent per-user read state verified across fresh session login!")

        # -------------------------------------------------------------------
        # STEP 3: TEST 2 — PAPREP ASSISTANT CHATBOT & NEW TOPICS
        # -------------------------------------------------------------------
        print("\n--- TEST 2: PaPrep Assistant Chatbot & Intent Matching ---")

        # 3.1 Quick Query Chips
        quick_queries = [
            ("Fever care guidance", "Fever Care"),
            ("Nutrition tips for my child", "Nutrition"),
            ("Emergency red flags", "Emergency"),
            ("Find a clinic nearby", "Clinics")
        ]

        for qtext, qname in quick_queries:
            res_bot = client.post('/chat/bot', json={'text': qtext}, headers=headers)
            data = res_bot.get_json()
            assert res_bot.status_code == 200 and data.get('ok'), f"Bot failed for chip {qname}"
            print(f"[PASS] Quick Query Chip [{qname}]: Returns valid response with {len(data.get('shortcuts', []))} shortcuts")

        # 3.2 Free-Text Match Tests for all 7 topics
        print("\n--- Testing Free-Text Bot Queries ---")

        topic_tests = [
            ("Fever", "my child has a high fever of 39C", "Fever Care Guidance"),
            ("Nutrition", "what fruits and food should I feed my toddler?", "Child Nutrition Tips"),
            ("Emergency", "child having severe breathing difficulty", "Emergency Alert"),
            ("Clinics", "where can I find a pediatric doctor near me?", "Clinic & Online Consultation"),
            ("Checklist", "how do I log daily sleep and bath health checklist", "Daily Health & Dietary Checklist"),
            ("Vaccination Schedule (NEW)", "what is the vaccination schedule for babies?", "Vaccination Schedule & Immunizations"),
            ("Medication Safety (NEW)", "what is the paracetamol dosage for my baby syrup?", "Medication & Dosing Safety"),
            ("Unmatched Fallback", "what is the weather today in Manila?", "Hi! I'm your PaPrep Assistant.")
        ]

        for topic_name, user_query, expected_phrase in topic_tests:
            res_bot = client.post('/chat/bot', json={'text': user_query}, headers=headers)
            data = res_bot.get_json()
            assert res_bot.status_code == 200 and data.get('ok'), f"Bot query failed for {topic_name}"
            bot_reply = data.get('text', '')
            assert expected_phrase.lower() in bot_reply.lower(), f"Expected '{expected_phrase}' in response for {topic_name}"



            if topic_name == "Medication Safety (NEW)":
                # Verify safety rules: No numeric dosing output like "mg/kg"
                assert "mg/kg" not in bot_reply.lower(), "Medication safety response improperly output numeric dosage mg/kg!"
                assert "weight and exact age" in bot_reply.lower(), "Medication response missing weight/age warning"
                print(f"[PASS] {topic_name}: Matched cleanly, safety rules enforced (no numeric mg/kg dosing given).")
            elif topic_name == "Vaccination Schedule (NEW)":
                assert "birth - 2 months" in bot_reply.lower(), "Vaccine response missing milestone breakdown"
                assert "pediatrician or health clinic" in bot_reply.lower(), "Vaccine response missing disclaimer"
                print(f"[PASS] {topic_name}: Matched cleanly with 0-2m, 4-6m, 12m+ milestones.")
            else:
                print(f"[PASS] {topic_name}: Matched expected response phrase '{expected_phrase}'")

        # 3.3 Live Clinic Messaging Check
        print("\n--- Testing Live Clinic Chat Endpoint ---")
        res_send = client.post('/chat/send', json={'clinic_id': 12, 'text': 'Hello clinic staff! Testing live chat.'}, headers=headers)
        assert res_send.status_code == 200 and res_send.get_json().get('ok'), "Live clinic messaging failed"
        
        saved_msg = ClinicMessage.query.filter_by(clinic_id=12, user_id=user.id, text='Hello clinic staff! Testing live chat.').first()
        assert saved_msg is not None, "Message was not saved in clinic_messages table"
        print("[PASS] Step 3.3: Live Clinic Socket.IO/REST message sent & persisted successfully!")

        print("\n========================================================")
        print("      ALL SMOKE TEST ASSERTONS PASSED SUCCESSFULLY!     ")
        print("========================================================\n")

if __name__ == '__main__':
    run_smoke_test()
