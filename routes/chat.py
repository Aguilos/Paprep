import os
import uuid
from flask import Blueprint, request, render_template, jsonify, session, redirect, url_for, flash, current_app
from flask_login import current_user, login_required
from app import db, csrf, socketio
from models import ClinicMessage, Clinic, User, ClinicAccount
from datetime import datetime
from werkzeug.utils import secure_filename

chat_bp = Blueprint('chat', __name__, url_prefix='/chat')

ALLOWED_FILE_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt', 'xls', 'xlsx', 'zip'}
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def _allowed(filename, allowed_set):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_set


@chat_bp.route('/upload', methods=['POST'])
@login_required
def upload_attachment():
    """Handle file or image attachment uploads for clinic chat."""
    clinic_id = request.form.get('clinic_id')
    upload_type = request.form.get('upload_type', 'file')  # 'image' or 'file'
    file = request.files.get('attachment')

    if not clinic_id or not file or file.filename == '':
        return jsonify({'error': 'clinic_id and attachment file required'}), 400

    clinic = Clinic.query.get(clinic_id)
    if not clinic:
        return jsonify({'error': 'clinic not found'}), 404

    allowed_set = ALLOWED_IMAGE_EXTENSIONS if upload_type == 'image' else ALLOWED_FILE_EXTENSIONS
    if not _allowed(file.filename, allowed_set):
        allowed_str = ', '.join(sorted(allowed_set))
        return jsonify({'error': f'File type not allowed. Accepted: {allowed_str}'}), 400

    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'chat')
    os.makedirs(upload_dir, exist_ok=True)

    ext = file.filename.rsplit('.', 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    save_path = os.path.join(upload_dir, unique_name)
    file.save(save_path)

    relative_url = f"/static/uploads/chat/{unique_name}"

    msg = ClinicMessage(
        clinic_id=int(clinic_id),
        user_id=current_user.id,
        sender='user',
        text=None,
        attachment_url=relative_url,
        attachment_type=upload_type,
        created_at=datetime.utcnow()
    )
    db.session.add(msg)
    db.session.commit()

    payload = msg.to_dict()
    try:
        room = f"chat_{clinic.id}_{current_user.id}"
        clinic_room = f"clinic_{clinic.id}"
        socketio.emit('chat_message', {'clinic_id': clinic.id, 'user_id': current_user.id, 'message': payload}, room=room)
        socketio.emit('unread_update', {'clinic_id': clinic.id, 'user_id': current_user.id, 'last_message': payload}, room=clinic_room)
    except Exception:
        pass

    return jsonify({'ok': True, 'message': payload})


@chat_bp.route('/upload_reply', methods=['POST'])
def upload_reply_attachment():
    """Handle file or image attachment uploads from clinic staff side."""
    clinic_account_id = session.get('clinic_account_id')
    if not clinic_account_id:
        return jsonify({'error': 'clinic login required'}), 403

    clinic = Clinic.query.filter_by(clinic_account_id=clinic_account_id).first()
    if not clinic:
        return jsonify({'error': 'clinic not found'}), 404

    user_id = request.form.get('user_id')
    upload_type = request.form.get('upload_type', 'file')
    file = request.files.get('attachment')

    if not user_id or not file or file.filename == '':
        return jsonify({'error': 'user_id and attachment file required'}), 400

    allowed_set = ALLOWED_IMAGE_EXTENSIONS if upload_type == 'image' else ALLOWED_FILE_EXTENSIONS
    if not _allowed(file.filename, allowed_set):
        allowed_str = ', '.join(sorted(allowed_set))
        return jsonify({'error': f'File type not allowed. Accepted: {allowed_str}'}), 400

    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'chat')
    os.makedirs(upload_dir, exist_ok=True)

    ext = file.filename.rsplit('.', 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    save_path = os.path.join(upload_dir, unique_name)
    file.save(save_path)

    relative_url = f"/static/uploads/chat/{unique_name}"

    msg = ClinicMessage(
        clinic_id=clinic.id,
        user_id=int(user_id),
        sender='clinic',
        text=None,
        attachment_url=relative_url,
        attachment_type=upload_type,
        created_at=datetime.utcnow()
    )
    db.session.add(msg)
    db.session.commit()

    payload = msg.to_dict()
    try:
        room = f"chat_{clinic.id}_{user_id}"
        user_room = f"user_{user_id}"
        socketio.emit('chat_message', {'clinic_id': clinic.id, 'user_id': int(user_id), 'message': payload}, room=room)
        socketio.emit('unread_update', {'clinic_id': clinic.id, 'user_id': int(user_id), 'last_message': payload}, room=user_room)
    except Exception:
        pass

    return jsonify({'ok': True, 'message': payload})


@chat_bp.route('/send', methods=['POST'])
@login_required
def send_message():
    clinic_id = request.form.get('clinic_id') or request.json.get('clinic_id')
    text = request.form.get('text') or request.json.get('text')
    if not clinic_id or not text:
        return jsonify({'error': 'clinic_id and text required'}), 400
    clinic = Clinic.query.get(clinic_id)
    if not clinic:
        return jsonify({'error': 'clinic not found'}), 404
    msg = ClinicMessage(
        clinic_id=clinic.id,
        user_id=current_user.id,
        sender='user',
        text=text,
        created_at=datetime.utcnow()
    )
    db.session.add(msg)
    db.session.commit()
    payload = msg.to_dict()
    try:
        room = f"chat_{clinic.id}_{current_user.id}"
        clinic_room = f"clinic_{clinic.id}"
        socketio.emit('chat_message', {'clinic_id': clinic.id, 'user_id': current_user.id, 'message': payload}, room=room)
        socketio.emit('unread_update', {'clinic_id': clinic.id, 'user_id': current_user.id, 'last_message': payload}, room=clinic_room)
    except Exception:
        pass
    return jsonify({'ok': True, 'message': payload})


@chat_bp.route('/history/<int:clinic_id>')
def history(clinic_id):
    clinic = Clinic.query.get_or_404(clinic_id)
    clinic_account_id = session.get('clinic_account_id')
    user_id = request.args.get('user_id', type=int)

    # 1. If user_id is explicitly provided in query params
    if user_id:
        if clinic_account_id:
            c_acc = Clinic.query.filter_by(clinic_account_id=clinic_account_id).first()
            if c_acc and c_acc.id == clinic.id:
                unread = ClinicMessage.query.filter_by(clinic_id=clinic.id, user_id=user_id, sender='user', is_read=False).all()
                for m in unread:
                    m.is_read = True
                if unread:
                    db.session.commit()
                msgs = ClinicMessage.query.filter_by(clinic_id=clinic.id, user_id=user_id)\
                    .order_by(ClinicMessage.created_at.asc()).all()
                return jsonify([m.to_dict() for m in msgs])

        if current_user.is_authenticated and current_user.id == user_id:
            msgs = ClinicMessage.query.filter_by(clinic_id=clinic.id, user_id=user_id)\
                .order_by(ClinicMessage.created_at.asc()).all()
            return jsonify([m.to_dict() for m in msgs])

    # 2. If user_id is not provided, check if current parent user is logged in
    if current_user.is_authenticated:
        msgs = ClinicMessage.query.filter_by(clinic_id=clinic.id, user_id=current_user.id)\
            .order_by(ClinicMessage.created_at.asc()).all()
        return jsonify([m.to_dict() for m in msgs])

    # 3. Default fallback for guests or missing parameters: return empty message list cleanly (200 OK)
    return jsonify([])




@chat_bp.route('/inbox')
def clinic_inbox():
    clinic_account_id = session.get('clinic_account_id')
    if not clinic_account_id:
        flash('Clinic login required to view inbox.', 'warning')
        return redirect(url_for('clinic_portal.login'))
    clinic = Clinic.query.filter_by(clinic_account_id=clinic_account_id).first()
    if not clinic:
        flash('No clinic found for this account.', 'warning')
        return redirect(url_for('clinic_portal.dashboard'))
    from sqlalchemy import func
    threads = db.session.query(ClinicMessage.user_id, func.max(ClinicMessage.created_at).label('last'))\
        .filter(ClinicMessage.clinic_id == clinic.id)\
        .group_by(ClinicMessage.user_id)\
        .order_by(func.max(ClinicMessage.created_at).desc()).all()
    users = []
    for uid, last in threads:
        user = User.query.get(uid)
        last_msg = ClinicMessage.query.filter_by(clinic_id=clinic.id, user_id=uid).order_by(ClinicMessage.created_at.desc()).first()
        unread_count = ClinicMessage.query.filter_by(clinic_id=clinic.id, user_id=uid, sender='user', is_read=False).count()
        users.append({'user': {'id': user.id, 'name': f'{user.first_name} {user.last_name}', 'email': user.email}, 'last': last_msg.to_dict() if last_msg else None, 'unread_count': unread_count})
    account = ClinicAccount.query.get(clinic_account_id)
    return render_template('clinic_portal/inbox.html', account=account, clinic=clinic, threads=users)


@chat_bp.route('/reply', methods=['POST'])
def clinic_reply():
    clinic_account_id = session.get('clinic_account_id')
    if not clinic_account_id:
        return jsonify({'error': 'clinic login required'}), 403
    clinic = Clinic.query.filter_by(clinic_account_id=clinic_account_id).first()
    if not clinic:
        return jsonify({'error': 'clinic not found'}), 404
    user_id = request.form.get('user_id') or request.json.get('user_id')
    text = request.form.get('text') or request.json.get('text')
    if not user_id or not text:
        return jsonify({'error': 'user_id and text required'}), 400
    msg = ClinicMessage(clinic_id=clinic.id, user_id=user_id, sender='clinic', text=text)
    db.session.add(msg)
    db.session.commit()
    payload = msg.to_dict()
    try:
        room = f"chat_{clinic.id}_{user_id}"
        user_room = f"user_{user_id}"
        socketio.emit('chat_message', {'clinic_id': clinic.id, 'user_id': int(user_id), 'message': payload}, room=room)
        socketio.emit('unread_update', {'clinic_id': clinic.id, 'user_id': int(user_id), 'last_message': payload}, room=user_room)
    except Exception:
        pass
    return jsonify({'ok': True, 'message': payload})


# ---------------------------------------------------------------------------
# WebSocket Event Handlers Registration
# ---------------------------------------------------------------------------

def register_socket_events(sio):
    from flask_socketio import emit, join_room, leave_room

    @sio.on('join')
    def handle_join(data):
        try:
            cid = data.get('clinic_id')
            uid = data.get('user_id')
            if cid and uid:
                chat_room = f"chat_{cid}_{uid}"
                clinic_room = f"clinic_{cid}"
                user_room = f"user_{uid}"
                join_room(chat_room)
                join_room(clinic_room)
                join_room(user_room)
                emit('room_joined', {'room': chat_room, 'ok': True})
        except Exception as e:
            print("Socket join error:", e)

    @sio.on('send_message')
    def handle_send_message(data):
        try:
            cid = data.get('clinic_id')
            uid = data.get('user_id') or (current_user.id if current_user.is_authenticated else None)
            text = (data.get('text') or '').strip()
            if not cid or not uid or not text:
                emit('error', {'message': 'clinic_id, user_id, and text required'})
                return
            
            msg = ClinicMessage(
                clinic_id=int(cid),
                user_id=int(uid),
                sender='user',
                text=text,
                created_at=datetime.utcnow()
            )
            db.session.add(msg)
            db.session.commit()
            
            payload = msg.to_dict()
            room = f"chat_{cid}_{uid}"
            clinic_room = f"clinic_{cid}"
            
            sio.emit('chat_message', {'clinic_id': int(cid), 'user_id': int(uid), 'message': payload}, room=room)
            sio.emit('unread_update', {
                'clinic_id': int(cid),
                'user_id': int(uid),
                'last_message': payload
            }, room=clinic_room)
        except Exception as e:
            print("Socket send_message error:", e)
            emit('error', {'message': str(e)})

    @sio.on('clinic_reply')
    def handle_clinic_reply(data):
        try:
            cid = data.get('clinic_id')
            uid = data.get('user_id')
            text = (data.get('text') or '').strip()
            if not cid or not uid or not text:
                emit('error', {'message': 'clinic_id, user_id, and text required'})
                return
            
            msg = ClinicMessage(
                clinic_id=int(cid),
                user_id=int(uid),
                sender='clinic',
                text=text,
                created_at=datetime.utcnow()
            )
            db.session.add(msg)
            db.session.commit()
            
            payload = msg.to_dict()
            room = f"chat_{cid}_{uid}"
            user_room = f"user_{uid}"
            
            sio.emit('chat_message', {'clinic_id': int(cid), 'user_id': int(uid), 'message': payload}, room=room)
            sio.emit('unread_update', {
                'clinic_id': int(cid),
                'user_id': int(uid),
                'last_message': payload
            }, room=user_room)
        except Exception as e:
            print("Socket clinic_reply error:", e)
            emit('error', {'message': str(e)})

    @sio.on('typing')
    def handle_typing(data):
        try:
            cid = data.get('clinic_id')
            uid = data.get('user_id')
            sender = data.get('sender', 'user')
            is_typing = data.get('is_typing', True)
            if cid and uid:
                room = f"chat_{cid}_{uid}"
                sio.emit('typing_status', {
                    'clinic_id': int(cid),
                    'user_id': int(uid),
                    'sender': sender,
                    'is_typing': bool(is_typing)
                }, room=room, include_self=False)
        except Exception:
            pass

    @sio.on('mark_read')
    def handle_mark_read(data):
        try:
            cid = data.get('clinic_id')
            uid = data.get('user_id')
            reader = data.get('reader')
            if cid and uid:
                if reader == 'clinic':
                    unread = ClinicMessage.query.filter_by(clinic_id=cid, user_id=uid, sender='user', is_read=False).all()
                else:
                    unread = ClinicMessage.query.filter_by(clinic_id=cid, user_id=uid, sender='clinic', is_read=False).all()
                for m in unread:
                    m.is_read = True
                if unread:
                    db.session.commit()
                room = f"chat_{cid}_{uid}"
                sio.emit('messages_read', {'clinic_id': int(cid), 'user_id': int(uid), 'reader': reader}, room=room)
        except Exception:
            pass

    @sio.on('bot_query')
    def handle_bot_query(data):
        try:
            text = (data.get('text') or '').strip()
            if not text:
                return
            reply_text, shortcuts, actions = match_bot_intent(text)
            emit('bot_response', {
                'ok': True,
                'sender': 'assistant',
                'text': reply_text,
                'shortcuts': shortcuts,
                'actions': actions,
                'created_at': datetime.utcnow().isoformat()
            })
        except Exception as e:
            print("Socket bot_query error:", e)


# ---------------------------------------------------------------------------
# PaPrep Assistant Automated Chatbot Engine
# ---------------------------------------------------------------------------

def match_bot_intent(text):
    text = text.lower()

    nav_shortcuts = [
        {'label': 'Nutrition Tracker', 'url': url_for('symptoms.health_checklist'), 'icon': 'bi-apple'},
        {'label': 'Symptom Checker', 'url': url_for('symptoms.symptom_checker'), 'icon': 'bi-clipboard2-pulse'},
        {'label': 'Find a Clinic', 'url': url_for('clinics.clinic_locator'), 'icon': 'bi-hospital'},
        {'label': 'Learning Modules', 'url': url_for('modules.list_modules'), 'icon': 'bi-book'},
    ]

    # 1. Emergency / Safety
    if any(k in text for k in ['emergency', 'seizure', 'breathing', 'convulsion', '911', '112', 'unconscious', 'emergency room', 'er visit', 'er room', 'danger', 'bleeding']):

        reply = (
            "🚨 **Emergency Alert**: If your child is experiencing difficulty breathing, seizures, loss of consciousness, "
            "or severe trauma, please **call emergency services (911 / 112)** or proceed to the nearest Emergency Room immediately.\n\n"
            "For non-emergency symptom triage, use our Symptom Checker."
        )
        shortcuts = [
            {'label': 'Symptom Checker', 'url': url_for('symptoms.symptom_checker'), 'icon': 'bi-clipboard2-pulse'},
            {'label': 'Find Nearest Clinic', 'url': url_for('clinics.clinic_locator'), 'icon': 'bi-hospital'},
        ]
        actions = ["What are red flag symptoms?", "Fever guidance", "Find a clinic"]
        return reply, shortcuts, actions

    # 2. Fever care & guidance
    elif any(k in text for k in ['fever', 'temperature', 'hot', 'feverish', 'high temp']):
        reply = (
            "🌡️ **Fever Care Guidance**:\n"
            "• **Mild Fever (37.5°C - 38.5°C)**: Offer plenty of fluids, dress lightly, and monitor temperature every 4 hours.\n"
            "• **High Fever (above 38.5°C)**: Consult your pediatrician within 24 hours. For infants under 3 months, any fever requires immediate medical evaluation.\n"
            "• **Urgent Signs**: Seek emergency care if accompanied by a rash, wheezing, or lethargy."
        )
        shortcuts = [
            {'label': 'Check Symptoms', 'url': url_for('symptoms.symptom_checker'), 'icon': 'bi-clipboard2-pulse'},
            {'label': 'Daily Health Checklist', 'url': url_for('symptoms.health_checklist'), 'icon': 'bi-clipboard2-heart'},
        ]
        actions = ["Nutrition tips", "Emergency red flags", "Contact a clinic"]
        return reply, shortcuts, actions

    # 3. Nutrition & Feeding
    elif any(k in text for k in ['nutrition', 'food', 'diet', 'feed', 'breastfeeding', 'formula', 'water', 'snack', 'eating', 'meal', 'fruit']):
        reply = (
            "🍎 **Child Nutrition Tips**:\n"
            "• **0–12 Months**: Breast milk or formula is primary. Introduce soft purees/solids around 6 months.\n"
            "• **1–5 Years**: Provide balanced meals with protein, grains, fruits/vegetables, dairy, and adequate hydration. Avoid sugary junk foods.\n"
            "• Track daily meals and hydration on your child's Health Checklist!"
        )
        shortcuts = [
            {'label': 'Log Today\'s Meals', 'url': url_for('symptoms.health_checklist'), 'icon': 'bi-apple'},
            {'label': 'Nutrition Guides', 'url': url_for('modules.list_modules', category='nutrition'), 'icon': 'bi-book'},
        ]
        actions = ["Fever care", "Daily checklist", "Find a clinic"]
        return reply, shortcuts, actions

    # 4. Clinic / Doctor / Consultation
    elif any(k in text for k in ['clinic', 'doctor', 'pediatrician', 'consult', 'appointment', 'hospital', 'nearby', 'map', 'find']):
        reply = (
            "🏥 **Clinic & Online Consultation**:\n"
            "PaPrep helps you discover nearby pediatric clinics with geolocation maps, operating hours, phone numbers, and direct live consultation messaging with clinic staff."
        )
        shortcuts = [
            {'label': 'Find Nearby Clinics', 'url': url_for('clinics.clinic_locator'), 'icon': 'bi-hospital'},
        ]
        actions = ["Symptom guidance", "Nutrition tips", "Emergency help"]
        return reply, shortcuts, actions

    # 5. Checklist / Daily monitoring
    elif any(k in text for k in ['checklist', 'daily', 'monitor', 'sleep', 'hygiene', 'bath', 'teeth', 'play', 'log']):
        reply = (
            "📋 **Daily Health & Dietary Checklist**:\n"
            "Track your child's daily meals, hydration, sleep, active play, and health signs tailored to their exact age bracket (0–12m, 1–2y, 2–3y, 3–4y, 4–5y)."
        )
        shortcuts = [
            {'label': 'Open Health Checklist', 'url': url_for('symptoms.health_checklist'), 'icon': 'bi-clipboard2-heart'},
        ]
        actions = ["Nutrition tips", "Fever guidance", "Symptom checker"]
        return reply, shortcuts, actions

    # 6. Vaccination Schedule & Immunizations
    elif any(k in text for k in ['vaccine', 'vaccination', 'shot', 'immunization', 'hepb', 'dtap', 'polio', 'booster', 'vax']):
        reply = (
            "💉 **Vaccination Schedule & Immunizations**:\n"
            "• **Birth - 2 Months**: BCG, Hepatitis B, DTaP, IPV (Polio), Hib, PCV.\n"
            "• **4 - 6 Months**: DTaP, IPV, Hib, PCV 2nd & 3rd doses, Rotavirus.\n"
            "• **12 Months+**: MMR (Measles, Mumps, Rubella), Varicella, Hepatitis A, annual Flu shot.\n\n"
            "📌 *Note*: This is general reference guidance. Actual vaccine schedules must be confirmed with your pediatrician or health clinic."
        )
        shortcuts = [
            {'label': 'Find Nearby Clinic', 'url': url_for('clinics.clinic_locator'), 'icon': 'bi-hospital'},
            {'label': 'Learning Modules', 'url': url_for('modules.list_modules', category='health'), 'icon': 'bi-book'},
        ]
        actions = ["Medication safety", "Fever care guidance", "Find a clinic"]
        return reply, shortcuts, actions

    # 7. Medication & Dosing Safety
    elif any(k in text for k in ['medicine', 'medication', 'dose', 'dosage', 'paracetamol', 'ibuprofen', 'calpol', 'tempra', 'syrup', 'drops']):
        reply = (
            "💊 **Medication & Dosing Safety**:\n"
            "• **Safety First**: Pediatric medication dosing depends strictly on your child's **weight and exact age**, not just age alone.\n"
            "• **Always Confirm**: Always check with a licensed pediatrician or pharmacist for exact dosage instructions before administering any medicine.\n"
            "• **Never Give Aspirin**: Aspirin should never be given to infants or children due to the risk of severe complications (Reye's syndrome).\n\n"
            "Need specific guidance? Connect directly with clinic staff via Live Clinic chat!"
        )
        shortcuts = [
            {'label': 'Find a Clinic', 'url': url_for('clinics.clinic_locator'), 'icon': 'bi-hospital'},
            {'label': 'Symptom Checker', 'url': url_for('symptoms.symptom_checker'), 'icon': 'bi-clipboard2-pulse'},
        ]
        actions = ["Vaccination schedule", "Fever care guidance", "Emergency red flags"]
        return reply, shortcuts, actions

    # Default / Greeting
    else:
        reply = (
            "👋 **Hi! I'm your PaPrep Assistant.**\n"
            "I can answer parenting questions regarding nutrition, fever care, vaccine schedules, medication safety, or direct you to key app features.\n\n"
            "Select a topic below or type your question!"
        )
        shortcuts = nav_shortcuts
        actions = [
            "Fever care guidance",
            "Nutrition tips for my child",
            "Vaccination schedule",
            "Medication safety"
        ]
        return reply, shortcuts, actions



@chat_bp.route('/bot', methods=['POST'])
@login_required
def bot_reply():
    data = request.get_json(silent=True) or {}
    text = (data.get('text') or '').strip()
    if not text:
        return jsonify({'error': 'Message text is required'}), 400

    reply_text, shortcuts, actions = match_bot_intent(text)

    return jsonify({
        'ok': True,
        'sender': 'assistant',
        'text': reply_text,
        'shortcuts': shortcuts,
        'actions': actions,
        'created_at': datetime.utcnow().isoformat()
    })

