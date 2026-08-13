from datetime import date, datetime, timedelta
import json

from flask import Blueprint, render_template, redirect, url_for, session, jsonify, request
from flask_login import login_required, current_user

from models import HealthChecklist, ClinicAnnouncement, ClinicMessage, Clinic, NotificationRead
from app import db
from utils import today_pht

main_bp = Blueprint('main', __name__)


def get_user_notifications():
    if not current_user.is_authenticated:
        return {'notifications': [], 'unread_count': 0}

    notifications = []
    read_records = NotificationRead.query.filter_by(user_id=current_user.id).all()
    read_ids = set(r.notification_key for r in read_records)

    # 1. Unread clinic messages
    unread_msgs = ClinicMessage.query.filter_by(
        user_id=current_user.id, sender='clinic', is_read=False
    ).order_by(ClinicMessage.created_at.desc()).all()

    for msg in unread_msgs:
        nid = f"msg_{msg.id}"
        clinic = Clinic.query.get(msg.clinic_id)
        clinic_name = clinic.name if clinic else "Clinic"
        notifications.append({
            'id': nid,
            'type': 'message',
            'icon': 'bi-chat-dots-fill',
            'color': '#4E97D9',
            'title': f"Message from {clinic_name}",
            'body': msg.text[:80] + ('...' if len(msg.text) > 80 else ''),
            'link': url_for('clinics.clinic_detail', clinic_id=msg.clinic_id),
            'time': msg.created_at.strftime('%b %d, %H:%M'),
            'is_read': nid in read_ids
        })

    # 2. Clinic announcements
    today = today_pht()
    announcements = ClinicAnnouncement.query.filter(
        ClinicAnnouncement.is_active == True,
        (ClinicAnnouncement.expires_at.is_(None)) | (ClinicAnnouncement.expires_at >= today)
    ).order_by(ClinicAnnouncement.created_at.desc()).limit(5).all()

    for ann in announcements:
        nid = f"ann_{ann.id}"
        clinic = Clinic.query.get(ann.clinic_id)
        clinic_name = clinic.name if clinic else "Clinic"
        notifications.append({
            'id': nid,
            'type': 'announcement',
            'icon': 'bi-megaphone-fill',
            'color': '#FF8C42',
            'title': f"{ann.title}",
            'body': f"{clinic_name}: {ann.body[:80]}...",
            'link': url_for('clinics.clinic_detail', clinic_id=ann.clinic_id),
            'time': ann.created_at.strftime('%b %d'),
            'is_read': nid in read_ids
        })

    # 3. Daily Health Checklist reminder for active child
    active_child_id = session.get('active_child_id')
    active_child = None
    if current_user.children:
        active_child = next((c for c in current_user.children if c.id == active_child_id), current_user.children[0])

    if active_child:
        today_date = date.today()
        checklist_done = HealthChecklist.query.filter_by(
            child_id=active_child.id, date=today_date
        ).first()
        nid = f"checklist_{active_child.id}_{today_date.isoformat()}"
        if not checklist_done or len(checklist_done.get_checked()) == 0:
            notifications.append({
                'id': nid,
                'type': 'checklist',
                'icon': 'bi-clipboard2-heart-fill',
                'color': '#5CAD5C',
                'title': f"Daily Health Reminder",
                'body': f"Log {active_child.name}'s daily meals & health monitoring checklist.",
                'link': url_for('symptoms.health_checklist'),
                'time': 'Today',
                'is_read': nid in read_ids
            })

    unread_count = sum(1 for n in notifications if not n['is_read'])
    return {'notifications': notifications, 'unread_count': unread_count}


@main_bp.app_context_processor
def inject_notifications():
    return {'notifications_summary': get_user_notifications()}


@main_bp.route('/api/notifications/mark-read', methods=['POST'])
def mark_notification_read():
    # Return JSON 401 for unauthenticated requests (e.g. clinic portal users)
    # so the JS caller gets JSON rather than an HTML redirect page.
    if not current_user.is_authenticated:
        return jsonify({'ok': False, 'error': 'login required'}), 401

    data = request.get_json(silent=True) or {}
    nid = data.get('id')
    if nid:
        keys_to_mark = [nid]
    else:
        notifs = get_user_notifications()['notifications']
        keys_to_mark = [n['id'] for n in notifs]

    for key in keys_to_mark:
        existing = NotificationRead.query.filter_by(user_id=current_user.id, notification_key=key).first()
        if not existing:
            nr = NotificationRead(user_id=current_user.id, notification_key=key)
            db.session.add(nr)
    db.session.commit()

    return jsonify({'ok': True, 'unread_count': get_user_notifications()['unread_count']})



@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        if not current_user.children:
            return redirect(url_for('children.create_child'))
        return redirect(url_for('main.dashboard'))
    return render_template('index.html')


@main_bp.route('/dashboard')
@login_required
def dashboard():
    if not current_user.children:
        return redirect(url_for('children.create_child'))

    active_child_id = session.get('active_child_id')
    active_child = next(
        (c for c in current_user.children if c.id == active_child_id),
        current_user.children[0]
    )

    # ── Health Checklist data ─────────────────────────────────
    today = date.today()
    seven_days_ago = today - timedelta(days=6)

    history_records = HealthChecklist.query.filter(
        HealthChecklist.child_id == active_child.id,
        HealthChecklist.date >= seven_days_ago,
        HealthChecklist.date <= today,
    ).all()
    history_map = {r.date: r for r in history_records}

    # Compute total items for this child's age bracket (lazy import avoids circulars)
    from routes.symptoms import CHECKLIST_ITEMS
    checklist_total = sum(
        1 for cat in CHECKLIST_ITEMS.values()
        for item in cat['items']
        if active_child.age_bracket in item['ages']
    )

    today_record = history_map.get(today)
    checklist_today_count = len(json.loads(today_record.checked_items or '[]')) if today_record else 0

    # 7-day history list (oldest → newest)
    history_days = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        rec = history_map.get(d)
        cnt = len(json.loads(rec.checked_items or '[]')) if rec else 0
        pct = round(cnt / checklist_total * 100) if checklist_total else 0
        history_days.append({
            'date': d,
            'label': d.strftime('%a'),
            'day_num': d.strftime('%d'),
            'count': cnt,
            'total': checklist_total,
            'pct': pct,
            'is_today': d == today,
        })

    return render_template('dashboard/dashboard.html',
                           active_child=active_child,
                           checklist_today_count=checklist_today_count,
                           checklist_total=checklist_total,
                           history_days=history_days,
                           page_title='Dashboard')


@main_bp.route('/special-needs')
@login_required
def special_needs():
    has_sn = any(c.child_type == 'special_needs' for c in current_user.children)
    if not has_sn:
        return redirect(url_for('main.dashboard'))
    return render_template('special_needs/special_needs.html',
                           page_title='Special Needs Support')

