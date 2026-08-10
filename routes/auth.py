from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, jsonify)
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from models import User

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


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been signed out. See you soon!', 'info')
    return redirect(url_for('auth.login'))
