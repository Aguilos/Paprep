import json
from flask import Blueprint, render_template, abort
from flask_login import login_required
from models import Clinic, ClinicSchedule, ClinicAnnouncement
from utils import today_pht

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
    return render_template('clinics/clinic_detail.html',
                           clinic=clinic,
                           schedules=schedules,
                           today=today,
                           announcements=active_announcements,
                           page_title=clinic.name)
