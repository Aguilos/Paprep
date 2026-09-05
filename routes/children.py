from datetime import date
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, session, jsonify)
from flask_login import login_required, current_user
from app import db
from models import ChildProfile

children_bp = Blueprint('children', __name__, url_prefix='/children')

SPECIAL_NEEDS_TYPES = [
    'Autism Spectrum Disorder (ASD)',
    'Down Syndrome',
    'Attention Deficit Hyperactivity Disorder (ADHD)',
    'Cerebral Palsy',
    'Developmental Delay',
    'Speech and Language Delay',
    'Sensory Processing Disorder',
    'Hearing Impairment',
    'Visual Impairment',
    'Other',
]

PROFILE_COLORS = [
    '#4E97D9', '#5CAD5C', '#FF8C42', '#9B59B6',
    '#E74C3C', '#1ABC9C', '#F39C12', '#3498DB',
]


@children_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_child():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        dob_str = request.form.get('date_of_birth', '')
        gender = request.form.get('gender', '').strip()
        child_type = request.form.get('child_type', 'normal')
        sn_type = request.form.get('special_needs_type', '').strip()
        sn_notes = request.form.get('special_needs_notes', '').strip()
        profile_color = request.form.get('profile_color', '#4E97D9')

        errors = []
        if not name:
            errors.append('Child\'s name is required.')
        if not dob_str:
            errors.append('Date of birth is required.')

        dob = None
        if dob_str:
            try:
                dob = date.fromisoformat(dob_str)
                if dob > date.today():
                    errors.append('Date of birth cannot be in the future.')
                age_months = (
                    (date.today().year - dob.year) * 12
                    + (date.today().month - dob.month)
                )
                if age_months > 72:
                    errors.append('PaPrep supports children aged 0–5 years (up to 60 months).')
            except ValueError:
                errors.append('Invalid date format.')

        if child_type not in ('normal', 'special_needs'):
            child_type = 'normal'

        if child_type == 'special_needs' and not sn_type:
            errors.append('Please specify the type of special need.')

        if profile_color not in PROFILE_COLORS:
            profile_color = '#4E97D9'

        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template('dashboard/create_child.html',
                                   special_needs_types=SPECIAL_NEEDS_TYPES,
                                   profile_colors=PROFILE_COLORS,
                                   form_data=request.form)

        child = ChildProfile(
            user_id=current_user.id,
            name=name,
            date_of_birth=dob,
            gender=gender,
            child_type=child_type,
            special_needs_type=sn_type if child_type == 'special_needs' else None,
            special_needs_notes=sn_notes if child_type == 'special_needs' else None,
            profile_color=profile_color,
        )
        db.session.add(child)
        db.session.commit()

        session['active_child_id'] = child.id

        if child_type == 'special_needs':
            flash(
                f'{name}\'s profile has been created! We\'ve enabled the Special Needs Support module for you.',
                'success'
            )
        else:
            flash(f'{name}\'s profile has been created! Welcome to PaPrep!', 'success')

        return redirect(url_for('main.dashboard'))

    return render_template('dashboard/create_child.html',
                           special_needs_types=SPECIAL_NEEDS_TYPES,
                           profile_colors=PROFILE_COLORS,
                           form_data={})


@children_bp.route('/<int:child_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_child(child_id):
    child = ChildProfile.query.filter_by(
        id=child_id, user_id=current_user.id
    ).first_or_404()

    if request.method == 'POST':
        child.name = request.form.get('name', child.name).strip()
        dob_str = request.form.get('date_of_birth', '')
        child.gender = request.form.get('gender', child.gender)
        child.child_type = request.form.get('child_type', child.child_type)
        child.special_needs_type = request.form.get('special_needs_type', '')
        child.special_needs_notes = request.form.get('special_needs_notes', '')
        profile_color = request.form.get('profile_color', child.profile_color)
        if profile_color in PROFILE_COLORS:
            child.profile_color = profile_color

        if dob_str:
            try:
                child.date_of_birth = date.fromisoformat(dob_str)
            except ValueError:
                flash('Invalid date format.', 'error')
                return redirect(url_for('children.edit_child', child_id=child_id))

        db.session.commit()
        flash(f'{child.name}\'s profile has been updated.', 'success')
        return redirect(url_for('main.dashboard'))

    return render_template('dashboard/create_child.html',
                           child=child,
                           special_needs_types=SPECIAL_NEEDS_TYPES,
                           profile_colors=PROFILE_COLORS,
                           form_data={},
                           editing=True)


# API: set active child
@children_bp.route('/api/set-active', methods=['POST'])
@login_required
def set_active_child():
    data = request.get_json(silent=True) or {}
    child_id = data.get('child_id')
    child = ChildProfile.query.filter_by(
        id=child_id, user_id=current_user.id
    ).first()
    if not child:
        return jsonify({'error': 'Child not found'}), 404
    session['active_child_id'] = child.id
    return jsonify({'success': True, 'child_id': child.id})
