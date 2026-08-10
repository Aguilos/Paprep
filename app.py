from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from config import Config
from flask_socketio import SocketIO, join_room, leave_room

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
socketio = SocketIO(cors_allowed_origins='*')


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access PaPrep.'
    login_manager.login_message_category = 'info'

    from models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # Register blueprints
    from routes.main import main_bp
    from routes.auth import auth_bp
    from routes.children import children_bp
    from routes.modules import modules_bp
    from routes.symptoms import symptoms_bp
    from routes.clinics import clinics_bp
    from routes.clinic_portal import clinic_portal_bp
    from routes.chat import chat_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(children_bp)
    app.register_blueprint(modules_bp)
    app.register_blueprint(symptoms_bp)
    app.register_blueprint(clinics_bp)
    app.register_blueprint(clinic_portal_bp)
    app.register_blueprint(chat_bp)

    # Context processor: inject child context into all templates
    from flask_login import current_user

    @app.context_processor
    def inject_child_context():
        if current_user.is_authenticated:
            from flask import session as flask_session
            children = current_user.children
            has_special_needs_child = any(
                c.child_type == 'special_needs' for c in children
            )
            active_child_id = flask_session.get('active_child_id')
            if not active_child_id and children:
                active_child_id = children[0].id
                flask_session['active_child_id'] = active_child_id
            active_child = next(
                (c for c in children if c.id == active_child_id),
                children[0] if children else None
            )
            return {
                'has_special_needs_child': has_special_needs_child,
                'children': children,
                'active_child': active_child,
                'active_child_id': active_child_id,
            }
        return {
            'has_special_needs_child': False,
            'children': [],
            'active_child': None,
            'active_child_id': None,
        }

    with app.app_context():
        db.create_all()

    # Attach SocketIO to the app
    socketio.init_app(app)

    # Socket handlers
    @socketio.on('join')
    def handle_join(data):
        try:
            cid = data.get('clinic_id')
            uid = data.get('user_id')
            if cid and uid:
                room = f"chat_{cid}_{uid}"
                join_room(room)
        except Exception:
            pass

    @app.shell_context_processor
    def make_shell_context():
        from models import (User, ChildProfile, LearningModule, Symptom,
                            ClinicAccount, Clinic, ClinicSchedule, TimeSlot)
        return dict(
            db=db,
            User=User,
            ChildProfile=ChildProfile,
            LearningModule=LearningModule,
            Symptom=Symptom,
            ClinicAccount=ClinicAccount,
            Clinic=Clinic,
            ClinicSchedule=ClinicSchedule,
            TimeSlot=TimeSlot,
        )

    return app
