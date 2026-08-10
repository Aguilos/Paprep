from datetime import date, timedelta
import json

from flask import Blueprint, render_template, redirect, url_for, session
from flask_login import login_required, current_user

from models import HealthChecklist

main_bp = Blueprint('main', __name__)


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
