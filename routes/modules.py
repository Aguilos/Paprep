from io import BytesIO
from flask import (Blueprint, render_template, request, make_response,
                   send_file, abort, Response)
from flask_login import login_required, current_user
from models import LearningModule
from app import db

modules_bp = Blueprint('modules', __name__, url_prefix='/modules')

CATEGORY_META = {
    'parenting':     {'label': 'Parenting',    'icon': 'bi-people-fill',     'color': '#4E97D9'},
    'nutrition':     {'label': 'Nutrition',    'icon': 'bi-apple',           'color': '#5CAD5C'},
    'safety':        {'label': 'Safety',       'icon': 'bi-shield-check',    'color': '#FF8C42'},
    'health':        {'label': 'Child Health', 'icon': 'bi-heart-pulse-fill','color': '#E74C3C'},
    'special_needs': {'label': 'Special Needs','icon': 'bi-person-heart',    'color': '#9B59B6'},
}


# ── Public routes (all logged-in users) ─────────────────────────────────────

@modules_bp.route('/')
@login_required
def list_modules():
    has_sn = any(c.child_type == 'special_needs' for c in current_user.children)
    query = LearningModule.query
    if not has_sn:
        query = query.filter_by(is_special_needs=False)
    category = request.args.get('category', '')
    if category and category in CATEGORY_META:
        query = query.filter_by(category=category)
    modules = query.order_by(LearningModule.sort_order, LearningModule.id).all()
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
    if module.is_special_needs:
        has_sn = any(c.child_type == 'special_needs' for c in current_user.children)
        if not has_sn:
            abort(403)
    meta = CATEGORY_META.get(module.category, {})
    return render_template('modules/module_detail.html',
                           module=module,
                           meta=meta,
                           page_title=module.title)


@modules_bp.route('/<int:module_id>/pdf')
@login_required
def view_pdf(module_id):
    """Serve PDF stored in DB inline so users can read it in the browser."""
    module = LearningModule.query.get_or_404(module_id)
    if module.is_special_needs:
        has_sn = any(c.child_type == 'special_needs' for c in current_user.children)
        if not has_sn:
            abort(403)
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
    if module.is_special_needs:
        has_sn = any(c.child_type == 'special_needs' for c in current_user.children)
        if not has_sn:
            abort(403)
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


