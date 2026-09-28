import json
from datetime import date, datetime, timedelta

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session
from flask_login import login_required, current_user

from app import db
from models import FeverReading, HealthChecklist

symptoms_bp = Blueprint('symptoms', __name__)

FEVER_DISCLAIMER = (
    "IMPORTANT DISCLAIMER: This Fever Tracker provides general temperature monitoring "
    "guidance only. It is NOT a substitute for professional medical advice, diagnosis, "
    "or treatment. Contact your child's pediatrician for medical advice. In an emergency, "
    "call emergency services (911 / 112) or go to the nearest emergency room immediately."
)


def _active_child():
    if not current_user.children:
        return None
    active_id = session.get('active_child_id')
    return next((child for child in current_user.children if child.id == active_id), current_user.children[0])


def _to_celsius(value, unit):
    return value if unit == 'C' else (value - 32) * 5 / 9


def _reading_guidance(child, readings):
    latest = readings[0] if readings else None
    if not latest:
        return {
            'severity': 'general',
            'title': 'No temperature readings yet',
            'message': 'Log a reading to receive age-aware monitoring guidance.',
            'actions': [],
        }

    recent_cutoff = datetime.utcnow() - timedelta(hours=24)
    recent_fever_count = sum(r.value_celsius >= 38 for r in readings if r.recorded_at >= recent_cutoff)
    temp = latest.value_celsius

    if (child.age_months < 3 and temp >= 38) or temp >= 40:
        return {
            'severity': 'emergency',
            'title': 'Emergency temperature reading',
            'message': 'Do not wait. An infant under 3 months with a temperature of 38°C or higher, or any child at 40°C or higher, needs immediate medical assessment.',
            'actions': ['Call emergency services (911 / 112)', 'Go to the nearest Emergency Room', 'Keep your child supervised and note when the temperature was taken', 'If a seizure, difficulty breathing, or unresponsiveness occurs, call emergency services immediately'],
        }
    if temp >= 39 or recent_fever_count >= 3:
        return {
            'severity': 'high',
            'title': 'High priority fever',
            'message': 'This temperature or repeated fever readings need prompt medical advice, especially if your child appears unwell.',
            'actions': ['Contact your pediatrician or clinic today', 'Offer age-appropriate fluids and keep your child comfortable', 'Record readings and watch for worsening symptoms', 'Seek emergency care for seizure, difficulty breathing, blue colour, or unusual unresponsiveness'],
        }
    if temp >= 38:
        return {
            'severity': 'monitor',
            'title': 'Monitor this fever',
            'message': 'A temperature of 38°C or higher is a fever. Continue monitoring and consider contacting your child’s clinician if it persists or your child seems unwell.',
            'actions': ['Recheck the temperature in a few hours', 'Offer fluids and rest', 'Use medicines only as directed by your child’s clinician', 'Seek urgent help if breathing difficulty, seizure, or severe lethargy develops'],
        }
    return {
        'severity': 'general',
        'title': 'Temperature is below the fever threshold',
        'message': 'Continue observing your child and log another reading if they seem unwell.',
        'actions': ['Keep your child comfortable', 'Continue normal fluids', 'Contact a clinician if other concerning symptoms appear'],
    }


@symptoms_bp.route('/fever-tracker', methods=['GET', 'POST'])
@login_required
def fever_tracker():
    child = _active_child()
    if not child:
        return redirect(url_for('children.create_child'))

    if request.method == 'POST':
        try:
            value = float(request.form.get('value', ''))
            unit = request.form.get('unit', 'C').upper()
            if unit not in ('C', 'F'):
                raise ValueError
            celsius = _to_celsius(value, unit)
            if not 30 <= celsius <= 45:
                raise ValueError
            recorded_at = datetime.fromisoformat(request.form.get('recorded_at', '').strip()) if request.form.get('recorded_at') else datetime.utcnow()
        except (TypeError, ValueError):
            flash('Enter a valid temperature between 30°C and 45°C.', 'error')
            return redirect(url_for('symptoms.fever_tracker'))

        reading = FeverReading(
            child_id=child.id,
            value=value,
            unit=unit,
            value_celsius=celsius,
            method=request.form.get('method', '').strip() or None,
            recorded_at=recorded_at,
        )
        db.session.add(reading)
        db.session.commit()
        flash('Temperature reading saved.', 'success')
        return redirect(url_for('symptoms.fever_tracker'))

    readings = FeverReading.query.filter_by(child_id=child.id).order_by(FeverReading.recorded_at.desc(), FeverReading.id.desc()).limit(30).all()
    return render_template('symptoms/fever_tracker.html', active_child=child, readings=readings, guidance=_reading_guidance(child, readings), disclaimer=FEVER_DISCLAIMER, page_title='Fever Tracker')


@symptoms_bp.route('/api/fever/readings', methods=['GET', 'POST'])
@login_required
def fever_readings_api():
    child = _active_child()
    if not child:
        return jsonify({'error': 'No active child.'}), 400
    if request.method == 'GET':
        readings = FeverReading.query.filter_by(child_id=child.id).order_by(FeverReading.recorded_at.desc()).limit(30).all()
        return jsonify({'readings': [{'id': r.id, 'value': r.value, 'unit': r.unit, 'method': r.method, 'recorded_at': r.recorded_at.isoformat()} for r in readings]})
    data = request.get_json(silent=True) or {}
    try:
        value = float(data['value'])
        unit = data.get('unit', 'C').upper()
        celsius = _to_celsius(value, unit)
        if unit not in ('C', 'F') or not 30 <= celsius <= 45:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        return jsonify({'error': 'Invalid temperature.'}), 400
    reading = FeverReading(child_id=child.id, value=value, unit=unit, value_celsius=celsius, method=data.get('method'))
    db.session.add(reading)
    db.session.commit()
    return jsonify({'ok': True, 'id': reading.id}), 201


# Dietary and health checklist remains available under the symptoms blueprint for compatibility.
_ALL_BRACKETS = ['0–12 months', '1–2 years', '2–3 years', '3–4 years', '4–5 years']
CHECKLIST_ITEMS = {
    'dietary': {'title': 'Dietary Monitoring', 'icon': 'bi-egg-fried', 'color': '#f97316', 'items': [
        {'key': 'breast_formula', 'label': 'Fed breast milk or formula regularly today', 'ages': ['0–12 months']},
        {'key': 'solids_intro', 'label': 'Soft solids / purees introduced (6+ months)', 'ages': ['0–12 months']},
        {'key': 'breakfast', 'label': 'Had a proper breakfast', 'ages': ['1–2 years', '2–3 years', '3–4 years', '4–5 years']},
        {'key': 'lunch', 'label': 'Had a proper lunch', 'ages': _ALL_BRACKETS},
        {'key': 'dinner', 'label': 'Had a proper dinner', 'ages': _ALL_BRACKETS},
        {'key': 'healthy_snack', 'label': 'Had a healthy snack (fruit / veg / nut butter)', 'ages': ['1–2 years', '2–3 years', '3–4 years', '4–5 years']},
        {'key': 'fruit_veg', 'label': 'Ate at least one fruit or vegetable', 'ages': _ALL_BRACKETS},
        {'key': 'protein', 'label': 'Had protein (meat / fish / eggs / beans)', 'ages': _ALL_BRACKETS},
        {'key': 'dairy', 'label': 'Had dairy (milk / yogurt / cheese)', 'ages': ['1–2 years', '2–3 years', '3–4 years', '4–5 years']},
        {'key': 'grains', 'label': 'Had grains (rice / bread / oats)', 'ages': _ALL_BRACKETS},
        {'key': 'water', 'label': 'Drank enough water / fluids today', 'ages': _ALL_BRACKETS},
        {'key': 'no_sugary', 'label': 'Avoided sugary drinks and junk food', 'ages': ['1–2 years', '2–3 years', '3–4 years', '4–5 years']},
    ]},
    'health': {'title': 'Health Monitoring', 'icon': 'bi-heart-pulse-fill', 'color': '#ef4444', 'items': [
        {'key': 'sleep_ok', 'label': 'Got adequate sleep last night', 'ages': _ALL_BRACKETS},
        {'key': 'tummy_time', 'label': 'Had supervised tummy time (≥ 3 min)', 'ages': ['0–12 months']},
        {'key': 'active_play', 'label': 'Had active play / physical activity today', 'ages': ['1–2 years', '2–3 years', '3–4 years', '4–5 years']},
        {'key': 'bath', 'label': 'Bathed and cleaned properly', 'ages': _ALL_BRACKETS},
        {'key': 'teeth', 'label': 'Brushed teeth (morning & night)', 'ages': ['1–2 years', '2–3 years', '3–4 years', '4–5 years']},
        {'key': 'vitamins', 'label': 'Took vitamins / supplements (if prescribed)', 'ages': _ALL_BRACKETS},
        {'key': 'no_fever', 'label': 'No fever or signs of illness observed', 'ages': _ALL_BRACKETS},
        {'key': 'mood_ok', 'label': 'Good mood / normal behavior today', 'ages': _ALL_BRACKETS},
        {'key': 'bowel_ok', 'label': 'Normal bowel movement / urination', 'ages': _ALL_BRACKETS},
        {'key': 'weight_check', 'label': 'Weight / growth checked this week', 'ages': _ALL_BRACKETS},
    ]},
}
SLEEP_GUIDE = {'0–12 months': '14–17 hours (newborns) / 12–16 hours (6–12 months)', '1–2 years': '11–14 hours (including naps)', '2–3 years': '11–14 hours (including naps)', '3–4 years': '10–13 hours', '4–5 years': '10–13 hours'}


def _filter_items_for_age(bracket):
    return {key: {**category, 'items': [item for item in category['items'] if bracket in item['ages']]} for key, category in CHECKLIST_ITEMS.items() if any(bracket in item['ages'] for item in category['items'])}


@symptoms_bp.route('/health-checklist', methods=['GET', 'POST'])
@login_required
def health_checklist():
    child = _active_child()
    if not child:
        return redirect(url_for('children.create_child'))
    today = date.today()
    categories = _filter_items_for_age(child.age_bracket)
    record = HealthChecklist.query.filter_by(child_id=child.id, date=today).first()
    if request.method == 'POST':
        if record is None:
            record = HealthChecklist(child_id=child.id, date=today)
            db.session.add(record)
        record.checked_items = json.dumps(request.form.getlist('items'))
        record.notes = request.form.get('notes', '').strip() or None
        db.session.commit()
        flash('Checklist saved successfully!', 'success')
        return redirect(url_for('symptoms.health_checklist'))
    checked_today = record.get_checked() if record else []
    total_items = sum(len(category['items']) for category in categories.values())
    item_labels = {item['key']: item['label'] for category in CHECKLIST_ITEMS.values() for item in category['items']}
    history = []
    for rec in HealthChecklist.query.filter_by(child_id=child.id).order_by(HealthChecklist.date.desc()).all():
        checked = rec.get_checked()
        history.append({'id': rec.id, 'date': rec.date, 'date_str': rec.date.strftime('%B %d, %Y'), 'day_str': rec.date.strftime('%A'), 'checked': checked, 'labels': [item_labels.get(key, key) for key in checked], 'count': len(checked), 'total': total_items, 'pct': round(len(checked) / total_items * 100) if total_items else 0, 'notes': rec.notes or '', 'is_today': rec.date == today})
    return render_template('symptoms/health_checklist.html', active_child=child, all_children=current_user.children, categories=categories, checked_today=checked_today, notes_today=record.notes if record else '', today=today, total_items=total_items, checked_count=len(checked_today), sleep_guide=SLEEP_GUIDE.get(child.age_bracket, ''), history=history, page_title='Dietary & Health Checklist')
