import json
from datetime import date, datetime, timedelta

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session
from flask_login import login_required, current_user

from app import db
from models import FeverReading, HealthChecklist, RespiratoryEpisode, DiarrheaEpisode

symptoms_bp = Blueprint('symptoms', __name__)

FEVER_DISCLAIMER = (
    "IMPORTANT DISCLAIMER: This Fever Tracker provides general temperature monitoring "
    "guidance only. It is NOT a substitute for professional medical advice, diagnosis, "
    "or treatment. Contact your child's pediatrician for medical advice. In an emergency, "
    "call emergency services (911 / 112) or go to the nearest emergency room immediately."
)
GUIDANCE_ATTRIBUTION = (
    "Placeholder attribution pending review by a pediatric clinician: NHS Healthier Together "
    "symptom guidance (fever, cough/cold, and diarrhoea/vomiting); last reviewed: pending."
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


def _respiratory_guidance(episode):
    if episode.difficulty_breathing:
        return {'severity': 'emergency', 'title': 'Emergency breathing warning', 'message': 'Difficulty breathing needs immediate medical assessment. Do not wait for symptoms to improve.', 'actions': ['Call emergency services (911 / 112)', 'Go to the nearest Emergency Room', 'Keep your child upright and supervised', 'Seek immediate help for blue lips, pauses in breathing, or unusual unresponsiveness']}
    if episode.wheezing or episode.severity == 'severe' or episode.duration_days >= 7:
        return {'severity': 'high', 'title': 'High priority cough/cold symptoms', 'message': 'Wheezing, severe symptoms, or symptoms lasting 7 days or more need prompt medical advice.', 'actions': ['Contact your pediatrician or clinic today', 'Offer fluids and keep your child comfortable', 'Monitor breathing and record worsening symptoms', 'Seek emergency care if breathing becomes difficult']}
    if episode.fever_present or episode.severity == 'moderate' or episode.duration_days >= 3:
        return {'severity': 'monitor', 'title': 'Monitor cough/cold symptoms', 'message': 'Continue close monitoring and contact a clinician if symptoms worsen, fever persists, or your child is not drinking normally.', 'actions': ['Offer fluids and rest', 'Recheck temperature if your child feels hot', 'Avoid smoke and other irritants', 'Seek urgent help if wheezing or breathing difficulty develops']}
    return {'severity': 'general', 'title': 'General cough/cold care', 'message': 'Mild, short-lived symptoms without breathing concerns can usually be monitored at home.', 'actions': ['Offer fluids and rest', 'Use age-appropriate comfort measures', 'Contact a clinician if symptoms worsen or last longer than expected']}


def _diarrhea_guidance(episode):
    if episode.blood_present or episode.dehydration_signs == 'severe':
        return {'severity': 'emergency', 'title': 'Emergency diarrhea warning', 'message': 'Blood in stool or severe dehydration signs need immediate medical assessment.', 'actions': ['Call emergency services (911 / 112) or go to the nearest Emergency Room', 'Do not wait for the diarrhea to stop', 'Offer oral rehydration solution if your child is alert and able to drink', 'Seek immediate help for unusual sleepiness, inability to drink, or very little urine']}
    if episode.dehydration_signs == 'moderate' or episode.episodes_per_day >= 6 or episode.duration_days >= 3:
        return {'severity': 'high', 'title': 'High priority diarrhea symptoms', 'message': 'Frequent diarrhea, dehydration signs, or symptoms lasting 3 days or more need prompt medical advice.', 'actions': ['Contact your pediatrician or clinic today', 'Give frequent small sips of oral rehydration solution', 'Track wet diapers or urination and stool frequency', 'Seek emergency care if blood or severe dehydration develops']}
    if episode.dehydration_signs == 'mild' or episode.episodes_per_day >= 3 or episode.duration_days >= 2:
        return {'severity': 'monitor', 'title': 'Monitor diarrhea symptoms', 'message': 'Continue hydration monitoring and contact a clinician if symptoms increase, persist, or your child drinks or urinates less.', 'actions': ['Offer frequent fluids or oral rehydration solution', 'Continue age-appropriate feeding', 'Track stool frequency and urination', 'Seek urgent help for worsening dehydration']}
    return {'severity': 'general', 'title': 'General diarrhea care', 'message': 'A short episode without blood or dehydration signs can be monitored while maintaining fluids.', 'actions': ['Offer frequent fluids', 'Continue normal feeding as tolerated', 'Watch for dehydration, blood, or increasing frequency']}


def _parse_recorded_at(form):
    value = form.get('recorded_at', '').strip()
    return datetime.fromisoformat(value) if value else datetime.utcnow()


@symptoms_bp.route('/fever-tracker', methods=['GET', 'POST'])
@login_required
def fever_tracker():
    child = _active_child()
    if not child:
        return redirect(url_for('children.create_child'))

    tab = request.args.get('tab', 'fever')
    if tab not in ('fever', 'cough', 'diarrhea'):
        tab = 'fever'

    if request.method == 'POST':
        form_type = request.form.get('_form_type', 'fever')

        if form_type == 'fever':
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
                return redirect(url_for('symptoms.fever_tracker', tab='fever'))
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
            return redirect(url_for('symptoms.fever_tracker', tab='fever'))

        elif form_type == 'cough':
            try:
                symptom_type = request.form['symptom_type']
                severity = request.form['severity']
                duration_days = int(request.form['duration_days'])
                if symptom_type not in ('cough', 'runny/stuffy nose', 'sore throat', 'other'):
                    raise ValueError
                if severity not in ('mild', 'moderate', 'severe') or duration_days < 1 or duration_days > 365:
                    raise ValueError
                recorded_at = _parse_recorded_at(request.form)
            except (KeyError, TypeError, ValueError):
                flash('Enter valid cough/cold details.', 'error')
                return redirect(url_for('symptoms.fever_tracker', tab='cough'))
            episode = RespiratoryEpisode(
                child_id=child.id, symptom_type=symptom_type, severity=severity,
                duration_days=duration_days, fever_present='fever_present' in request.form,
                wheezing='wheezing' in request.form,
                difficulty_breathing='difficulty_breathing' in request.form,
                recorded_at=recorded_at,
            )
            db.session.add(episode)
            db.session.commit()
            flash('Cough/cold episode saved.', 'success')
            return redirect(url_for('symptoms.fever_tracker', tab='cough'))

        elif form_type == 'diarrhea':
            try:
                episodes_per_day = int(request.form['episodes_per_day'])
                consistency = request.form['consistency']
                dehydration_signs = request.form['dehydration_signs']
                duration_days = int(request.form['duration_days'])
                if episodes_per_day < 1 or episodes_per_day > 100 or duration_days < 1 or duration_days > 365:
                    raise ValueError
                if consistency not in ('loose', 'watery') or dehydration_signs not in ('none', 'mild', 'moderate', 'severe'):
                    raise ValueError
                recorded_at = _parse_recorded_at(request.form)
            except (KeyError, TypeError, ValueError):
                flash('Enter valid diarrhea details.', 'error')
                return redirect(url_for('symptoms.fever_tracker', tab='diarrhea'))
            episode = DiarrheaEpisode(
                child_id=child.id, episodes_per_day=episodes_per_day,
                consistency=consistency, blood_present='blood_present' in request.form,
                dehydration_signs=dehydration_signs, duration_days=duration_days,
                recorded_at=recorded_at,
            )
            db.session.add(episode)
            db.session.commit()
            flash('Diarrhea episode saved.', 'success')
            return redirect(url_for('symptoms.fever_tracker', tab='diarrhea'))

    readings = FeverReading.query.filter_by(child_id=child.id).order_by(FeverReading.recorded_at.desc(), FeverReading.id.desc()).limit(30).all()
    resp_episodes = RespiratoryEpisode.query.filter_by(child_id=child.id).order_by(RespiratoryEpisode.recorded_at.desc(), RespiratoryEpisode.id.desc()).limit(30).all()
    diarr_episodes = DiarrheaEpisode.query.filter_by(child_id=child.id).order_by(DiarrheaEpisode.recorded_at.desc(), DiarrheaEpisode.id.desc()).limit(30).all()

    resp_guidance = _respiratory_guidance(resp_episodes[0]) if resp_episodes else {
        'severity': 'general', 'title': 'No cough/cold episodes yet',
        'message': 'Log an episode to receive monitoring guidance.', 'actions': []
    }
    diarr_guidance = _diarrhea_guidance(diarr_episodes[0]) if diarr_episodes else {
        'severity': 'general', 'title': 'No diarrhea episodes yet',
        'message': 'Log an episode to receive hydration and monitoring guidance.', 'actions': []
    }

    return render_template(
        'symptoms/fever_tracker.html',
        active_child=child,
        active_tab=tab,
        readings=readings,
        resp_episodes=resp_episodes,
        diarr_episodes=diarr_episodes,
        guidance=_reading_guidance(child, readings),
        resp_guidance=resp_guidance,
        diarr_guidance=diarr_guidance,
        disclaimer=FEVER_DISCLAIMER,
        guidance_source=GUIDANCE_ATTRIBUTION,
        page_title='Fever Tracker',
    )


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


@symptoms_bp.route('/cough-cold-tracker', methods=['GET', 'POST'])
@login_required
def cough_cold_tracker():
    # Merged into the Fever Tracker – redirect to the Cough & Colds tab.
    return redirect(url_for('symptoms.fever_tracker', tab='cough'))


@symptoms_bp.route('/diarrhea-tracker', methods=['GET', 'POST'])
@login_required
def diarrhea_tracker():
    # Merged into the Fever Tracker – redirect to the Diarrhea tab.
    return redirect(url_for('symptoms.fever_tracker', tab='diarrhea'))


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
