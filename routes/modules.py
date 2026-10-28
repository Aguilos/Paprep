from io import BytesIO
import json
import os
from pathlib import Path
from flask import Blueprint, render_template, request, make_response, jsonify, \
    send_file, abort, Response, session
from flask import current_app
from flask_login import login_required, current_user
from models import LearningModule, ModuleProgress, ModuleQuizQuestion
from app import db
from datetime import datetime

modules_bp = Blueprint('modules', __name__, url_prefix='/modules')

CATEGORY_META = {
    'parenting':     {'label': 'Parenting',    'icon': 'bi-people-fill',     'color': '#4E97D9'},
    'nutrition':     {'label': 'Nutrition',    'icon': 'bi-apple',           'color': '#5CAD5C'},
    'safety':        {'label': 'Safety',       'icon': 'bi-shield-check',    'color': '#FF8C42'},
}

PASS_THRESHOLD = 70   # minimum quiz score (%) to mark a module complete

PRESENTATION_FILES = {
    'parenting': 'Parenting.pdf',
    'nutrition': 'Nutrition.pdf',
    'safety': 'Safety.pdf',
}

GIVEN_MODULES_MANIFEST = 'manifest.json'


def given_module_registry():
    base = Path(current_app.config['GIVEN_MODULES_FOLDER'])
    manifest_path = base / GIVEN_MODULES_MANIFEST
    try:
        with manifest_path.open(encoding='utf-8') as manifest_file:
            manifest = json.load(manifest_file)
            if isinstance(manifest, dict) and manifest:
                return manifest
    except (OSError, ValueError):
        pass

    # Auto-generate fallback if manifest is missing or invalid
    titles = {
        'nutrition': ('Nutrition Guide', 'Nutrition.pptx'),
        'nutrition_tagalog': ('Gabay sa Nutrisyon', 'Nutrition_Tagalog.pptx'),
        'parenting': ('Parenting Guide', 'Parenting.pptx'),
        'parenting_tagalog': ('Gabay sa Pagpapalaki', 'Parenting_Tagalog.pptx'),
        'safety': ('Safety Guide', 'Safety.pptx'),
        'safety_tagalog': ('Gabay sa Kaligtasan', 'Safety_Tagalog.pptx'),
    }
    manifest = {}
    for mod_id, (title, filename) in titles.items():
        mod_dir = base / mod_id
        if not mod_dir.is_dir():
            continue
        slides = sorted([f.name for f in mod_dir.glob('slide-*.jpg')])
        if slides:
            manifest[mod_id] = {
                'id': mod_id,
                'title': title,
                'filename': filename,
                'slide_count': len(slides),
                'slides': [{'filename': s, 'alt': f'{title}, slide {i+1} of {len(slides)}'} for i, s in enumerate(slides)],
                'lang': 'tl' if mod_id.endswith('_tagalog') else 'en'
            }
    if manifest:
        try:
            with manifest_path.open('w', encoding='utf-8') as f:
                json.dump(manifest, f, indent=2)
        except OSError:
            pass
    return manifest


def presentation_filename(module):
    return PRESENTATION_FILES.get(module.category)


# ── Public routes (all logged-in users) ─────────────────────────────────────

@modules_bp.route('/')
@login_required
def list_modules():
    query = LearningModule.query.filter(LearningModule.category.in_(CATEGORY_META))
    category = request.args.get('category', '')
    if category and category in CATEGORY_META:
        session['last_module_topic'] = category
        query = query.filter_by(category=category)
    modules = query.order_by(LearningModule.sort_order, LearningModule.id).all()

    # Fetch user progress for all modules in one query
    progress_map = {}
    if current_user.is_authenticated:
        module_ids = [m.id for m in modules]
        if module_ids:
            records = ModuleProgress.query.filter(
                ModuleProgress.user_id == current_user.id,
                ModuleProgress.module_id.in_(module_ids)
            ).all()
            progress_map = {r.module_id: r for r in records}

    # Annotate each module with its progress state
    for m in modules:
        prog = progress_map.get(m.id)
        m.user_status    = prog.status if prog else None
        m.completed      = prog.status == 'completed' if prog else False
        m.in_progress    = prog.status == 'in_progress' if prog else False
        m.last_section   = prog.last_section if prog else 0
        m.quiz_score     = prog.quiz_score if prog else None
        m.presentation_filename = presentation_filename(m)

    grouped = {}
    for m in modules:
        grouped.setdefault(m.category, []).append(m)

    return render_template('modules/modules.html',
                           modules=modules,
                           grouped=grouped,
                           given_modules=given_module_registry(),
                           category_meta=CATEGORY_META,
                           active_category=category,
                           page_title='Learning Modules')


@modules_bp.route('/<int:module_id>')
@login_required
def module_detail(module_id):
    module = LearningModule.query.filter(
        LearningModule.id == module_id,
        LearningModule.category.in_(CATEGORY_META),
    ).first_or_404()
    session['last_module_topic'] = module.category
    meta = CATEGORY_META.get(module.category, {})

    # User progress
    progress = ModuleProgress.query.filter_by(
        user_id=current_user.id, module_id=module_id
    ).first()

    # Quiz questions (prepared as dicts for frontend JSON)
    questions = module.quiz_questions  # ordered by sort_order
    questions_data = [q.to_dict() for q in questions]

    # Upsert: create a progress record if none exists yet
    if not progress:
        progress = ModuleProgress(
            user_id=current_user.id,
            module_id=module_id,
            status='in_progress',
            last_section=0
        )
        db.session.add(progress)
        db.session.commit()

    return render_template('modules/module_detail.html',
                           module=module,
                           presentation_filename=presentation_filename(module),
                           meta=meta,
                           progress=progress,
                           questions=questions,
                           questions_data=questions_data,
                           pass_threshold=PASS_THRESHOLD,
                           page_title=module.title)


@modules_bp.route('/given/<given_id>')
@login_required
def given_module_viewer(given_id):
    registry = given_module_registry()
    given_module = registry.get(given_id)
    if not given_module:
        abort(404)
    base_id = given_id.replace('_tagalog', '')
    if base_id in CATEGORY_META:
        session['last_module_topic'] = base_id

    tagalog_id = f"{base_id}_tagalog"
    tagalog_module = registry.get(tagalog_id)
    english_module = registry.get(base_id)

    return render_template(
        'modules/given_module_viewer.html',
        given_module=given_module,
        base_id=base_id,
        tagalog_module=tagalog_module,
        english_module=english_module,
        page_title=given_module['title'],
    )


@modules_bp.route('/given/<given_id>/pdf')
@login_required
def given_module_pdf(given_id):
    filename_map = {
        'nutrition': 'Nutrition.pdf',
        'nutrition_tagalog': 'Nutrition_Tagalog.pdf',
        'parenting': 'Parenting.pdf',
        'parenting_tagalog': 'Parenting_Tagalog.pdf',
        'safety': 'Safety.pdf',
        'safety_tagalog': 'Safety_Tagalog.pdf',
    }
    filename = filename_map.get(given_id)
    if not filename:
        abort(404)
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    if not os.path.isfile(file_path):
        abort(404)
    return send_file(
        file_path,
        mimetype='application/pdf',
        as_attachment=request.args.get('download') == '1',
        download_name=filename,
    )


@modules_bp.route('/api/track-interaction', methods=['POST'])
@login_required
def track_interaction():
    data = request.get_json(silent=True) or {}
    category = (data.get('category') or '').strip().lower()
    if category in CATEGORY_META:
        session['last_module_topic'] = category
        session.modified = True
        return jsonify({'ok': True, 'category': category})
    return jsonify({'ok': False, 'error': 'Invalid category'}), 400


@modules_bp.route('/given/<given_id>/slide/<int:slide_number>')
@login_required
def given_module_slide(given_id, slide_number):
    given_module = given_module_registry().get(given_id)
    if not given_module or not 1 <= slide_number <= given_module.get('slide_count', 0):
        abort(404)
    slides = given_module.get('slides', [])
    if slide_number > len(slides):
        abort(404)
    filename = slides[slide_number - 1].get('filename')
    if not isinstance(filename, str) or Path(filename).name != filename:
        abort(404)
    slide_path = Path(current_app.config['GIVEN_MODULES_FOLDER']) / given_id / filename
    if not slide_path.is_file():
        abort(404)
    return send_file(slide_path, mimetype='image/jpeg', conditional=False)


@modules_bp.route('/<int:module_id>/pdf')
@login_required
def view_pdf(module_id):
    """Serve PDF stored in DB inline so users can read it in the browser."""
    module = LearningModule.query.filter(
        LearningModule.id == module_id,
        LearningModule.category.in_(CATEGORY_META),
    ).first_or_404()
    if not module.pdf_data:
        abort(404)
    return Response(
        BytesIO(module.pdf_data),
        mimetype='application/pdf',
        headers={'Content-Disposition': 'inline'}
    )


@modules_bp.route('/<int:module_id>/presentation')
@login_required
def view_presentation(module_id):
    """Serve the category presentation converted from the supplied PPTX."""
    module = LearningModule.query.filter(
        LearningModule.id == module_id,
        LearningModule.category.in_(CATEGORY_META),
    ).first_or_404()
    filename = presentation_filename(module)
    if not filename:
        abort(404)
    presentation_path = os.path.join(
        current_app.config['UPLOAD_FOLDER'], filename
    )
    if not os.path.isfile(presentation_path):
        abort(404)
    return send_file(
        presentation_path,
        mimetype='application/pdf',
        as_attachment=False,
        download_name=filename,
    )


@modules_bp.route('/<int:module_id>/download')
@login_required
def download_module(module_id):
    """Download the PDF from DB (or fall back to HTML)."""
    module = LearningModule.query.filter(
        LearningModule.id == module_id,
        LearningModule.category.in_(CATEGORY_META),
    ).first_or_404()
    safe_title = ''.join(c if c.isalnum() else '_' for c in module.title)
    if module.pdf_data:
        return send_file(
            BytesIO(module.pdf_data),
            as_attachment=True,
            download_name=f'PaPrep_{safe_title}.pdf',
            mimetype='application/pdf'
        )
    meta = CATEGORY_META.get(module.category, {})
    html_content = render_template('modules/module_print.html', module=module, meta=meta)
    response = make_response(html_content)
    response.headers['Content-Disposition'] = f'attachment; filename=PaPrep_{safe_title}.html'
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    return response


# ── Interactive Progress API ─────────────────────────────────────────────────

@modules_bp.route('/<int:module_id>/progress', methods=['POST'])
@login_required
def save_progress(module_id):
    """Save the user's last-read section index (called client-side on nav)."""
    LearningModule.query.filter(
        LearningModule.id == module_id,
        LearningModule.category.in_(CATEGORY_META),
    ).first_or_404()
    data = request.get_json(silent=True) or {}
    section_index = int(data.get('section', 0))

    progress = ModuleProgress.query.filter_by(
        user_id=current_user.id, module_id=module_id
    ).first()

    if not progress:
        progress = ModuleProgress(
            user_id=current_user.id,
            module_id=module_id,
            status='in_progress',
            last_section=section_index
        )
        db.session.add(progress)
    else:
        # Only update if moving forward (don't reset on back-nav)
        if section_index > progress.last_section:
            progress.last_section = section_index
        if progress.status != 'completed':
            progress.status = 'in_progress'

    db.session.commit()
    return jsonify({'ok': True, 'last_section': progress.last_section})


@modules_bp.route('/<int:module_id>/quiz', methods=['POST'])
@login_required
def submit_quiz(module_id):
    """Score submitted quiz answers.  Returns score + pass/fail status."""
    module = LearningModule.query.filter(
        LearningModule.id == module_id,
        LearningModule.category.in_(CATEGORY_META),
    ).first_or_404()
    questions = module.quiz_questions
    if not questions:
        return jsonify({'ok': False, 'error': 'No quiz questions for this module.'}), 400

    data = request.get_json(silent=True) or {}
    answers = data.get('answers', {})   # {str(question_id): 'a'|'b'|'c'|'d'}

    correct_count = 0
    results = []
    for q in questions:
        submitted = answers.get(str(q.id), '').lower().strip()
        is_correct = submitted == q.correct.lower()
        if is_correct:
            correct_count += 1
        results.append({
            'id': q.id,
            'submitted': submitted,
            'correct': q.correct,
            'is_correct': is_correct,
            'explanation': q.explanation or '',
        })

    score = round(correct_count / len(questions) * 100)
    passed = score >= PASS_THRESHOLD

    # Update progress record
    progress = ModuleProgress.query.filter_by(
        user_id=current_user.id, module_id=module_id
    ).first()
    if not progress:
        progress = ModuleProgress(user_id=current_user.id, module_id=module_id)
        db.session.add(progress)

    progress.quiz_score = score
    progress.quiz_attempts = (progress.quiz_attempts or 0) + 1
    if passed and progress.status != 'completed':
        progress.status = 'completed'
        progress.completed_at = datetime.utcnow()

    db.session.commit()

    return jsonify({
        'ok': True,
        'score': score,
        'passed': passed,
        'pass_threshold': PASS_THRESHOLD,
        'correct_count': correct_count,
        'total': len(questions),
        'results': results,
    })


@modules_bp.route('/<int:module_id>/complete', methods=['POST'])
@login_required
def complete_module(module_id):
    """Directly mark a module as completed (no quiz path, e.g. no questions exist)."""
    LearningModule.query.filter(
        LearningModule.id == module_id,
        LearningModule.category.in_(CATEGORY_META),
    ).first_or_404()
    progress = ModuleProgress.query.filter_by(
        user_id=current_user.id, module_id=module_id
    ).first()
    if not progress:
        progress = ModuleProgress(user_id=current_user.id, module_id=module_id)
        db.session.add(progress)
    progress.status = 'completed'
    progress.completed_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'ok': True})
