from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, PasswordField, SubmitField, SelectField, BooleanField
from wtforms.validators import DataRequired, Length, Email, EqualTo
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps
import pymysql
import re

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:root@localhost/afropeople_forum'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Custom Jinja2 filters
@app.template_filter('nl2br')
def nl2br_filter(text):
    """Convert newlines to HTML line breaks"""
    if text:
        return text.replace('\n', '<br>')
    return text

@app.template_filter('truncate_words')
def truncate_words_filter(text, length=150):
    """Truncate text to specified length"""
    if text and len(text) > length:
        return text[:length] + '...'
    return text

# Admin decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

# User loader callback
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    date_joined = db.Column(db.DateTime, default=datetime.utcnow)
    posts = db.relationship('Post', backref='author', lazy=True)
    comments = db.relationship('Comment', backref='author', lazy=True)
    likes = db.relationship('Like', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    posts = db.relationship('Post', backref='category', lazy=True)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    comments = db.relationship('Comment', backref='post', lazy=True, cascade='all, delete-orphan')
    likes = db.relationship('Like', backref='post', lazy=True, cascade='all, delete-orphan')

    def get_like_count(self):
        return len(self.likes)

    def is_liked_by(self, user):
        return Like.query.filter_by(user_id=user.id, post_id=self.id).first() is not None

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    date_liked = db.Column(db.DateTime, default=datetime.utcnow)

class AdSense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    publisher_id = db.Column(db.String(50))  # Google AdSense Publisher ID
    header_ad_code = db.Column(db.Text)  # Ad code for header
    sidebar_ad_code = db.Column(db.Text)  # Ad code for sidebar
    footer_ad_code = db.Column(db.Text)  # Ad code for footer
    post_content_ad_code = db.Column(db.Text)  # Ad code for within post content
    is_enabled = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Forms
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=20)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    password2 = PasswordField('Confirm Password', 
                              validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

class PostForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(max=200)])
    content = TextAreaField('Content', validators=[DataRequired()])
    submit = SubmitField('Create Post')

class CommentForm(FlaskForm):
    content = TextAreaField('Comment', validators=[DataRequired()])
    submit = SubmitField('Add Comment')

class CategoryForm(FlaskForm):
    name = StringField('Category Name', validators=[DataRequired(), Length(max=80)])
    description = TextAreaField('Description')
    submit = SubmitField('Save Category')

class EditUserForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=20)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    is_admin = BooleanField('Admin User')
    is_active = BooleanField('Active User')
    submit = SubmitField('Update User')

class AdSenseForm(FlaskForm):
    publisher_id = StringField('Publisher ID (ca-pub-xxxxxxxxx)', validators=[Length(max=50)])
    header_ad_code = TextAreaField('Header Ad Code')
    sidebar_ad_code = TextAreaField('Sidebar Ad Code')
    footer_ad_code = TextAreaField('Footer Ad Code')
    post_content_ad_code = TextAreaField('Post Content Ad Code')
    is_enabled = BooleanField('Enable AdSense')
    submit = SubmitField('Save AdSense Settings')

# Routes
@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    posts = Post.query.filter_by(is_active=True).order_by(Post.date_posted.desc()).paginate(
        page=page, per_page=10, error_out=False)
    categories = Category.query.filter_by(is_active=True).all()
    return render_template('index.html', posts=posts, categories=categories)

@app.route('/category/<int:category_id>')
def category(category_id):
    page = request.args.get('page', 1, type=int)
    category = Category.query.get_or_404(category_id)
    posts = Post.query.filter_by(category_id=category_id, is_active=True).order_by(Post.date_posted.desc()).paginate(
        page=page, per_page=10, error_out=False)
    categories = Category.query.filter_by(is_active=True).all()
    return render_template('category.html', posts=posts, category=category, categories=categories)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data) and user.is_active:
            login_user(user)
            flash('Login successful!', 'success')
            # Redirect to admin dashboard if user is admin
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'danger')
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = RegisterForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/create_post', methods=['GET', 'POST'])
@login_required
def create_post():
    form = PostForm()
    categories = Category.query.filter_by(is_active=True).all()
    
    if form.validate_on_submit():
        category_id = request.form.get('category')
        post = Post(title=form.title.data, content=form.content.data,
                   author=current_user, category_id=category_id)
        db.session.add(post)
        db.session.commit()
        flash('Your post has been created!', 'success')
        return redirect(url_for('index'))
    
    return render_template('create_post.html', form=form, categories=categories)

@app.route('/post/<int:post_id>')
def post_detail(post_id):
    post = Post.query.filter_by(id=post_id, is_active=True).first_or_404()
    form = CommentForm()
    return render_template('post_detail.html', post=post, form=form)

@app.route('/add_comment/<int:post_id>', methods=['POST'])
@login_required
def add_comment(post_id):
    form = CommentForm()
    if form.validate_on_submit():
        comment = Comment(content=form.content.data, author=current_user, post_id=post_id)
        db.session.add(comment)
        db.session.commit()
        flash('Your comment has been added!', 'success')
    return redirect(url_for('post_detail', post_id=post_id))

@app.route('/like_post/<int:post_id>')
@login_required
def like_post(post_id):
    post = Post.query.get_or_404(post_id)
    like = Like.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    
    if like:
        db.session.delete(like)
        db.session.commit()
        flash('Post unliked!', 'info')
    else:
        like = Like(user_id=current_user.id, post_id=post_id)
        db.session.add(like)
        db.session.commit()
        flash('Post liked!', 'success')
    
    return redirect(url_for('post_detail', post_id=post_id))

# Admin Routes
@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    # Statistics
    total_users = User.query.count()
    total_posts = Post.query.count()
    total_comments = Comment.query.count()
    total_categories = Category.query.count()
    
    # Recent activities
    recent_users = User.query.order_by(User.date_joined.desc()).limit(5).all()
    recent_posts = Post.query.order_by(Post.date_posted.desc()).limit(5).all()
    
    return render_template('admin/dashboard.html', 
                         total_users=total_users,
                         total_posts=total_posts,
                         total_comments=total_comments,
                         total_categories=total_categories,
                         recent_users=recent_users,
                         recent_posts=recent_posts)

@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    page = request.args.get('page', 1, type=int)
    users = User.query.paginate(page=page, per_page=20, error_out=False)
    return render_template('admin/users.html', users=users)

@app.route('/admin/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_user(user_id):
    user = User.query.get_or_404(user_id)
    form = EditUserForm(obj=user)
    
    if form.validate_on_submit():
        user.username = form.username.data
        user.email = form.email.data
        user.is_admin = form.is_admin.data
        user.is_active = form.is_active.data
        db.session.commit()
        flash(f'User {user.username} updated successfully!', 'success')
        return redirect(url_for('admin_users'))
    
    return render_template('admin/edit_user.html', form=form, user=user)

@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot delete your own account!', 'danger')
        return redirect(url_for('admin_users'))
    
    db.session.delete(user)
    db.session.commit()
    flash(f'User {user.username} deleted successfully!', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/posts')
@login_required
@admin_required
def admin_posts():
    page = request.args.get('page', 1, type=int)
    posts = Post.query.order_by(Post.date_posted.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template('admin/posts.html', posts=posts)

@app.route('/admin/posts/<int:post_id>/toggle', methods=['POST'])
@login_required
@admin_required
def admin_toggle_post(post_id):
    post = Post.query.get_or_404(post_id)
    post.is_active = not post.is_active
    db.session.commit()
    status = "activated" if post.is_active else "deactivated"
    flash(f'Post "{post.title}" {status} successfully!', 'success')
    return redirect(url_for('admin_posts'))

@app.route('/admin/posts/<int:post_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    flash(f'Post "{post.title}" deleted successfully!', 'success')
    return redirect(url_for('admin_posts'))

@app.route('/admin/categories')
@login_required
@admin_required
def admin_categories():
    categories = Category.query.all()
    return render_template('admin/categories.html', categories=categories)

@app.route('/admin/categories/add', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_add_category():
    form = CategoryForm()
    if form.validate_on_submit():
        category = Category(name=form.name.data, description=form.description.data)
        db.session.add(category)
        db.session.commit()
        flash(f'Category "{category.name}" added successfully!', 'success')
        return redirect(url_for('admin_categories'))
    return render_template('admin/add_category.html', form=form)

@app.route('/admin/categories/<int:category_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_category(category_id):
    category = Category.query.get_or_404(category_id)
    form = CategoryForm(obj=category)
    
    if form.validate_on_submit():
        category.name = form.name.data
        category.description = form.description.data
        db.session.commit()
        flash(f'Category "{category.name}" updated successfully!', 'success')
        return redirect(url_for('admin_categories'))
    
    return render_template('admin/edit_category.html', form=form, category=category)

@app.route('/admin/categories/<int:category_id>/toggle', methods=['POST'])
@login_required
@admin_required
def admin_toggle_category(category_id):
    category = Category.query.get_or_404(category_id)
    category.is_active = not category.is_active
    db.session.commit()
    status = "activated" if category.is_active else "deactivated"
    flash(f'Category "{category.name}" {status} successfully!', 'success')
    return redirect(url_for('admin_categories'))

@app.route('/admin/comments')
@login_required
@admin_required
def admin_comments():
    page = request.args.get('page', 1, type=int)
    comments = Comment.query.order_by(Comment.date_posted.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template('admin/comments.html', comments=comments)

@app.route('/admin/comments/<int:comment_id>/toggle', methods=['POST'])
@login_required
@admin_required
def admin_toggle_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    comment.is_active = not comment.is_active
    db.session.commit()
    status = "activated" if comment.is_active else "deactivated"
    flash(f'Comment {status} successfully!', 'success')
    return redirect(url_for('admin_comments'))

@app.route('/admin/comments/<int:comment_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    db.session.delete(comment)
    db.session.commit()
    flash('Comment deleted successfully!', 'success')
    return redirect(url_for('admin_comments'))

@app.route('/admin/adsense', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_adsense():
    # Get existing AdSense settings or create new one
    adsense = AdSense.query.first()
    if not adsense:
        adsense = AdSense()
    
    form = AdSenseForm(obj=adsense)
    
    if form.validate_on_submit():
        adsense.publisher_id = form.publisher_id.data
        adsense.header_ad_code = form.header_ad_code.data
        adsense.sidebar_ad_code = form.sidebar_ad_code.data
        adsense.footer_ad_code = form.footer_ad_code.data
        adsense.post_content_ad_code = form.post_content_ad_code.data
        adsense.is_enabled = form.is_enabled.data
        adsense.updated_at = datetime.utcnow()
        
        if adsense.id is None:  # New record
            db.session.add(adsense)
        
        db.session.commit()
        flash('AdSense settings saved successfully!', 'success')
        return redirect(url_for('admin_adsense'))
    
    return render_template('admin/adsense.html', form=form, adsense=adsense)

# Template context processor to make AdSense available in all templates
@app.context_processor
def inject_adsense():
    adsense = AdSense.query.first()
    return dict(adsense=adsense)

def init_db():
    """Initialize the database with default categories and admin user"""
    db.create_all()
    
    # Create admin user if it doesn't exist
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(username='admin', email='admin@afropeople.com', is_admin=True)
        admin.set_password('admin123')  # Change this password!
        db.session.add(admin)
        print("Admin user created! Username: admin, Password: admin123")
    
    # Create default categories if they don't exist
    if not Category.query.first():
        categories = [
            Category(name='General Discussion', description='General topics and discussions'),
            Category(name='Culture & Heritage', description='African culture, traditions, and heritage'),
            Category(name='Business & Finance', description='Business opportunities and financial discussions'),
            Category(name='Education', description='Educational topics and academic discussions'),
            Category(name='Politics', description='Political discussions and current affairs'),
            Category(name='Entertainment', description='Music, movies, and entertainment'),
            Category(name='Technology', description='Tech discussions and innovations'),
            Category(name='Health & Wellness', description='Health tips and wellness discussions')
        ]
        
        for category in categories:
            db.session.add(category)
        
        db.session.commit()
        print("Database initialized with default categories!")

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True) 