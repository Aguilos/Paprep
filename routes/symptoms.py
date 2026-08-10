import json
from datetime import date

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session
from flask_login import login_required, current_user

from app import db
from models import Symptom, HealthChecklist, ChildProfile

symptoms_bp = Blueprint('symptoms', __name__)

EMERGENCY_NAMES = {'Seizure / Convulsion', 'Difficulty Breathing'}
HIGH_PRIORITY_NAMES = {
    'High Fever (above 38.5°C)',
    'Jaundice (Yellow Skin/Eyes)',
    'Hives / Allergic Skin Reaction',
    'Pale Skin',
    'Lethargy / Weakness',
}

DISCLAIMER = (
    "⚠️ IMPORTANT DISCLAIMER: This Symptom Checker is intended for general "
    "informational and monitoring guidance only. It is NOT a substitute for "
    "professional medical advice, diagnosis, or treatment. Always seek the advice "
    "of your child's pediatrician or a qualified healthcare professional regarding "
    "any medical condition. In case of emergency, call emergency services (911 / 112) "
    "or go to the nearest emergency room immediately."
)


@symptoms_bp.route('/symptoms')
@login_required
def symptom_checker():
    symptoms = Symptom.query.order_by(Symptom.sort_order, Symptom.id).all()

    # Group by category
    grouped = {}
    category_labels = {
        'fever': 'Fever',
        'respiratory': 'Respiratory',
        'digestive': 'Digestive / Stomach',
        'skin': 'Skin',
        'eyes_ears': 'Eyes & Ears',
        'behavioral': 'Behavioral / Neurological',
        'general': 'General',
    }
    for s in symptoms:
        grouped.setdefault(s.category, []).append(s)

    return render_template('symptoms/symptom_checker.html',
                           grouped=grouped,
                           category_labels=category_labels,
                           disclaimer=DISCLAIMER,
                           page_title='Symptom Checker')


@symptoms_bp.route('/api/symptoms/check', methods=['POST'])
@login_required
def check_symptoms():
    data = request.get_json(silent=True) or {}
    selected_ids = data.get('symptom_ids', [])

    if not selected_ids:
        return jsonify({'error': 'No symptoms selected.'}), 400

    symptoms = Symptom.query.filter(Symptom.id.in_(selected_ids)).all()
    names = {s.name for s in symptoms}
    categories = {s.category for s in symptoms}

    recommendations = []
    severity = 'low'

    # ── Emergency ──────────────────────────────────────────────────────────
    if names & EMERGENCY_NAMES:
        severity = 'emergency'
        matched = names & EMERGENCY_NAMES
        recommendations.append({
            'type': 'emergency',
            'title': '🚨 EMERGENCY — Go to the ER Immediately',
            'content': (
                f'Your child is showing sign(s) of a medical emergency '
                f'({", ".join(matched)}). Do NOT wait. Proceed to the nearest '
                'Emergency Room or call emergency services (911 / 112) now.'
            ),
            'actions': [
                'Call 911 or 112 immediately',
                'Go to the nearest Emergency Room',
                'Keep the child calm and do not leave unattended',
                'Note the time the symptoms started',
            ],
        })
        return jsonify({
            'severity': severity,
            'recommendations': recommendations,
            'disclaimer': DISCLAIMER,
        })

    # ── High priority ───────────────────────────────────────────────────────
    matched_high = names & HIGH_PRIORITY_NAMES
    if matched_high:
        severity = 'high'

    # High fever rule
    if 'High Fever (above 38.5°C)' in names:
        if 'Skin Rash' in names:
            recommendations.append({
                'type': 'danger',
                'title': 'High Fever with Rash — See a Doctor Promptly',
                'content': (
                    'The combination of high fever and a skin rash can indicate '
                    'several conditions including roseola, measles, or scarlet fever. '
                    'Medical evaluation is needed soon.'
                ),
                'actions': [
                    'Visit a pediatrician or clinic within the day',
                    'Note the appearance and spread of the rash',
                    'Keep child hydrated with fluids',
                    'Avoid giving aspirin to children',
                ],
            })
        else:
            recommendations.append({
                'type': 'danger',
                'title': 'High Fever — Medical Consultation Needed',
                'content': (
                    'A fever above 38.5 °C in young children requires medical evaluation. '
                    'For infants under 3 months, any fever is an emergency. '
                    'For older children, consult a doctor within 24 hours if the fever persists.'
                ),
                'actions': [
                    'Give age-appropriate fever reducer as directed by your pediatrician',
                    'Keep child well-hydrated (water, breast milk, or ORS)',
                    'Dress child lightly — avoid over-bundling',
                    'See a doctor if fever persists more than 24 hours or exceeds 40°C',
                ],
            })

    elif 'Mild Fever (37.5°C - 38.5°C)' in names:
        recommendations.append({
            'type': 'warning',
            'title': 'Mild Fever — Monitor at Home',
            'content': (
                'A mild fever is often the body\'s response to an infection. '
                'Home monitoring is usually appropriate for mild fevers in children over 3 months.'
            ),
            'actions': [
                'Check temperature every 4 hours',
                'Ensure adequate fluid intake',
                'Keep child rested and comfortable',
                'Contact a doctor if fever rises above 38.5°C, lasts more than 2 days, '
                'or if the child appears very unwell',
            ],
        })

    # Wheezing
    if 'Wheezing' in names:
        if severity not in ('emergency', 'high'):
            severity = 'high'
        recommendations.append({
            'type': 'danger',
            'title': 'Wheezing — Consult a Doctor',
            'content': (
                'Wheezing in young children can indicate asthma, bronchiolitis, or other '
                'respiratory conditions. A doctor should evaluate this, especially if '
                'recurrent or accompanied by fever.'
            ),
            'actions': [
                'Keep the child upright to ease breathing',
                'Avoid smoke and allergens',
                'Visit a doctor or clinic today',
                'If breathing worsens or child turns bluish — go to ER immediately',
            ],
        })

    # Respiratory
    if {'Cough', 'Runny Nose', 'Nasal Congestion'} & names and severity == 'low':
        severity = 'medium' if len(names) > 1 else 'low'
        recommendations.append({
            'type': 'info',
            'title': 'Cold / Upper Respiratory Symptoms — Home Care',
            'content': (
                'Common cold symptoms are very frequent in young children and usually '
                'resolve within 7–10 days. Focus on comfort care and monitoring.'
            ),
            'actions': [
                'Use a saline nasal spray or bulb syringe to clear congestion',
                'Offer plenty of clear fluids',
                'Use a cool-mist humidifier in the room',
                'Elevate the head slightly during sleep',
                'See a doctor if symptoms persist beyond 10 days or worsen significantly',
            ],
        })

    # Digestive
    has_vomiting = 'Vomiting' in names
    has_diarrhea = 'Diarrhea' in names
    if has_vomiting or has_diarrhea:
        if severity not in ('emergency', 'high'):
            severity = 'medium'
        recommendations.append({
            'type': 'warning',
            'title': 'Dehydration Risk — Fluid Management Critical',
            'content': (
                f'{"Vomiting and/or diarrhea" if (has_vomiting and has_diarrhea) else ("Vomiting" if has_vomiting else "Diarrhea")} '
                'can quickly lead to dehydration in young children. '
                'Monitor for signs of dehydration: dry mouth, sunken eyes, no tears, dark urine, or lethargy.'
            ),
            'actions': [
                'Offer Oral Rehydration Solution (ORS) in small, frequent sips',
                'Do NOT give plain water as the sole fluid (it lacks electrolytes)',
                'Continue breastfeeding if applicable',
                'Avoid high-sugar juices or carbonated drinks',
                'See a doctor if vomiting/diarrhea persists beyond 24 hours, '
                'or if you notice signs of dehydration',
            ],
        })

    # Jaundice
    if 'Jaundice (Yellow Skin/Eyes)' in names:
        severity = 'high'
        recommendations.append({
            'type': 'danger',
            'title': 'Jaundice (Yellow Skin/Eyes) — See a Doctor Today',
            'content': (
                'Jaundice — yellowing of the skin or whites of the eyes — requires '
                'prompt medical evaluation to determine the cause, especially in infants.'
            ),
            'actions': [
                'Visit a doctor or clinic today — do not wait',
                'For newborns (< 2 weeks): jaundice is an urgent concern',
                'Keep child well-fed and hydrated',
                'Note when the yellowing started and its extent',
            ],
        })

    # Hives / Allergic reaction
    if 'Hives / Allergic Skin Reaction' in names:
        recommendations.append({
            'type': 'warning',
            'title': 'Possible Allergic Reaction — Monitor Closely',
            'content': (
                'Hives may indicate an allergic reaction. While often mild, '
                'watch closely for signs of a severe reaction (anaphylaxis): '
                'difficulty breathing, swelling of lips/tongue/throat, or sudden weakness.'
            ),
            'actions': [
                'Check for difficulty breathing or swelling — if present, go to ER immediately',
                'Try to identify and remove the trigger (food, insect sting, medication)',
                'Apply cool compress to itchy areas',
                'Consult a doctor if hives spread, worsen, or do not resolve within 24 hours',
            ],
        })

    # Eye symptoms
    if 'Eye Discharge / Pink Eye' in names:
        recommendations.append({
            'type': 'info',
            'title': 'Eye Discharge — Keep Clean, Consult if Needed',
            'content': (
                'Eye discharge can result from conjunctivitis (pink eye) or a blocked tear duct. '
                'It can be contagious if bacterial or viral.'
            ),
            'actions': [
                'Clean the eye gently from inner to outer corner with a clean, damp cloth',
                'Avoid touching/rubbing the eyes',
                'Wash hands frequently',
                'See a doctor if discharge is thick/green, eye is very red, or child has discomfort',
            ],
        })

    # Ear pain
    if 'Ear Pain' in names:
        if severity not in ('emergency', 'high'):
            severity = 'medium'
        recommendations.append({
            'type': 'warning',
            'title': 'Ear Pain — Consult a Doctor',
            'content': (
                'Ear pain in young children is often due to an ear infection (otitis media). '
                'This may need antibiotic treatment.'
            ),
            'actions': [
                'Keep child upright when possible — lying flat increases ear pain',
                'Apply a warm compress to the ear for comfort',
                'Visit a doctor within 24 hours for evaluation',
                'Do NOT insert any objects into the ear',
            ],
        })

    # Behavioral
    if 'Lethargy / Weakness' in names:
        severity = 'high'
        recommendations.append({
            'type': 'danger',
            'title': 'Lethargy / Unusual Weakness — Seek Medical Care',
            'content': (
                'Unusual tiredness or difficulty waking in a child can indicate a '
                'more serious underlying condition and warrants prompt medical evaluation.'
            ),
            'actions': [
                'Do not delay — consult a doctor today',
                'Keep child comfortable and hydrated if responsive',
                'Monitor breathing, colour, and responsiveness',
                'If unresponsive or breathing abnormally — call emergency services',
            ],
        })

    if 'Excessive / Inconsolable Crying' in names and severity == 'low':
        recommendations.append({
            'type': 'info',
            'title': 'Excessive Crying — Check for Underlying Cause',
            'content': (
                'Inconsolable crying in infants and toddlers may indicate pain, hunger, '
                'colic, ear infection, or other discomfort. Try to identify the cause.'
            ),
            'actions': [
                'Check for obvious causes: hunger, wet diaper, temperature discomfort',
                'Gently check for signs of pain (ear pulling, leg drawing to abdomen)',
                'Try soothing techniques: gentle rocking, skin-to-skin contact',
                'If crying is accompanied by fever, rash, or other symptoms — see a doctor',
                'See a doctor if crying is persistent and inconsolable for more than 3 hours',
            ],
        })

    # Swollen nodes
    if 'Swollen Lymph Nodes' in names and severity == 'low':
        recommendations.append({
            'type': 'info',
            'title': 'Swollen Lymph Nodes — Monitor and Consult',
            'content': (
                'Swollen lymph nodes are commonly a sign of infection (cold, ear infection, etc.) '
                'and usually resolve on their own. Persistent swelling warrants medical review.'
            ),
            'actions': [
                'Monitor for changes in size or tenderness',
                'See a doctor if swelling lasts more than 2 weeks or is rapidly growing',
                'Note any accompanying fever, weight loss, or fatigue',
            ],
        })

    # Default advice if nothing specific was triggered
    if not recommendations:
        recommendations.append({
            'type': 'info',
            'title': 'General Comfort Care',
            'content': (
                'Based on the symptoms selected, general supportive care is recommended. '
                'Ensure your child is comfortable, rested, and well-hydrated.'
            ),
            'actions': [
                'Ensure adequate rest and comfortable environment',
                'Maintain good hydration (fluids appropriate for age)',
                'Monitor symptoms and note any changes',
                'Contact your pediatrician if symptoms persist or worsen',
            ],
        })

    return jsonify({
        'severity': severity,
        'symptom_count': len(symptoms),
        'recommendations': recommendations,
        'disclaimer': DISCLAIMER,
    })


# ---------------------------------------------------------------------------
# Dietary & Health Monitoring Checklist
# ---------------------------------------------------------------------------

# Items keyed by category.  'ages' lists every bracket that should see the item.
_ALL_BRACKETS = ['0–12 months', '1–2 years', '2–3 years', '3–4 years', '4–5 years']

CHECKLIST_ITEMS = {
    'dietary': {
        'title': 'Dietary Monitoring',
        'icon': 'bi-egg-fried',
        'color': '#f97316',
        'items': [
            {'key': 'breast_formula', 'label': 'Fed breast milk or formula regularly today', 'ages': ['0–12 months']},
            {'key': 'solids_intro',   'label': 'Soft solids / purees introduced (6+ months)', 'ages': ['0–12 months']},
            {'key': 'breakfast',      'label': 'Had a proper breakfast', 'ages': ['1–2 years', '2–3 years', '3–4 years', '4–5 years']},
            {'key': 'lunch',          'label': 'Had a proper lunch', 'ages': _ALL_BRACKETS},
            {'key': 'dinner',         'label': 'Had a proper dinner', 'ages': _ALL_BRACKETS},
            {'key': 'healthy_snack',  'label': 'Had a healthy snack (fruit / veg / nut butter)', 'ages': ['1–2 years', '2–3 years', '3–4 years', '4–5 years']},
            {'key': 'fruit_veg',      'label': 'Ate at least one fruit or vegetable', 'ages': _ALL_BRACKETS},
            {'key': 'protein',        'label': 'Had protein (meat / fish / eggs / beans)', 'ages': _ALL_BRACKETS},
            {'key': 'dairy',          'label': 'Had dairy (milk / yogurt / cheese)', 'ages': ['1–2 years', '2–3 years', '3–4 years', '4–5 years']},
            {'key': 'grains',         'label': 'Had grains (rice / bread / oats)', 'ages': _ALL_BRACKETS},
            {'key': 'water',          'label': 'Drank enough water / fluids today', 'ages': _ALL_BRACKETS},
            {'key': 'no_sugary',      'label': 'Avoided sugary drinks and junk food', 'ages': ['1–2 years', '2–3 years', '3–4 years', '4–5 years']},
        ],
    },
    'health': {
        'title': 'Health Monitoring',
        'icon': 'bi-heart-pulse-fill',
        'color': '#ef4444',
        'items': [
            {'key': 'sleep_ok',     'label': 'Got adequate sleep last night', 'ages': _ALL_BRACKETS},
            {'key': 'tummy_time',   'label': 'Had supervised tummy time (≥ 3 min)', 'ages': ['0–12 months']},
            {'key': 'active_play',  'label': 'Had active play / physical activity today', 'ages': ['1–2 years', '2–3 years', '3–4 years', '4–5 years']},
            {'key': 'bath',         'label': 'Bathed and cleaned properly', 'ages': _ALL_BRACKETS},
            {'key': 'teeth',        'label': 'Brushed teeth (morning & night)', 'ages': ['1–2 years', '2–3 years', '3–4 years', '4–5 years']},
            {'key': 'vitamins',     'label': 'Took vitamins / supplements (if prescribed)', 'ages': _ALL_BRACKETS},
            {'key': 'no_fever',     'label': 'No fever or signs of illness observed', 'ages': _ALL_BRACKETS},
            {'key': 'mood_ok',      'label': 'Good mood / normal behavior today', 'ages': _ALL_BRACKETS},
            {'key': 'bowel_ok',     'label': 'Normal bowel movement / urination', 'ages': _ALL_BRACKETS},
            {'key': 'weight_check', 'label': 'Weight / growth checked this week', 'ages': _ALL_BRACKETS},
        ],
    },
}

SLEEP_GUIDE = {
    '0–12 months': '14–17 hours (newborns) / 12–16 hours (6–12 months)',
    '1–2 years': '11–14 hours (including naps)',
    '2–3 years': '11–14 hours (including naps)',
    '3–4 years': '10–13 hours',
    '4–5 years': '10–13 hours',
}


def _filter_items_for_age(bracket):
    """Return checklist categories with items filtered to the given age bracket."""
    result = {}
    for cat_key, cat in CHECKLIST_ITEMS.items():
        filtered = [i for i in cat['items'] if bracket in i['ages']]
        if filtered:
            result[cat_key] = {**cat, 'items': filtered}
    return result


@symptoms_bp.route('/health-checklist', methods=['GET', 'POST'])
@login_required
def health_checklist():
    if not current_user.children:
        return redirect(url_for('children.create_child'))

    active_child_id = session.get('active_child_id')
    active_child = next(
        (c for c in current_user.children if c.id == active_child_id),
        current_user.children[0],
    )

    today = date.today()
    categories = _filter_items_for_age(active_child.age_bracket)

    # Fetch or create today's record
    record = HealthChecklist.query.filter_by(
        child_id=active_child.id, date=today
    ).first()

    if request.method == 'POST':
        checked = request.form.getlist('items')
        notes_text = request.form.get('notes', '').strip()
        if record is None:
            record = HealthChecklist(child_id=active_child.id, date=today)
            db.session.add(record)
        record.checked_items = json.dumps(checked)
        record.notes = notes_text or None
        db.session.commit()
        flash('Checklist saved successfully!', 'success')
        return redirect(url_for('symptoms.health_checklist'))

    checked_today = record.get_checked() if record else []
    notes_today = record.notes if record else ''

    # Count total items for progress
    total_items = sum(len(c['items']) for c in categories.values())
    checked_count = sum(1 for k in checked_today if any(
        k in [i['key'] for i in c['items']] for c in categories.values()
    ))

    # Label lookup  (key → human label) for history display
    item_labels = {
        item['key']: item['label']
        for cat in CHECKLIST_ITEMS.values()
        for item in cat['items']
    }

    # Full history — all records for this child, newest first
    all_records = HealthChecklist.query.filter_by(
        child_id=active_child.id
    ).order_by(HealthChecklist.date.desc()).all()

    history = []
    for rec in all_records:
        checked_keys = rec.get_checked()
        cnt  = len(checked_keys)
        pct  = round(cnt / total_items * 100) if total_items else 0
        history.append({
            'id':       rec.id,
            'date':     rec.date,
            'date_str': rec.date.strftime('%B %d, %Y'),
            'day_str':  rec.date.strftime('%A'),
            'checked':  checked_keys,
            'labels':   [item_labels.get(k, k) for k in checked_keys],
            'count':    cnt,
            'total':    total_items,
            'pct':      pct,
            'notes':    rec.notes or '',
            'is_today': rec.date == today,
        })

    return render_template(
        'symptoms/health_checklist.html',
        active_child=active_child,
        all_children=current_user.children,
        categories=categories,
        checked_today=checked_today,
        notes_today=notes_today,
        today=today,
        total_items=total_items,
        checked_count=checked_count,
        sleep_guide=SLEEP_GUIDE.get(active_child.age_bracket, ''),
        history=history,
        page_title='Dietary & Health Checklist',
    )

