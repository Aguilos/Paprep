"""
Clinic Portal — separate auth + dashboard for clinic accounts.
Uses a session key 'clinic_id' instead of flask-login to keep it
completely separate from the parent-user login.
"""
import os
import base64
import functools
import hashlib
import secrets
from datetime import date, datetime
from io import BytesIO
from urllib.parse import urlparse
import pyotp
import qrcode

from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, session, abort, send_file, Response, current_app,
                   jsonify)
from werkzeug.utils import secure_filename
from app import db
from models import (ClinicAccount, Clinic, ClinicSchedule, LearningModule,
                    ClinicAnnouncement, ParentChildResource, PasswordResetToken,
                    ClinicRegistration, ChildProfile, Newsletter, NewsletterMedia,
                    ModuleQuizQuestion)

clinic_portal_bp = Blueprint('clinic_portal', __name__, url_prefix='/clinic')

DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
CATEGORY_META = {
    'parenting':     {'label': 'Parenting',    'icon': 'bi-people-fill',      'color': '#4E97D9'},
    'nutrition':     {'label': 'Nutrition',    'icon': 'bi-apple',            'color': '#5CAD5C'},
    'safety':        {'label': 'Safety',       'icon': 'bi-shield-check',     'color': '#FF8C42'},
    'health':        {'label': 'Child Health', 'icon': 'bi-heart-pulse-fill', 'color': '#E74C3C'},
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

def _parse_int(val, default=0):
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _clinic_child_registration(account, child_id):
    """Return a valid clinic-child registration, or None for unrelated children."""
    registration = ClinicRegistration.query.filter_by(
        clinic_id=account.clinic.id,
        child_id=child_id,
    ).first()
    if not registration or not registration.child:
        return None
    if registration.child.user_id != registration.user_id:
        return None
    return registration


def _newsletter_media_from_form(form):
    media = []
    types = form.getlist('media_type')
    sources = form.getlist('media_source')
    captions = form.getlist('media_caption')
    if len(types) > 10:
        raise ValueError('A newsletter can contain at most 10 media attachments.')
    for index, (media_type, source) in enumerate(zip(types, sources)):
        media_type = media_type.strip().lower()
        source = source.strip()
        caption = captions[index].strip() if index < len(captions) else ''
        if not source:
            continue
        parsed = urlparse(source)
        if parsed.scheme not in ('http', 'https') or not parsed.netloc:
            raise ValueError('Media sources must be valid http(s) URLs.')
        if media_type == 'video':
            from models import youtube_embed_url
            if not youtube_embed_url(source):
                raise ValueError('Video attachments must use a YouTube URL.')
        elif media_type != 'image':
            raise ValueError('Media type must be image or video.')
        media.append(NewsletterMedia(media_type=media_type, source=source, caption=caption or None))
    return media


def _replace_newsletter_media(newsletter, form):
    newsletter.media.clear()
    newsletter.media.extend(_newsletter_media_from_form(form))


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


@clinic_portal_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    reset_url = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        account = ClinicAccount.query.filter_by(email=email).first() if email else None
        if account:
            raw_token = secrets.token_urlsafe(32)
            token = PasswordResetToken(
                token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
                clinic_account_id=account.id,
                expires_at=datetime.utcnow() + current_app.config['PASSWORD_RESET_TOKEN_TTL'],
            )
            db.session.add(token)
            db.session.commit()
            reset_url = url_for('clinic_portal.reset_password', token=raw_token, _external=True)
        flash('If an account matches that email, a password reset link is ready.', 'info')
    return render_template('clinic_portal/forgot_password.html', reset_url=reset_url)


@clinic_portal_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    token_record = PasswordResetToken.query.filter_by(
        token_hash=hashlib.sha256(token.encode()).hexdigest(), used_at=None
    ).first()
    if not token_record or token_record.expires_at < datetime.utcnow() or not token_record.clinic_account_id:
        flash('This password reset link is invalid or expired.', 'error')
        return redirect(url_for('clinic_portal.forgot_password'))
    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        if len(password) < MIN_PASSWORD_LENGTH:
            flash(f'Password must be at least {MIN_PASSWORD_LENGTH} characters.', 'error')
        elif password != confirm:
            flash('Passwords do not match.', 'error')
        else:
            token_record.clinic_account.set_password(password)
            token_record.used_at = datetime.utcnow()
            db.session.commit()
            flash('Your password has been reset. You can now log in.', 'success')
            return redirect(url_for('clinic_portal.login'))
    return render_template('clinic_portal/reset_password.html')


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
    resources = ParentChildResource.query.filter_by(clinic_account_id=account.id)\
                                         .order_by(ParentChildResource.id.desc()).all()
    return render_template('clinic_portal/manage_modules.html',
                           account=account,
                           clinic=account.clinic,
                           modules=modules,
                           resources=resources,
                           category_meta=CATEGORY_META)


@clinic_portal_bp.route('/resources/add', methods=['POST'])
@clinic_login_required
def add_resource():
    account = _current_clinic_account()
    if not account.clinic:
        return redirect(url_for('clinic_portal.setup_clinic'))
    title = request.form.get('title', '').strip()
    url = request.form.get('url', '').strip()
    resource_type = request.form.get('resource_type', 'link')
    if not title or not url:
        flash('Resource title and URL are required.', 'error')
        return redirect(url_for('clinic_portal.manage_modules'))
    if resource_type not in ('video', 'link'):
        resource_type = 'link'
    min_age = _parse_int(request.form.get('target_age_min_months'), 0)
    max_age = _parse_int(request.form.get('target_age_max_months'), 60)
    if min_age < 0 or max_age < min_age:
        flash('Please provide a valid age range.', 'error')
        return redirect(url_for('clinic_portal.manage_modules'))
    resource = ParentChildResource(
        title=title,
        description=request.form.get('description', '').strip(),
        url=url,
        thumbnail_url=request.form.get('thumbnail_url', '').strip() or None,
        resource_type=resource_type,
        category=request.form.get('category', 'parenting').strip() or 'parenting',
        target_age_min_months=min_age,
        target_age_max_months=max_age,
        clinic_account_id=account.id,
    )
    db.session.add(resource)
    db.session.commit()
    flash(f'Resource "{resource.title}" added.', 'success')
    return redirect(url_for('clinic_portal.manage_modules'))


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
    flash(f'Module "{module.title}" created. Add content and quiz questions below.', 'success')
    return redirect(url_for('clinic_portal.module_editor', module_id=module.id))


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


# ── Module Full-Page Editor ───────────────────────────────────────────────────

@clinic_portal_bp.route('/modules/<int:module_id>/editor', methods=['GET', 'POST'])
@clinic_login_required
def module_editor(module_id):
    """Dedicated full-page editor for a clinic-owned module."""
    account = _current_clinic_account()
    module = LearningModule.query.filter_by(id=module_id, clinic_account_id=account.id).first_or_404()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if title:
            module.title = title
        module.description = request.form.get('description', '').strip()
        module.content     = request.form.get('content', '').strip()
        cat = request.form.get('category', module.category)
        if cat in CATEGORY_META:
            module.category = cat
        module.age_group = request.form.get('age_group', '').strip()
        file = request.files.get('pdf_file')
        if file and file.filename.lower().endswith('.pdf'):
            module.pdf_data     = file.read()
            module.pdf_filename = secure_filename(file.filename)
        db.session.commit()
        flash(f'Module "{module.title}" saved successfully.', 'success')
        return redirect(url_for('clinic_portal.module_editor', module_id=module.id))

    questions = ModuleQuizQuestion.query.filter_by(module_id=module_id)\
        .order_by(ModuleQuizQuestion.sort_order, ModuleQuizQuestion.id).all()

    return render_template('clinic_portal/module_editor.html',
                           account=account,
                           module=module,
                           questions=questions,
                           category_meta=CATEGORY_META)


# ── Quiz Question CRUD (AJAX) ─────────────────────────────────────────────────

@clinic_portal_bp.route('/modules/<int:module_id>/quiz/add', methods=['POST'])
@clinic_login_required
def add_quiz_question(module_id):
    account = _current_clinic_account()
    LearningModule.query.filter_by(id=module_id, clinic_account_id=account.id).first_or_404()

    data = request.get_json(silent=True) or request.form
    question_text = (data.get('question') or '').strip()
    option_a      = (data.get('option_a') or '').strip()
    option_b      = (data.get('option_b') or '').strip()
    correct       = (data.get('correct') or '').lower().strip()

    if not question_text or not option_a or not option_b or correct not in ('a', 'b', 'c', 'd'):
        return jsonify({'ok': False, 'error': 'question, option_a, option_b and correct (a/b/c/d) are required.'}), 400

    # Determine next sort_order
    max_order = db.session.query(db.func.max(ModuleQuizQuestion.sort_order))\
        .filter_by(module_id=module_id).scalar() or 0

    q = ModuleQuizQuestion(
        module_id=module_id,
        question=question_text,
        option_a=option_a,
        option_b=option_b,
        option_c=(data.get('option_c') or '').strip() or None,
        option_d=(data.get('option_d') or '').strip() or None,
        correct=correct,
        explanation=(data.get('explanation') or '').strip() or None,
        sort_order=max_order + 1,
    )
    db.session.add(q)
    db.session.commit()
    return jsonify({'ok': True, 'question': q.to_dict()})


@clinic_portal_bp.route('/modules/<int:module_id>/quiz/<int:q_id>/edit', methods=['POST'])
@clinic_login_required
def edit_quiz_question(module_id, q_id):
    account = _current_clinic_account()
    LearningModule.query.filter_by(id=module_id, clinic_account_id=account.id).first_or_404()
    q = ModuleQuizQuestion.query.filter_by(id=q_id, module_id=module_id).first_or_404()

    data = request.get_json(silent=True) or request.form
    if data.get('question'):
        q.question = data['question'].strip()
    if data.get('option_a'):
        q.option_a = data['option_a'].strip()
    if data.get('option_b'):
        q.option_b = data['option_b'].strip()
    q.option_c = (data.get('option_c') or '').strip() or None
    q.option_d = (data.get('option_d') or '').strip() or None
    correct = (data.get('correct') or '').lower().strip()
    if correct in ('a', 'b', 'c', 'd'):
        q.correct = correct
    q.explanation = (data.get('explanation') or '').strip() or None
    db.session.commit()
    return jsonify({'ok': True, 'question': q.to_dict()})


@clinic_portal_bp.route('/modules/<int:module_id>/quiz/<int:q_id>/delete', methods=['POST'])
@clinic_login_required
def delete_quiz_question(module_id, q_id):
    account = _current_clinic_account()
    LearningModule.query.filter_by(id=module_id, clinic_account_id=account.id).first_or_404()
    q = ModuleQuizQuestion.query.filter_by(id=q_id, module_id=module_id).first_or_404()
    db.session.delete(q)
    db.session.commit()
    return jsonify({'ok': True})


@clinic_portal_bp.route('/modules/<int:module_id>/image/upload', methods=['POST'])
@clinic_login_required
def upload_module_image(module_id):
    """AJAX endpoint: upload an image for use in module content. Returns JSON {ok, url}."""
    account = _current_clinic_account()
    LearningModule.query.filter_by(id=module_id, clinic_account_id=account.id).first_or_404()
    f = request.files.get('image')
    if not f:
        return jsonify({'ok': False, 'error': 'No file provided'}), 400
    ext = os.path.splitext(secure_filename(f.filename))[1].lower()
    if ext not in ('.jpg', '.jpeg', '.png', '.gif', '.webp'):
        return jsonify({'ok': False, 'error': 'Unsupported file type. Use JPG, PNG, GIF, or WebP.'}), 400
    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], str(module_id))
    os.makedirs(upload_dir, exist_ok=True)
    fname = f"{secrets.token_hex(8)}{ext}"
    f.save(os.path.join(upload_dir, fname))
    url = url_for('static', filename=f'uploads/modules/{module_id}/{fname}')
    return jsonify({'ok': True, 'url': url})


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


# ── Child newsletters ────────────────────────────────────────────────────────

@clinic_portal_bp.route('/newsletters')
@clinic_login_required
def newsletters():
    account = _current_clinic_account()
    if not account.clinic:
        return redirect(url_for('clinic_portal.setup_clinic'))
    registrations = ClinicRegistration.query.filter(
        ClinicRegistration.clinic_id == account.clinic.id,
        ClinicRegistration.child_id.isnot(None),
    ).order_by(ClinicRegistration.created_at.desc()).all()
    entries = Newsletter.query.filter_by(clinic_id=account.clinic.id).order_by(
        Newsletter.updated_at.desc(), Newsletter.id.desc()
    ).all()
    return render_template('clinic_portal/newsletters.html',
                           account=account, clinic=account.clinic,
                           registrations=registrations, newsletters=entries)


@clinic_portal_bp.route('/newsletters/add', methods=['POST'])
@clinic_login_required
def add_newsletter():
    account = _current_clinic_account()
    if not account.clinic:
        return redirect(url_for('clinic_portal.setup_clinic'))
    child_id = _parse_int(request.form.get('child_id'), 0)
    registration = _clinic_child_registration(account, child_id)
    if not registration:
        abort(403)
    title = request.form.get('title', '').strip()
    body = request.form.get('body', '').strip()
    if not title or not body:
        flash('Newsletter title and body are required.', 'error')
        return redirect(url_for('clinic_portal.newsletters'))
    try:
        media = _newsletter_media_from_form(request.form)
    except ValueError as error:
        flash(str(error), 'error')
        return redirect(url_for('clinic_portal.newsletters'))
    newsletter = Newsletter(
        title=title,
        body=body,
        child_id=child_id,
        clinic_id=account.clinic.id,
        is_published=request.form.get('action') == 'publish',
    )
    newsletter.media.extend(media)
    db.session.add(newsletter)
    db.session.commit()
    flash(f'Newsletter "{title}" saved.', 'success')
    return redirect(url_for('clinic_portal.newsletters'))


@clinic_portal_bp.route('/newsletters/<int:newsletter_id>/edit', methods=['POST'])
@clinic_login_required
def edit_newsletter(newsletter_id):
    account = _current_clinic_account()
    newsletter = Newsletter.query.filter_by(
        id=newsletter_id, clinic_id=account.clinic.id
    ).first_or_404()
    if not _clinic_child_registration(account, newsletter.child_id):
        abort(403)
    title = request.form.get('title', '').strip()
    body = request.form.get('body', '').strip()
    if not title or not body:
        flash('Newsletter title and body are required.', 'error')
        return redirect(url_for('clinic_portal.newsletters'))
    try:
        _replace_newsletter_media(newsletter, request.form)
    except ValueError as error:
        flash(str(error), 'error')
        return redirect(url_for('clinic_portal.newsletters'))
    newsletter.title = title
    newsletter.body = body
    newsletter.is_published = request.form.get('action') == 'publish'
    db.session.commit()
    flash(f'Newsletter "{title}" updated.', 'success')
    return redirect(url_for('clinic_portal.newsletters'))


@clinic_portal_bp.route('/newsletters/<int:newsletter_id>/toggle', methods=['POST'])
@clinic_login_required
def toggle_newsletter(newsletter_id):
    account = _current_clinic_account()
    newsletter = Newsletter.query.filter_by(
        id=newsletter_id, clinic_id=account.clinic.id
    ).first_or_404()
    if not _clinic_child_registration(account, newsletter.child_id):
        abort(403)
    newsletter.is_published = not newsletter.is_published
    db.session.commit()
    flash('Newsletter published.' if newsletter.is_published else 'Newsletter unpublished.', 'success')
    return redirect(url_for('clinic_portal.newsletters'))

