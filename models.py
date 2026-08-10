from datetime import datetime, date
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import deferred
from app import db
from utils import today_pht


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(60), nullable=False)
    last_name = db.Column(db.String(60), nullable=False)
    phone = db.Column(db.String(20))
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    children = db.relationship(
        'ChildProfile', backref='parent', lazy=True,
        cascade='all, delete-orphan'
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.email}>'


class ChildProfile(db.Model):
    __tablename__ = 'child_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    gender = db.Column(db.String(10))
    # 'normal' or 'special_needs'
    child_type = db.Column(db.String(20), nullable=False, default='normal')
    special_needs_type = db.Column(db.String(200))
    special_needs_notes = db.Column(db.Text)
    profile_color = db.Column(db.String(7), default='#4E97D9')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def age_months(self):
        today = today_pht()
        months = (
            (today.year - self.date_of_birth.year) * 12
            + (today.month - self.date_of_birth.month)
        )
        return max(0, months)

    @property
    def age_display(self):
        months = self.age_months
        if months < 1:
            days = (today_pht() - self.date_of_birth).days
            return f"{days} day{'s' if days != 1 else ''}"
        if months < 12:
            return f"{months} month{'s' if months != 1 else ''}"
        years = months // 12
        rem = months % 12
        if rem == 0:
            return f"{years} year{'s' if years != 1 else ''}"
        return f"{years} yr {rem} mo"

    @property
    def age_bracket(self):
        m = self.age_months
        if m < 12:
            return '0–12 months'
        elif m < 24:
            return '1–2 years'
        elif m < 36:
            return '2–3 years'
        elif m < 48:
            return '3–4 years'
        else:
            return '4–5 years'

    def __repr__(self):
        return f'<Child {self.name}>'


class LearningModule(db.Model):
    __tablename__ = 'learning_modules'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    # parenting | nutrition | safety | health | special_needs
    category = db.Column(db.String(30), nullable=False)
    content = db.Column(db.Text)
    age_group = db.Column(db.String(50))
    is_special_needs = db.Column(db.Boolean, default=False)
    icon = db.Column(db.String(60), default='bi-book')
    sort_order = db.Column(db.Integer, default=0)
    pdf_filename = db.Column(db.String(255))
    pdf_data = deferred(db.Column(db.LargeBinary))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # NULL = system module (admin), set = clinic-owned module
    clinic_account_id = db.Column(db.Integer, db.ForeignKey('clinic_accounts.id'), nullable=True)

    def __repr__(self):
        return f'<Module {self.title}>'


class Symptom(db.Model):
    __tablename__ = 'symptoms'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(30))
    icon = db.Column(db.String(60), default='bi-circle')
    is_emergency = db.Column(db.Boolean, default=False)
    sort_order = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'category': self.category,
            'icon': self.icon,
            'is_emergency': self.is_emergency,
        }


class ClinicAccount(UserMixin, db.Model):
    """Login account for a clinic (staff/owner). Separate from the parent User."""
    __tablename__ = 'clinic_accounts'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    contact_name = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    totp_secret = db.Column(db.String(32), nullable=True)
    totp_enabled = db.Column(db.Boolean, default=False)

    # one account → one clinic
    clinic = db.relationship('Clinic', backref='account', uselist=False, lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<ClinicAccount {self.email}>'


class Clinic(db.Model):
    __tablename__ = 'clinics'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    address = db.Column(db.Text)
    city = db.Column(db.String(100))
    phone = db.Column(db.String(30))
    email = db.Column(db.String(120))
    website = db.Column(db.String(200))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    # pediatric | general | specialty
    clinic_type = db.Column(db.String(30))
    accepts_special_needs = db.Column(db.Boolean, default=False)
    description = db.Column(db.Text)
    # FK to clinic account that owns this clinic
    clinic_account_id = db.Column(db.Integer, db.ForeignKey('clinic_accounts.id'), nullable=True)

    schedules = db.relationship(
        'ClinicSchedule', backref='clinic', lazy=True,
        cascade='all, delete-orphan'
    )
    time_slots = db.relationship(
        'TimeSlot', backref='clinic', lazy=True,
        cascade='all, delete-orphan'
    )
    announcements = db.relationship(
        'ClinicAnnouncement', backref='clinic', lazy=True,
        cascade='all, delete-orphan'
    )

    @property
    def has_active_announcement(self):
        today = today_pht()
        return any(
            a.is_active and (a.expires_at is None or a.expires_at >= today)
            for a in self.announcements
        )

    def to_dict(self):
        today = today_pht()
        preview = next(
            (a.title for a in self.announcements
             if a.is_active and (a.expires_at is None or a.expires_at >= today)),
            None
        )
        return {
            'id': self.id,
            'name': self.name,
            'address': self.address,
            'city': self.city,
            'phone': self.phone,
            'email': self.email,
            'website': self.website,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'clinic_type': self.clinic_type,
            'accepts_special_needs': self.accepts_special_needs,
            'description': self.description,
            'has_announcement': self.has_active_announcement,
            'announcement_preview': preview,
        }


class ClinicSchedule(db.Model):
    __tablename__ = 'clinic_schedules'

    id = db.Column(db.Integer, primary_key=True)
    clinic_id = db.Column(db.Integer, db.ForeignKey('clinics.id'), nullable=False)
    day_of_week = db.Column(db.String(10))
    open_time = db.Column(db.String(8))
    close_time = db.Column(db.String(8))
    is_closed = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            'id': self.id,
            'day_of_week': self.day_of_week,
            'open_time': self.open_time,
            'close_time': self.close_time,
            'is_closed': self.is_closed,
        }


class HealthChecklist(db.Model):
    """Daily dietary & health monitoring checklist per child."""
    __tablename__ = 'health_checklists'

    id = db.Column(db.Integer, primary_key=True)
    child_id = db.Column(db.Integer, db.ForeignKey('child_profiles.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    checked_items = db.Column(db.Text, default='[]')   # JSON list of item keys
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    child = db.relationship('ChildProfile', backref='checklists')

    def get_checked(self):
        import json
        try:
            return json.loads(self.checked_items or '[]')
        except Exception:
            return []

    def __repr__(self):
        return f'<HealthChecklist child={self.child_id} date={self.date}>'


class ClinicAnnouncement(db.Model):
    __tablename__ = 'clinic_announcements'

    id = db.Column(db.Integer, primary_key=True)
    clinic_id = db.Column(db.Integer, db.ForeignKey('clinics.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.Date, nullable=True)

    def __repr__(self):
        return f'<Announcement {self.title}>'


class TimeSlot(db.Model):
    __tablename__ = 'time_slots'

    id = db.Column(db.Integer, primary_key=True)
    clinic_id = db.Column(db.Integer, db.ForeignKey('clinics.id'), nullable=False)
    slot_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.String(8))
    end_time = db.Column(db.String(8))
    total_slots = db.Column(db.Integer, default=10)
    booked_slots = db.Column(db.Integer, default=0)

    @property
    def available(self):
        return self.total_slots - self.booked_slots

    @property
    def is_full(self):
        return self.booked_slots >= self.total_slots

    def to_dict(self):
        return {
            'id': self.id,
            'slot_date': self.slot_date.isoformat(),
            'start_time': self.start_time,
            'end_time': self.end_time,
            'total_slots': self.total_slots,
            'booked_slots': self.booked_slots,
            'available': self.available,
            'is_full': self.is_full,
        }


class ClinicMessage(db.Model):
    __tablename__ = 'clinic_messages'

    id = db.Column(db.Integer, primary_key=True)
    clinic_id = db.Column(db.Integer, db.ForeignKey('clinics.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    # 'user' or 'clinic' — who sent this message
    sender = db.Column(db.String(16), nullable=False, default='user')
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)

    user = db.relationship('User', backref='clinic_messages', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'clinic_id': self.clinic_id,
            'user_id': self.user_id,
            'sender': self.sender,
            'text': self.text,
            'created_at': self.created_at.isoformat(),
            'is_read': self.is_read,
        }
