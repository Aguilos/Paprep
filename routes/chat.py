from flask import Blueprint, request, render_template, jsonify, session, redirect, url_for, flash
from flask_login import current_user, login_required
from app import db, csrf, socketio
from models import ClinicMessage, Clinic, User, ClinicAccount
from datetime import datetime

chat_bp = Blueprint('chat', __name__, url_prefix='/chat')


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
    # emit to clinic room for live updates
    try:
        room = f"chat_{clinic.id}_{current_user.id}"
        socketio.emit('chat_message', {'clinic_id': clinic.id, 'user_id': current_user.id, 'message': msg.to_dict()}, room=room)
    except Exception:
        pass
    return jsonify({'ok': True, 'message': msg.to_dict()})


@chat_bp.route('/history/<int:clinic_id>')
@login_required
def history(clinic_id):
    clinic = Clinic.query.get_or_404(clinic_id)
    # If user_id provided, return only that thread; otherwise return all messages
    user_id = request.args.get('user_id', type=int)
    query = ClinicMessage.query.filter_by(clinic_id=clinic.id)
    if user_id:
        query = query.filter_by(user_id=user_id)
        # If a clinic staff is requesting a user's thread, mark incoming user messages as read
        clinic_account_id = session.get('clinic_account_id')
        if clinic_account_id:
            unread = ClinicMessage.query.filter_by(clinic_id=clinic.id, user_id=user_id, sender='user', is_read=False).all()
            for m in unread:
                m.is_read = True
            if unread:
                db.session.commit()
    msgs = query.order_by(ClinicMessage.created_at.asc()).all()
    return jsonify([m.to_dict() for m in msgs])


@chat_bp.route('/inbox')
def clinic_inbox():
    # clinic staff view: requires clinic portal session
    clinic_account_id = session.get('clinic_account_id')
    if not clinic_account_id:
        flash('Clinic login required to view inbox.', 'warning')
        return redirect(url_for('clinic_portal.login'))
    # find the clinic owned by account
    clinic = Clinic.query.filter_by(clinic_account_id=clinic_account_id).first()
    if not clinic:
        flash('No clinic found for this account.', 'warning')
        return redirect(url_for('clinic_portal.dashboard'))
    # list distinct user threads (group by user_id)
    from sqlalchemy import func
    threads = db.session.query(ClinicMessage.user_id, func.max(ClinicMessage.created_at).label('last'))\
        .filter(ClinicMessage.clinic_id == clinic.id)\
        .group_by(ClinicMessage.user_id)\
        .order_by(func.max(ClinicMessage.created_at).desc()).all()
    users = []
    for uid, last in threads:
        user = User.query.get(uid)
        last_msg = ClinicMessage.query.filter_by(clinic_id=clinic.id, user_id=uid).order_by(ClinicMessage.created_at.desc()).first()
        # compute unread messages from this user
        unread_count = ClinicMessage.query.filter_by(clinic_id=clinic.id, user_id=uid, sender='user', is_read=False).count()
        users.append({'user': {'id': user.id, 'name': f'{user.first_name} {user.last_name}', 'email': user.email}, 'last': last_msg.to_dict() if last_msg else None, 'unread_count': unread_count})
    account = ClinicAccount.query.get(clinic_account_id)
    return render_template('clinic_portal/inbox.html', account=account, clinic=clinic, threads=users)


@chat_bp.route('/reply', methods=['POST'])
def clinic_reply():
    # clinic staff sends a reply to a user's thread
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
    # emit to user room for live updates
    try:
        room = f"chat_{clinic.id}_{user_id}"
        socketio.emit('chat_message', {'clinic_id': clinic.id, 'user_id': int(user_id), 'message': msg.to_dict()}, room=room)
    except Exception:
        pass
    return jsonify({'ok': True, 'message': msg.to_dict()})
