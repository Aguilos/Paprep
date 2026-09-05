"""
Clinic Portal — separate auth + dashboard for clinic accounts.
Uses a session key 'clinic_id' instead of flask-login to keep it
completely separate from the parent-user login.
"""
import os
import base64
import functools
from datetime import date
from io import BytesIO
import pyotp
import qrcode

from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, session, abort, send_file, Response)
from werkzeug.utils import secure_filename
from app import db
from models import ClinicAccount, Clinic, ClinicSchedule, LearningModule, ClinicAnnouncement

clinic_portal_bp = Blueprint('clinic_portal', __name__, url_prefix='/clinic')

DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
CATEGORY_META = {
    'parenting':     {'label': 'Parenting',    'icon': 'bi-people-fill',      'color': '#4E97D9'},
    'nutrition':     {'label': 'Nutrition',    'icon': 'bi-apple',            'color': '#5CAD5C'},
    'safety':        {'label': 'Safety',       'icon': 'bi-shield-check',     'color': '#FF8C42'},
    'health':        {'label': 'Child Health', 'icon': 'bi-heart-pulse-fill', 'color': '#E74C3C'},
    'special_needs': {'label': 'Special Needs','icon': 'bi-person-heart',     'color': '#9B59B6'},
}
MIN_PASSWORD_LENGTH = 8


# ── Auth helpers ──────────────────────────────────────────────────────────────

def _current_clinic_account():
    cid = session.get('clinic_account_id')
    if not cid:
        return None
    return db.session.get(ClinicAccount, cid)


def clinic_login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        cid = session.get('clinic_account_id')
        if not cid:
            flash('Please log in to access your clinic portal.', 'warning')
            return redirect(url_for('clinic_portal.login'))
        # Guard against stale sessions pointing to a deleted account
        if not db.session.get(ClinicAccount, cid):
            session.pop('clinic_account_id', None)
            flash('Your session has expired. Please log in again.', 'warning')
            return redirect(url_for('clinic_portal.login'))
        return f(*args, **kwargs)
    return decorated


def _parse_float(val):
    try:
        return float(val) if val else None
    except (TypeError, ValueError):
        return None


def _ampm_to_24h(hour, minute, period):
    h = int(hour) if hour else 8
    m = minute if minute else '00'
    if period == 'AM':
        if h == 12:
            h = 0
    else:
        if h != 12:
            h += 12
    return f'{h:02d}:{m}'


def _save_schedules(clinic_id, form):
    for day in DAYS_OF_WEEK:
        sched = ClinicSchedule.query.filter_by(clinic_id=clinic_id, day_of_week=day).first()
        if not sched:
            sched = ClinicSchedule(clinic_id=clinic_id, day_of_week=day)
            db.session.add(sched)
        sched.is_closed = (f'closed_{day}' in form)
        sched.open_time = _ampm_to_24h(
            form.get(f'open_hour_{day}', '8'),
            form.get(f'open_min_{day}', '00'),
            form.get(f'open_period_{day}', 'AM')
        )
        sched.close_time = _ampm_to_24h(
            form.get(f'close_hour_{day}', '5'),
            form.get(f'close_min_{day}', '00'),
            form.get(f'close_period_{day}', 'PM')
        )


# ── Auth routes ───────────────────────────────────────────────────────────────

@clinic_portal_bp.route('/')
def index():
    if session.get('clinic_account_id'):
        return redirect(url_for('clinic_portal.dashboard'))
    return redirect(url_for('clinic_portal.login'))


@clinic_portal_bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('clinic_account_id'):
        return redirect(url_for('clinic_portal.dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        account = ClinicAccount.query.filter_by(email=email).first()
        if not account or not account.check_password(password):
            flash('Invalid email or password.', 'error')
            return render_template('clinic_portal/login.html', email=email)
        # If 2FA is enabled, hold in pending state until code verified
        if account.totp_enabled:
            session.permanent = True
            session['clinic_pending_2fa'] = account.id
            return redirect(url_for('clinic_portal.verify_2fa'))
        session.permanent = True
        session['clinic_account_id'] = account.id
        flash(f'Welcome back, {account.contact_name}!', 'success')
        return redirect(url_for('clinic_portal.dashboard'))
    return render_template('clinic_portal/login.html')


@clinic_portal_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if session.get('clinic_account_id'):
        return redirect(url_for('clinic_portal.dashboard'))
    if request.method == 'POST':
        contact_name = request.form.get('contact_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        errors = []
        if not contact_name:
            errors.append('Contact name is required.')
        if not email or '@' not in email:
            errors.append('A valid email address is required.')
        if len(password) < MIN_PASSWORD_LENGTH:
            errors.append(f'Password must be at least {MIN_PASSWORD_LENGTH} characters.')
        if password != confirm:
            errors.append('Passwords do not match.')
        if ClinicAccount.query.filter_by(email=email).first():
            errors.append('An account with that email already exists.')

        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template('clinic_portal/signup.html',
                                   contact_name=contact_name, email=email)

        account = ClinicAccount(contact_name=contact_name, email=email)
        account.set_password(password)
        account.totp_secret = pyotp.random_base32()   # pre-generate secret for QR
        db.session.add(account)
        db.session.commit()
        session.permanent = True
        session['clinic_setup_2fa'] = account.id      # pending 2FA setup
        return redirect(url_for('clinic_portal.signup_2fa'))
    return render_template('clinic_portal/signup.html')


@clinic_portal_bp.route('/logout')
def logout():
    session.pop('clinic_account_id', None)
    flash('You have been signed out of the clinic portal.', 'info')
    return redirect(url_for('clinic_portal.login'))


@clinic_portal_bp.route('/signup/2fa', methods=['GET', 'POST'])
def signup_2fa():
    """2FA setup step embedded in the signup flow."""
    pending_id = session.get('clinic_setup_2fa')
    if not pending_id:
        return redirect(url_for('clinic_portal.signup'))
    account = db.session.get(ClinicAccount, pending_id)
    if not account:
        session.pop('clinic_setup_2fa', None)
        return redirect(url_for('clinic_portal.signup'))

    if request.method == 'POST':
        code = request.form.get('code', '').strip().replace(' ', '')
        totp = pyotp.TOTP(account.totp_secret)
        if totp.verify(code, valid_window=1):
            account.totp_enabled = True
            db.session.commit()
            session.pop('clinic_setup_2fa', None)
            session['clinic_account_id'] = account.id
            flash(f'Welcome to PaPrep, {account.contact_name}! Your account is secured with 2FA. Set up your clinic profile below.', 'success')
            return redirect(url_for('clinic_portal.setup_clinic'))
        flash('Invalid code — please try again with a fresh code from your app.', 'error')

    qr_b64 = _make_qr_b64(account)
    return render_template('clinic_portal/signup_2fa.html',
                           account=account,
                           qr_b64=qr_b64,
                           secret=account.totp_secret)


# ── First-time clinic setup ───────────────────────────────────────────────────

@clinic_portal_bp.route('/setup', methods=['GET', 'POST'])
@clinic_login_required
def setup_clinic():
    account = _current_clinic_account()
    if account.clinic:
        return redirect(url_for('clinic_portal.dashboard'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Clinic name is required.', 'error')
            return render_template('clinic_portal/setup_clinic.html', account=account, days=DAYS_OF_WEEK)
        clinic = Clinic(
            name=name,
            address=request.form.get('address', '').strip(),
            city=request.form.get('city', '').strip(),
            phone=request.form.get('phone', '').strip(),
            email=request.form.get('email', '').strip(),
            website=request.form.get('website', '').strip(),
            clinic_type=request.form.get('clinic_type', 'general'),
            accepts_special_needs='accepts_special_needs' in request.form,
            description=request.form.get('description', '').strip(),
            latitude=_parse_float(request.form.get('latitude')),
            longitude=_parse_float(request.form.get('longitude')),
            clinic_account_id=account.id,
        )
        db.session.add(clinic)
        db.session.flush()
        _save_schedules(clinic.id, request.form)
        db.session.commit()
        flash(f'Clinic "{clinic.name}" created successfully!', 'success')
        return redirect(url_for('clinic_portal.dashboard'))
    return render_template('clinic_portal/setup_clinic.html', account=account, days=DAYS_OF_WEEK)


# ── Dashboard ─────────────────────────────────────────────────────────────────

@clinic_portal_bp.route('/dashboard')
@clinic_login_required
def dashboard():
    account = _current_clinic_account()
    if not account.clinic:
        return redirect(url_for('clinic_portal.setup_clinic'))
    clinic = account.clinic
    modules = LearningModule.query.filter_by(clinic_account_id=account.id).order_by(LearningModule.id.desc()).all()
    schedules = ClinicSchedule.query.filter_by(clinic_id=clinic.id).all()
    return render_template('clinic_portal/dashboard.html',
                           account=account,
                           clinic=clinic,
                           modules=modules,
                           schedules=schedules,
                           category_meta=CATEGORY_META)


# ── Clinic profile / location ─────────────────────────────────────────────────

@clinic_portal_bp.route('/profile', methods=['GET', 'POST'])
@clinic_login_required
def clinic_profile():
    account = _current_clinic_account()
    if not account.clinic:
        return redirect(url_for('clinic_portal.setup_clinic'))
    clinic = account.clinic
    schedules = {s.day_of_week: s for s in clinic.schedules}
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if name:
            clinic.name = name
        clinic.address = request.form.get('address', '').strip()
        clinic.city = request.form.get('city', '').strip()
        clinic.phone = request.form.get('phone', '').strip()
        clinic.email = request.form.get('email', '').strip()
        clinic.website = request.form.get('website', '').strip()
        clinic.clinic_type = request.form.get('clinic_type', 'general')
        clinic.accepts_special_needs = 'accepts_special_needs' in request.form
        clinic.description = request.form.get('description', '').strip()
        lat = _parse_float(request.form.get('latitude'))
        lng = _parse_float(request.form.get('longitude'))
        if lat is not None:
            clinic.latitude = lat
        if lng is not None:
            clinic.longitude = lng
        _save_schedules(clinic.id, request.form)
        db.session.commit()
        flash('Clinic profile updated successfully.', 'success')
        return redirect(url_for('clinic_portal.clinic_profile'))
    clinic_json = clinic.to_dict()
    clinic_json['schedules'] = {day: s.to_dict() for day, s in schedules.items()}
    return render_template('clinic_portal/clinic_profile.html',
                           account=account,
                           clinic=clinic,
                           schedules=schedules,
                           clinic_json=clinic_json,
                           days=DAYS_OF_WEEK)


# ── Modules ───────────────────────────────────────────────────────────────────

@clinic_portal_bp.route('/modules')
@clinic_login_required
def manage_modules():
    account = _current_clinic_account()
    if not account.clinic:
        return redirect(url_for('clinic_portal.setup_clinic'))
    modules = LearningModule.query.filter_by(clinic_account_id=account.id)\
                                  .order_by(LearningModule.id.desc()).all()
    return render_template('clinic_portal/manage_modules.html',
                           account=account,
                           clinic=account.clinic,
                           modules=modules,
                           category_meta=CATEGORY_META)


@clinic_portal_bp.route('/modules/add', methods=['POST'])
@clinic_login_required
def add_module():
    account = _current_clinic_account()
    title = request.form.get('title', '').strip()
    category = request.form.get('category', 'parenting')
    if not title:
        flash('Module title is required.', 'error')
        return redirect(url_for('clinic_portal.manage_modules'))
    module = LearningModule(
        title=title,
        description=request.form.get('description', '').strip(),
        content=request.form.get('content', '').strip(),
        category=category if category in CATEGORY_META else 'parenting',
        age_group=request.form.get('age_group', '').strip(),
        is_special_needs=(category == 'special_needs'),
        clinic_account_id=account.id,
    )
    db.session.add(module)
    db.session.flush()
    # Handle optional PDF upload
    file = request.files.get('pdf_file')
    if file and file.filename.lower().endswith('.pdf'):
        module.pdf_data = file.read()
        module.pdf_filename = secure_filename(file.filename)
    db.session.commit()
    flash(f'Module "{module.title}" added.', 'success')
    return redirect(url_for('clinic_portal.manage_modules'))


@clinic_portal_bp.route('/modules/<int:module_id>/edit', methods=['POST'])
@clinic_login_required
def edit_module(module_id):
    account = _current_clinic_account()
    module = LearningModule.query.filter_by(id=module_id, clinic_account_id=account.id).first_or_404()
    title = request.form.get('title', '').strip()
    if title:
        module.title = title
    module.description = request.form.get('description', '').strip()
    module.content = request.form.get('content', '').strip()
    cat = request.form.get('category', module.category)
    if cat in CATEGORY_META:
        module.category = cat
    module.age_group = request.form.get('age_group', '').strip()
    module.is_special_needs = (module.category == 'special_needs')
    # Handle optional PDF upload
    file = request.files.get('pdf_file')
    if file and file.filename.lower().endswith('.pdf'):
        module.pdf_data = file.read()
        module.pdf_filename = secure_filename(file.filename)
    db.session.commit()
    flash(f'Module "{module.title}" updated.', 'success')
    return redirect(url_for('clinic_portal.manage_modules'))


@clinic_portal_bp.route('/modules/<int:module_id>/delete', methods=['POST'])
@clinic_login_required
def delete_module(module_id):
    account = _current_clinic_account()
    module = LearningModule.query.filter_by(id=module_id, clinic_account_id=account.id).first_or_404()
    title = module.title
    db.session.delete(module)
    db.session.commit()
    flash(f'Module "{title}" deleted.', 'info')
    return redirect(url_for('clinic_portal.manage_modules'))


@clinic_portal_bp.route('/modules/<int:module_id>/pdf')
@clinic_login_required
def view_pdf(module_id):
    account = _current_clinic_account()
    module = LearningModule.query.filter_by(id=module_id, clinic_account_id=account.id).first_or_404()
    if not module.pdf_data:
        abort(404)
    return Response(BytesIO(module.pdf_data), mimetype='application/pdf',
                    headers={'Content-Disposition': 'inline'})


# ── Announcements ─────────────────────────────────────────────────────────────

@clinic_portal_bp.route('/announcements')
@clinic_login_required
def announcements():
    account = _current_clinic_account()
    if not account.clinic:
        return redirect(url_for('clinic_portal.setup_clinic'))
    anns = ClinicAnnouncement.query.filter_by(clinic_id=account.clinic.id)\
                                   .order_by(ClinicAnnouncement.created_at.desc()).all()
    return render_template('clinic_portal/announcements.html',
                           account=account,
                           clinic=account.clinic,
                           announcements=anns)


@clinic_portal_bp.route('/announcements/add', methods=['POST'])
@clinic_login_required
def add_announcement():
    account = _current_clinic_account()
    if not account.clinic:
        return redirect(url_for('clinic_portal.setup_clinic'))
    title = request.form.get('title', '').strip()
    body = request.form.get('body', '').strip()
    if not title or not body:
        flash('Title and message are required.', 'error')
        return redirect(url_for('clinic_portal.announcements'))
    expires_str = request.form.get('expires_at', '').strip()
    expires = None
    if expires_str:
        try:
            expires = date.fromisoformat(expires_str)
        except ValueError:
            pass
    ann = ClinicAnnouncement(
        clinic_id=account.clinic.id,
        title=title,
        body=body,
        expires_at=expires,
    )
    db.session.add(ann)
    db.session.commit()
    flash(f'Announcement "{title}" posted.', 'success')
    return redirect(url_for('clinic_portal.announcements'))


@clinic_portal_bp.route('/announcements/<int:ann_id>/toggle', methods=['POST'])
@clinic_login_required
def toggle_announcement(ann_id):
    account = _current_clinic_account()
    ann = ClinicAnnouncement.query.filter_by(
        id=ann_id, clinic_id=account.clinic.id
    ).first_or_404()
    ann.is_active = not ann.is_active
    db.session.commit()
    state = 'activated' if ann.is_active else 'deactivated'
    flash(f'Announcement {state}.', 'success')
    return redirect(url_for('clinic_portal.announcements'))


@clinic_portal_bp.route('/announcements/<int:ann_id>/delete', methods=['POST'])
@clinic_login_required
def delete_announcement(ann_id):
    account = _current_clinic_account()
    ann = ClinicAnnouncement.query.filter_by(
        id=ann_id, clinic_id=account.clinic.id
    ).first_or_404()
    db.session.delete(ann)
    db.session.commit()
    flash('Announcement deleted.', 'info')
    return redirect(url_for('clinic_portal.announcements'))


# ── Two-Factor Authentication ─────────────────────────────────────────────────

def _make_qr_b64(account):
    """Return a base64-encoded PNG of the TOTP provisioning QR code."""
    uri = pyotp.totp.TOTP(account.totp_secret).provisioning_uri(
        name=account.email,
        issuer_name='PaPrep Clinic Portal'
    )
    img = qrcode.make(uri)
    buf = BytesIO()
    img.save(buf, format='PNG')
    return base64.b64encode(buf.getvalue()).decode()


@clinic_portal_bp.route('/2fa/verify', methods=['GET', 'POST'])
def verify_2fa():
    """Step 2 of login: verify TOTP code when 2FA is enabled."""
    pending_id = session.get('clinic_pending_2fa')
    if not pending_id:
        return redirect(url_for('clinic_portal.login'))
    account = db.session.get(ClinicAccount, pending_id)
    if not account:
        session.pop('clinic_pending_2fa', None)
        return redirect(url_for('clinic_portal.login'))

    if request.method == 'POST':
        code = request.form.get('code', '').strip().replace(' ', '')
        totp = pyotp.TOTP(account.totp_secret)
        if totp.verify(code, valid_window=1):
            session.pop('clinic_pending_2fa', None)
            session.permanent = True
            session['clinic_account_id'] = account.id
            flash(f'Welcome back, {account.contact_name}!', 'success')
            return redirect(url_for('clinic_portal.dashboard'))
        flash('Invalid or expired code. Please try again.', 'error')

    return render_template('clinic_portal/2fa_verify.html')


@clinic_portal_bp.route('/2fa/setup')
@clinic_login_required
def setup_2fa():
    """Show QR code for the authenticator app."""
    account = _current_clinic_account()
    if not account.totp_secret:
        account.totp_secret = pyotp.random_base32()
        db.session.commit()
    qr_b64 = _make_qr_b64(account)
    return render_template('clinic_portal/2fa_setup.html',
                           account=account,
                           qr_b64=qr_b64,
                           secret=account.totp_secret)


@clinic_portal_bp.route('/2fa/enable', methods=['POST'])
@clinic_login_required
def enable_2fa():
    """Verify the first TOTP code then activate 2FA."""
    account = _current_clinic_account()
    if not account.totp_secret:
        flash('Please scan the QR code first.', 'error')
        return redirect(url_for('clinic_portal.setup_2fa'))
    code = request.form.get('code', '').strip().replace(' ', '')
    totp = pyotp.TOTP(account.totp_secret)
    if totp.verify(code, valid_window=1):
        account.totp_enabled = True
        db.session.commit()
        flash('Two-factor authentication has been enabled.', 'success')
        return redirect(url_for('clinic_portal.dashboard'))
    flash('Invalid code. Please try again with a fresh code from your app.', 'error')
    return redirect(url_for('clinic_portal.setup_2fa'))


@clinic_portal_bp.route('/2fa/disable', methods=['POST'])
@clinic_login_required
def disable_2fa():
    """Disable 2FA after confirming the current TOTP code."""
    account = _current_clinic_account()
    code = request.form.get('code', '').strip().replace(' ', '')
    if not account.totp_secret or not pyotp.TOTP(account.totp_secret).verify(code, valid_window=1):
        flash('Invalid code. 2FA was not disabled.', 'error')
        return redirect(url_for('clinic_portal.setup_2fa'))
    account.totp_enabled = False
    account.totp_secret = None
    db.session.commit()
    flash('Two-factor authentication has been disabled.', 'info')
    return redirect(url_for('clinic_portal.dashboard'))


# ── Patients ──────────────────────────────────────────────────────────────────

@clinic_portal_bp.route('/patients')
@clinic_login_required
def patients():
    account = _current_clinic_account()
    if not account.clinic:
        return redirect(url_for('clinic_portal.setup_clinic'))
        
    # Get all users registered to this clinic
    from models import ClinicRegistration
    registrations = ClinicRegistration.query.filter_by(clinic_id=account.clinic.id).order_by(ClinicRegistration.created_at.desc()).all()
    
    return render_template('clinic_portal/patients.html',
                           account=account,
                           clinic=account.clinic,
                           registrations=registrations)

