from datetime import date, datetime, timedelta
import json

from flask import Blueprint, abort, render_template, redirect, url_for, session, jsonify, request
from flask_login import login_required, current_user

from models import (
    HealthChecklist, ClinicAnnouncement, ClinicMessage, Clinic,
    NotificationRead, ParentChildResource, Newsletter,
    NewsletterLike, NewsletterComment,
)
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


def get_accessible_newsletter(newsletter_id):
    newsletter = Newsletter.query.filter_by(
        id=newsletter_id, is_published=True
    ).first_or_404()
    if newsletter.child_id not in {child.id for child in current_user.children}:
        abort(404)
    return newsletter


@main_bp.route('/api/newsletters/<int:newsletter_id>/like', methods=['POST'])
@login_required
def toggle_newsletter_like(newsletter_id):
    newsletter = get_accessible_newsletter(newsletter_id)
    existing_like = NewsletterLike.query.filter_by(
        user_id=current_user.id, newsletter_id=newsletter.id
    ).first()

    if existing_like:
        db.session.delete(existing_like)
        liked = False
    else:
        db.session.add(NewsletterLike(
            user_id=current_user.id,
            newsletter_id=newsletter.id,
        ))
        liked = True

    db.session.commit()
    like_count = NewsletterLike.query.filter_by(newsletter_id=newsletter.id).count()
    return jsonify({'ok': True, 'liked': liked, 'like_count': like_count})


@main_bp.route('/api/newsletters/<int:newsletter_id>/comment', methods=['POST'])
@login_required
def add_newsletter_comment(newsletter_id):
    newsletter = get_accessible_newsletter(newsletter_id)
    data = request.get_json(silent=True) or {}
    raw_text = data.get('text', '') if isinstance(data, dict) else ''
    text = raw_text.strip() if isinstance(raw_text, str) else ''

    if not text:
        return jsonify({'ok': False, 'error': 'Comment cannot be empty'}), 400

    comment = NewsletterComment(
        user_id=current_user.id,
        newsletter_id=newsletter.id,
        text=text,
    )
    db.session.add(comment)
    db.session.commit()

    return jsonify({
        'ok': True,
        'comment': {
            'id': comment.id,
            'user_name': f'{current_user.first_name} {current_user.last_name}',
            'text': comment.text,
            'time': 'Just now',
        },
    })



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

    expanded_child_id = request.args.get('expanded_child', type=int)
    if expanded_child_id not in {child.id for child in current_user.children}:
        expanded_child_id = None

    # ── Health Checklist data for every child card ────────────
    today = date.today()
    seven_days_ago = today - timedelta(days=6)
    from routes.symptoms import CHECKLIST_ITEMS

    children_dashboard = []
    for child in current_user.children:
        history_records = HealthChecklist.query.filter(
            HealthChecklist.child_id == child.id,
            HealthChecklist.date >= seven_days_ago,
            HealthChecklist.date <= today,
        ).all()
        history_map = {r.date: r for r in history_records}

        checklist_total = sum(
            1 for cat in CHECKLIST_ITEMS.values()
            for item in cat['items']
            if child.age_bracket in item['ages']
        )
        today_record = history_map.get(today)
        checklist_today_count = len(json.loads(today_record.checked_items or '[]')) if today_record else 0

        history_days = []
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            record = history_map.get(day)
            count = len(json.loads(record.checked_items or '[]')) if record else 0
            pct = round(count / checklist_total * 100) if checklist_total else 0
            history_days.append({
                'date': day,
                'label': day.strftime('%a'),
                'day_num': day.strftime('%d'),
                'count': count,
                'total': checklist_total,
                'pct': pct,
                'is_today': day == today,
            })

        children_dashboard.append({
            'child': child,
            'checklist_today_count': checklist_today_count,
            'checklist_total': checklist_total,
            'history_days': history_days,
        })

    age_months = active_child.age_months
    resource_query = ParentChildResource.query.filter(
        ParentChildResource.target_age_min_months <= age_months,
        ParentChildResource.target_age_max_months >= age_months,
    )
    resources = resource_query.order_by(
        ParentChildResource.created_at.desc(), ParentChildResource.id.desc()
    ).limit(6).all()

    newsletters = Newsletter.query.filter_by(
        child_id=active_child.id, is_published=True
    ).order_by(Newsletter.created_at.desc(), Newsletter.id.desc()).all()
    liked_newsletter_ids = {
        like.newsletter_id
        for like in NewsletterLike.query.filter_by(user_id=current_user.id).all()
    }

    return render_template('dashboard/dashboard.html',
                           active_child=active_child,
                           children_dashboard=children_dashboard,
                           expanded_child_id=expanded_child_id,
                           resources=resources,
                           newsletters=newsletters,
                           liked_newsletter_ids=liked_newsletter_ids,
                           page_title='Dashboard')
