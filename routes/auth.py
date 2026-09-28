import hashlib
import secrets
from datetime import datetime, timedelta
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, jsonify, current_app, abort)
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from models import User, PasswordResetToken

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

MIN_PASSWORD_LENGTH = 8


@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        # Server-side validation
        errors = []
        if not first_name or not last_name:
            errors.append('Full name is required.')
        if not email or '@' not in email:
            errors.append('A valid email address is required.')
        if len(password) < MIN_PASSWORD_LENGTH:
            errors.append(f'Password must be at least {MIN_PASSWORD_LENGTH} characters.')
        if password != confirm:
            errors.append('Passwords do not match.')

        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template('auth/signup.html',
                                   first_name=first_name,
                                   last_name=last_name,
                                   email=email,
                                   phone=phone)

        if User.query.filter_by(email=email).first():
            flash('An account with that email already exists.', 'error')
            return render_template('auth/signup.html', email=email)

        user = User(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user, remember=True)
        flash(f'Welcome to PaPrep, {first_name}! Let\'s set up your child\'s profile.', 'success')
        return redirect(url_for('children.create_child'))

    return render_template('auth/signup.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))

        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash('Invalid email or password. Please try again.', 'error')
            return render_template('auth/login.html', email=email)

        login_user(user, remember=remember)

        if not user.children:
            return redirect(url_for('children.create_child'))

        next_page = request.args.get('next')
        if next_page and next_page.startswith('/'):
            return redirect(next_page)
        return redirect(url_for('main.dashboard'))

    return render_template('auth/login.html')


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    reset_url = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = User.query.filter_by(email=email).first() if email else None
        if user:
            raw_token = secrets.token_urlsafe(32)
            token = PasswordResetToken(
                token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
                user_id=user.id,
                expires_at=datetime.utcnow() + current_app.config['PASSWORD_RESET_TOKEN_TTL'],
            )
            db.session.add(token)
            db.session.commit()
            reset_url = url_for('auth.reset_password', token=raw_token, _external=True)
        flash('If an account matches that email, a password reset link is ready.', 'info')
    return render_template('auth/forgot_password.html', reset_url=reset_url)


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    token_record = PasswordResetToken.query.filter_by(
        token_hash=hashlib.sha256(token.encode()).hexdigest(), used_at=None
    ).first()
    if not token_record or token_record.expires_at < datetime.utcnow() or not token_record.user_id:
        flash('This password reset link is invalid or expired.', 'error')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        if len(password) < MIN_PASSWORD_LENGTH:
            flash(f'Password must be at least {MIN_PASSWORD_LENGTH} characters.', 'error')
        elif password != confirm:
            flash('Passwords do not match.', 'error')
        else:
            token_record.user.set_password(password)
            token_record.used_at = datetime.utcnow()
            db.session.commit()
            flash('Your password has been reset. You can now log in.', 'success')
            return redirect(url_for('auth.login'))
    return render_template('auth/reset_password.html')


@auth_bp.route('/profile', methods=['POST'])
@login_required
def profile():
    if (current_user.role or '').lower() != 'parent':
        abort(403)

    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    email = request.form.get('email', '').strip().lower()
    current_password = request.form.get('current_password', '')
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')

    errors = []
    if not first_name or not last_name:
        errors.append('First and last name are required.')
    if not email or '@' not in email:
        errors.append('A valid email address is required.')
    existing = User.query.filter(User.email == email, User.id != current_user.id).first()
    if existing:
        errors.append('That email address is already in use.')

    changing_password = any((current_password, new_password, confirm_password))
    if changing_password:
        if not current_password or not current_user.check_password(current_password):
            errors.append('Your current password is incorrect.')
        if len(new_password) < MIN_PASSWORD_LENGTH:
            errors.append(f'New password must be at least {MIN_PASSWORD_LENGTH} characters.')
        if new_password != confirm_password:
            errors.append('New passwords do not match.')

    if errors:
        for error in errors:
            flash(error, 'error')
    else:
        current_user.first_name = first_name
        current_user.last_name = last_name
        current_user.email = email
        if changing_password:
            current_user.set_password(new_password)
        db.session.commit()
        flash('Account settings updated successfully.', 'success')

    return redirect(request.referrer or url_for('main.dashboard'))


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been signed out. See you soon!', 'info')
    return redirect(url_for('auth.login'))
