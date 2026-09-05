from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from flask_login import login_required, current_user
from app import db
from models import ForumPost, ForumReply

forum_bp = Blueprint('forum', __name__, url_prefix='/forum')

FORUM_CATEGORIES = {
    'general':      {'label': 'General',        'icon': 'bi-chat-dots-fill',      'color': '#4E97D9'},
    'parenting':    {'label': 'Parenting Tips',  'icon': 'bi-people-fill',          'color': '#9B59B6'},
    'nutrition':    {'label': 'Nutrition',       'icon': 'bi-apple',               'color': '#5CAD5C'},
    'health':       {'label': 'Child Health',    'icon': 'bi-heart-pulse-fill',    'color': '#E74C3C'},
    'safety':       {'label': 'Safety',          'icon': 'bi-shield-check',        'color': '#FF8C42'},
    'special_needs':{'label': 'Special Needs',   'icon': 'bi-person-heart',        'color': '#8E44AD'},
}


@forum_bp.route('/')
@login_required
def forum_home():
    """List all forum posts, filterable by category."""
    category = request.args.get('category', '')
    query = ForumPost.query
    if category and category in FORUM_CATEGORIES:
        query = query.filter_by(category=category)
    # Pinned posts first, then newest
    posts = query.order_by(
        ForumPost.is_pinned.desc(),
        ForumPost.created_at.desc()
    ).all()
    return render_template(
        'forum/forum_home.html',
        posts=posts,
        categories=FORUM_CATEGORIES,
        active_category=category,
        page_title='Parent Forum'
    )


@forum_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_post():
    """Create a new forum post."""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        body = request.form.get('body', '').strip()
        category = request.form.get('category', 'general')
        if not title or not body:
            flash('Title and message body are required.', 'error')
            return redirect(url_for('forum.new_post'))
        if category not in FORUM_CATEGORIES:
            category = 'general'
        post = ForumPost(
            user_id=current_user.id,
            title=title,
            body=body,
            category=category
        )
        db.session.add(post)
        db.session.commit()
        flash('Your post has been published!', 'success')
        return redirect(url_for('forum.post_detail', post_id=post.id))
    return render_template(
        'forum/new_post.html',
        categories=FORUM_CATEGORIES,
        page_title='New Discussion'
    )


@forum_bp.route('/<int:post_id>')
@login_required
def post_detail(post_id):
    """View a single forum post and its replies."""
    post = ForumPost.query.get_or_404(post_id)
    return render_template(
        'forum/post_detail.html',
        post=post,
        categories=FORUM_CATEGORIES,
        page_title=post.title
    )


@forum_bp.route('/<int:post_id>/reply', methods=['POST'])
@login_required
def reply(post_id):
    """Submit a reply to a forum post."""
    post = ForumPost.query.get_or_404(post_id)
    body = request.form.get('body', '').strip()
    if not body:
        flash('Reply cannot be empty.', 'error')
        return redirect(url_for('forum.post_detail', post_id=post_id))
    reply_obj = ForumReply(
        post_id=post.id,
        user_id=current_user.id,
        body=body
    )
    db.session.add(reply_obj)
    db.session.commit()
    flash('Reply posted!', 'success')
    return redirect(url_for('forum.post_detail', post_id=post_id) + '#replies')


@forum_bp.route('/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    """Delete own forum post."""
    post = ForumPost.query.get_or_404(post_id)
    if post.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    db.session.delete(post)
    db.session.commit()
    flash('Post deleted.', 'success')
    return redirect(url_for('forum.forum_home'))
