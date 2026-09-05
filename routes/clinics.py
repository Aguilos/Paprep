import json
from flask import Blueprint, render_template, abort, redirect, url_for, flash
from flask_login import login_required, current_user
from models import Clinic, ClinicSchedule, ClinicAnnouncement, LearningModule, ClinicRegistration
from utils import today_pht
from app import db

clinics_bp = Blueprint('clinics', __name__, url_prefix='/clinics')


@clinics_bp.route('/')
@login_required
def clinic_locator():
    clinics = Clinic.query.filter(Clinic.clinic_account_id.isnot(None)).all()
    clinics_json = json.dumps([c.to_dict() for c in clinics])
    return render_template('clinics/clinics.html',
                           clinics=clinics,
                           clinics_json=clinics_json,
                           page_title='Find a Clinic')


@clinics_bp.route('/<int:clinic_id>')
@login_required
def clinic_detail(clinic_id):
    clinic = Clinic.query.get_or_404(clinic_id)
    schedules = ClinicSchedule.query.filter_by(clinic_id=clinic_id).all()
    today = today_pht()
    active_announcements = [
        a for a in clinic.announcements
        if a.is_active and (a.expires_at is None or a.expires_at >= today)
    ]
    # Fetch learning modules published by this clinic (only if registered)
    clinic_modules = []
    is_registered = False
    
    if clinic.clinic_account_id:
        clinic_modules = LearningModule.query.filter_by(
            clinic_account_id=clinic.clinic_account_id
        ).order_by(LearningModule.sort_order, LearningModule.id).all()
        
        # Check if the current user has registered with this clinic
        is_registered = ClinicRegistration.query.filter_by(
            clinic_id=clinic.id, user_id=current_user.id
        ).first() is not None

    return render_template('clinics/clinic_detail.html',
                           clinic=clinic,
                           schedules=schedules,
                           today=today,
                           announcements=active_announcements,
                           clinic_modules=clinic_modules,
                           is_registered=is_registered,
                           page_title=clinic.name)


@clinics_bp.route('/<int:clinic_id>/register', methods=['POST'])
@login_required
def register(clinic_id):
    clinic = Clinic.query.get_or_404(clinic_id)
    if not clinic.clinic_account_id:
        flash('This clinic is not fully registered on PaPrep yet.', 'error')
        return redirect(url_for('clinics.clinic_detail', clinic_id=clinic.id))
        
    existing = ClinicRegistration.query.filter_by(
        clinic_id=clinic.id, user_id=current_user.id
    ).first()
    
    if not existing:
        reg = ClinicRegistration(clinic_id=clinic.id, user_id=current_user.id)
        db.session.add(reg)
        db.session.commit()
        flash(f'You have successfully registered with {clinic.name}. You can now message them.', 'success')
        
    return redirect(url_for('clinics.clinic_detail', clinic_id=clinic.id))
