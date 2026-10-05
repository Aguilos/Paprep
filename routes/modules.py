from io import BytesIO
from flask import Blueprint, render_template, request, make_response, jsonify, \
    send_file, abort, Response
from flask_login import login_required, current_user
from models import LearningModule, ModuleProgress, ModuleQuizQuestion
from app import db
from datetime import datetime

modules_bp = Blueprint('modules', __name__, url_prefix='/modules')

CATEGORY_META = {
    'parenting':     {'label': 'Parenting',    'icon': 'bi-people-fill',     'color': '#4E97D9'},
    'nutrition':     {'label': 'Nutrition',    'icon': 'bi-apple',           'color': '#5CAD5C'},
    'safety':        {'label': 'Safety',       'icon': 'bi-shield-check',    'color': '#FF8C42'},
    'health':        {'label': 'Child Health', 'icon': 'bi-heart-pulse-fill','color': '#E74C3C'},
}

PASS_THRESHOLD = 70   # minimum quiz score (%) to mark a module complete


# ── Public routes (all logged-in users) ─────────────────────────────────────

@modules_bp.route('/')
@login_required
def list_modules():
    query = LearningModule.query
    category = request.args.get('category', '')
    if category and category in CATEGORY_META:
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

    grouped = {}
    for m in modules:
        grouped.setdefault(m.category, []).append(m)

    return render_template('modules/modules.html',
                           modules=modules,
                           grouped=grouped,
                           category_meta=CATEGORY_META,
                           active_category=category,
                           page_title='Learning Modules')


@modules_bp.route('/<int:module_id>')
@login_required
def module_detail(module_id):
    module = LearningModule.query.get_or_404(module_id)
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
                           meta=meta,
                           progress=progress,
                           questions=questions,
                           questions_data=questions_data,
                           pass_threshold=PASS_THRESHOLD,
                           page_title=module.title)


@modules_bp.route('/<int:module_id>/pdf')
@login_required
def view_pdf(module_id):
    """Serve PDF stored in DB inline so users can read it in the browser."""
    module = LearningModule.query.get_or_404(module_id)
    if not module.pdf_data:
        abort(404)
    return Response(
        BytesIO(module.pdf_data),
        mimetype='application/pdf',
        headers={'Content-Disposition': 'inline'}
    )


@modules_bp.route('/<int:module_id>/download')
@login_required
def download_module(module_id):
    """Download the PDF from DB (or fall back to HTML)."""
    module = LearningModule.query.get_or_404(module_id)
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


@modules_bp.route('/assessment')
@login_required
def assessment():
    return render_template('modules/assessment.html', page_title='Preparedness Assessment')


# ── Interactive Progress API ─────────────────────────────────────────────────

@modules_bp.route('/<int:module_id>/progress', methods=['POST'])
@login_required
def save_progress(module_id):
    """Save the user's last-read section index (called client-side on nav)."""
    LearningModule.query.get_or_404(module_id)
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
    module = LearningModule.query.get_or_404(module_id)
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
    LearningModule.query.get_or_404(module_id)
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
