import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import unittest
from app import create_app, db, socketio
from models import User, ClinicAccount, Clinic, ClinicMessage

class TestWebSocket(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.user = User.query.first()
        self.clinic = Clinic.query.first()

    def tearDown(self):
        self.app_context.pop()

    def test_websocket_flow(self):
        client = socketio.test_client(self.app)
        self.assertTrue(client.is_connected())

        # 1. Join event
        client.emit('join', {'clinic_id': self.clinic.id, 'user_id': self.user.id})
        rec1 = client.get_received()
        self.assertEqual(len(rec1), 1)
        self.assertEqual(rec1[0]['name'], 'room_joined')

        # 2. Send message event
        client.emit('send_message', {
            'clinic_id': self.clinic.id,
            'user_id': self.user.id,
            'text': 'Automated websocket test message'
        })
        rec2 = client.get_received()
        self.assertEqual(len(rec2), 2)
        self.assertEqual(rec2[0]['name'], 'chat_message')
        self.assertEqual(rec2[1]['name'], 'unread_update')

        # 3. Clinic reply event
        client.emit('clinic_reply', {
            'clinic_id': self.clinic.id,
            'user_id': self.user.id,
            'text': 'Automated websocket test reply'
        })
        rec3 = client.get_received()
        self.assertEqual(len(rec3), 2)
        self.assertEqual(rec3[0]['name'], 'chat_message')

        # 4. Typing indicator event
        client.emit('typing', {
            'clinic_id': self.clinic.id,
            'user_id': self.user.id,
            'sender': 'user',
            'is_typing': True
        })

        # 5. Bot query event
        client.emit('bot_query', {'text': 'Fever care guidance'})
        rec4 = client.get_received()
        self.assertEqual(len(rec4), 1)
        self.assertEqual(rec4[0]['name'], 'bot_response')

        client.disconnect()

if __name__ == '__main__':
    unittest.main()
