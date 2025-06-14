from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, PasswordField, SubmitField, SelectField, BooleanField, DateField, DateTimeLocalField
from wtforms.validators import DataRequired, Length, Email, EqualTo, Optional, URL
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from functools import wraps
import pymysql
import re
import os
from PIL import Image
import secrets

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:root@localhost/afropeople_forum'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

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

def moderator_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_moderator:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def admin_or_moderator_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.can_moderate():
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def should_display_ads(adsense):
    """Determine if ads should be displayed based on user status and settings"""
    if not adsense or not adsense.is_enabled:
        return False
    
    if adsense.ad_frequency == 'always':
        return True
    elif adsense.ad_frequency == 'logged_out':
        return not current_user.is_authenticated
    elif adsense.ad_frequency == 'members':
        return current_user.is_authenticated
    
    return True

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
    is_moderator = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    date_joined = db.Column(db.DateTime, default=datetime.utcnow)
    profile_image = db.Column(db.String(255), default='default.jpg')
    bio = db.Column(db.Text)
    location = db.Column(db.String(100))
    website = db.Column(db.String(200))
    twitter_handle = db.Column(db.String(50))
    linkedin_url = db.Column(db.String(200))
    github_url = db.Column(db.String(200))
    birth_date = db.Column(db.Date)
    occupation = db.Column(db.String(100))
    interests = db.Column(db.Text)
    profile_updated_at = db.Column(db.DateTime)
    posts = db.relationship('Post', backref='author', lazy=True)
    comments = db.relationship('Comment', backref='author', lazy=True)
    likes = db.relationship('Like', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def can_moderate(self):
        """Check if user can moderate (admin or moderator)"""
        return self.is_admin or self.is_moderator
    
    def get_role_display(self):
        """Get user role for display purposes"""
        if self.is_admin:
            return "Administrator"
        elif self.is_moderator:
            return "Moderator"
        else:
            return "Member"

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    posts = db.relationship('Post', backref='category', lazy=True)

    @staticmethod
    def generate_slug(name):
        """Generate a URL-friendly slug from the category name"""
        # Convert to lowercase and replace spaces with hyphens
        slug = re.sub(r'[^\w\s-]', '', name.lower())
        slug = re.sub(r'[-\s]+', '-', slug)
        slug = slug.strip('-')
        
        # Ensure slug is not empty
        if not slug:
            slug = 'category'
        
        # Check if slug already exists and make it unique
        existing_category = Category.query.filter_by(slug=slug).first()
        if existing_category:
            counter = 1
            while Category.query.filter_by(slug=f"{slug}-{counter}").first():
                counter += 1
            slug = f"{slug}-{counter}"
        
        return slug

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(250), unique=True, nullable=False)
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

    @staticmethod
    def generate_slug(title):
        """Generate a URL-friendly slug from the title"""
        # Convert to lowercase and replace spaces with hyphens
        slug = re.sub(r'[^\w\s-]', '', title.lower())
        slug = re.sub(r'[-\s]+', '-', slug)
        slug = slug.strip('-')
        
        # Ensure slug is not empty
        if not slug:
            slug = 'post'
        
        # Check if slug already exists and make it unique
        existing_post = Post.query.filter_by(slug=slug).first()
        if existing_post:
            counter = 1
            while Post.query.filter_by(slug=f"{slug}-{counter}").first():
                counter += 1
            slug = f"{slug}-{counter}"
        
        return slug

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=True)
    replies = db.relationship('Comment', backref=db.backref('parent', remote_side=[id]), lazy=True)
    helpful_votes = db.relationship('CommentHelpful', backref='comment', lazy=True, cascade='all, delete-orphan')

    def get_helpful_count(self):
        return len(self.helpful_votes)

    def is_helpful_by(self, user):
        return CommentHelpful.query.filter_by(user_id=user.id, comment_id=self.id).first() is not None

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    date_liked = db.Column(db.DateTime, default=datetime.utcnow)

class CommentHelpful(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    comment_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=False)
    date_voted = db.Column(db.DateTime, default=datetime.utcnow)

class AdSense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    publisher_id = db.Column(db.String(50))
    header_ad_code = db.Column(db.Text)
    sidebar_ad_code = db.Column(db.Text)
    footer_ad_code = db.Column(db.Text)
    post_content_ad_code = db.Column(db.Text)
    category_ad_code = db.Column(db.Text)
    profile_ad_code = db.Column(db.Text)
    is_enabled = db.Column(db.Boolean, default=False)
    auto_ads_enabled = db.Column(db.Boolean, default=False)
    ad_frequency = db.Column(db.String(20), default='always')
    responsive_ads = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Advertisement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    image_url = db.Column(db.String(500))  # For external URLs
    image_file = db.Column(db.String(255))  # For uploaded images
    link_url = db.Column(db.String(500))
    ad_type = db.Column(db.String(50), default='banner')  # banner, sidebar, popup, text
    placement = db.Column(db.String(50), default='sidebar')  # sidebar, header, footer, content
    target_audience = db.Column(db.String(50), default='all')  # all, members, guests
    priority = db.Column(db.Integer, default=1)  # 1-10, higher = more priority
    is_active = db.Column(db.Boolean, default=True)
    click_count = db.Column(db.Integer, default=0)
    impression_count = db.Column(db.Integer, default=0)
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    end_date = db.Column(db.DateTime)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    creator = db.relationship('User', backref='created_ads', lazy=True)
    
    def get_image_url(self):
        """Get the appropriate image URL (uploaded file or external URL)"""
        if self.image_file:
            return url_for('static', filename=f'uploads/ads/{self.image_file}')
        elif self.image_url:
            return self.image_url
        return None
    
    def is_expired(self):
        """Check if advertisement has expired"""
        if self.end_date:
            return datetime.utcnow() > self.end_date
        return False
    
    def get_ctr(self):
        """Calculate click-through rate"""
        if self.impression_count > 0:
            return round((self.click_count / self.impression_count) * 100, 2)
        return 0.0
    
    def should_display_to_user(self, user=None):
        """Check if ad should be displayed to the current user"""
        if not self.is_active or self.is_expired():
            return False
        
        if self.target_audience == 'all':
            return True
        elif self.target_audience == 'members':
            return user and user.is_authenticated
        elif self.target_audience == 'guests':
            return not (user and user.is_authenticated)
        
        return True

class AdClick(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ad_id = db.Column(db.Integer, db.ForeignKey('advertisement.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))
    clicked_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    advertisement = db.relationship('Advertisement', backref='clicks', lazy=True)
    user = db.relationship('User', backref='ad_clicks', lazy=True)

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
    is_moderator = BooleanField('Moderator User')
    is_active = BooleanField('Active User')
    submit = SubmitField('Update User')

class AdSenseForm(FlaskForm):
    publisher_id = StringField('Publisher ID (ca-pub-xxxxxxxxx)', validators=[Length(max=50)])
    header_ad_code = TextAreaField('Header Ad Code')
    sidebar_ad_code = TextAreaField('Sidebar Ad Code')
    footer_ad_code = TextAreaField('Footer Ad Code')
    post_content_ad_code = TextAreaField('Post Content Ad Code')
    category_ad_code = TextAreaField('Category Page Ad Code')
    profile_ad_code = TextAreaField('Profile Page Ad Code')
    is_enabled = BooleanField('Enable AdSense')
    auto_ads_enabled = BooleanField('Enable Auto Ads')
    ad_frequency = SelectField('Ad Display Frequency', 
                              choices=[('always', 'Show Always'), 
                                     ('logged_out', 'Show Only to Logged Out Users'),
                                     ('members', 'Show Only to Members')],
                              default='always')
    responsive_ads = BooleanField('Use Responsive Ad Units', default=True)
    submit = SubmitField('Save AdSense Settings')

class AdvertisementForm(FlaskForm):
    title = StringField('Advertisement Title', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description', validators=[Length(max=500)])
    image_file = FileField('Upload Image', validators=[FileAllowed(['jpg', 'png', 'jpeg', 'gif'], 'Images only!')])
    image_url = StringField('Or Image URL', validators=[Optional(), URL(), Length(max=500)])
    link_url = StringField('Link URL', validators=[Optional(), URL(), Length(max=500)])
    ad_type = SelectField('Advertisement Type', 
                         choices=[('banner', 'Banner Ad'), 
                                ('text', 'Text Ad'),
                                ('image', 'Image Ad'),
                                ('video', 'Video Ad')],
                         default='banner')
    placement = SelectField('Placement Location', 
                           choices=[('sidebar', 'Right Sidebar - 300x250px (Medium Rectangle)'), 
                                  ('left_sidebar', 'Left Sidebar - 300x250px (Medium Rectangle)'),
                                  ('header', 'Header - 728x90px (Leaderboard)'),
                                  ('footer', 'Footer - 728x90px (Leaderboard)'),
                                  ('content', 'Content Area - 336x280px (Large Rectangle)'),
                                  ('popup', 'Popup - 300x300px (Square)')],
                           default='sidebar')
    target_audience = SelectField('Target Audience', 
                                 choices=[('all', 'All Users'), 
                                        ('members', 'Members Only'),
                                        ('guests', 'Guests Only')],
                                 default='all')
    priority = SelectField('Priority Level', 
                          choices=[(str(i), f'Priority {i}') for i in range(1, 11)],
                          default='5')
    start_date = DateTimeLocalField('Start Date', validators=[Optional()])
    end_date = DateTimeLocalField('End Date', validators=[Optional()])
    is_active = BooleanField('Active', default=True)
    submit = SubmitField('Save Advertisement')

class ProfileForm(FlaskForm):
    username = StringField('Username', validators=[Length(min=4, max=20)])
    email = StringField('Email')
    bio = TextAreaField('Bio', validators=[Length(max=500)])
    location = StringField('Location', validators=[Length(max=100)])
    website = StringField('Website', validators=[Optional(), URL(), Length(max=200)])
    twitter_handle = StringField('Twitter Handle', validators=[Length(max=50)])
    linkedin_url = StringField('LinkedIn URL', validators=[Optional(), URL(), Length(max=200)])
    github_url = StringField('GitHub URL', validators=[Optional(), URL(), Length(max=200)])
    birth_date = DateField('Birth Date', validators=[Optional()])
    occupation = StringField('Occupation', validators=[Length(max=100)])
    interests = TextAreaField('Interests', validators=[Length(max=300)])
    profile_image = FileField('Profile Picture', validators=[FileAllowed(['jpg', 'png', 'jpeg'], 'Images only!')])
    submit = SubmitField('Update Profile')

# Helper Functions
def save_profile_picture(form_picture):
    """Save and resize profile picture"""
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.root_path, 'static/uploads/profile_pics', picture_fn)
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(picture_path), exist_ok=True)
    
    # Resize image
    output_size = (300, 300)
    img = Image.open(form_picture)
    
    # Convert to RGB if necessary (for PNG with transparency)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    
    # Create a square crop
    width, height = img.size
    min_dimension = min(width, height)
    left = (width - min_dimension) // 2
    top = (height - min_dimension) // 2
    right = left + min_dimension
    bottom = top + min_dimension
    
    img = img.crop((left, top, right, bottom))
    img.thumbnail(output_size)
    img.save(picture_path)
    
    return picture_fn

def save_advertisement_image(form_picture):
    """Save and resize advertisement image"""
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.root_path, 'static/uploads/ads', picture_fn)
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(picture_path), exist_ok=True)
    
    # Resize image based on common ad sizes
    img = Image.open(form_picture)
    
    # Convert to RGB if necessary (for PNG with transparency)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    
    # Don't resize, keep original dimensions for flexibility
    # Admin can upload images in the correct sizes
    img.save(picture_path, quality=95)
    
    return picture_fn

# Routes
@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    posts = Post.query.filter_by(is_active=True).order_by(Post.date_posted.desc()).paginate(
        page=page, per_page=10, error_out=False)
    categories = Category.query.filter_by(is_active=True).all()
    
    # Get user's liked posts if authenticated
    user_likes = []
    if current_user.is_authenticated:
        user_likes = [like.post_id for like in current_user.likes]
    
    return render_template('index.html', posts=posts, categories=categories, user_likes=user_likes)

@app.route('/category/<slug>')
def category(slug):
    page = request.args.get('page', 1, type=int)
    category = Category.query.filter_by(slug=slug, is_active=True).first_or_404()
    posts = Post.query.filter_by(category_id=category.id, is_active=True).order_by(Post.date_posted.desc()).paginate(
        page=page, per_page=10, error_out=False)
    categories = Category.query.filter_by(is_active=True).all()
    
    # Get user's liked posts if authenticated
    user_likes = []
    if current_user.is_authenticated:
        user_likes = [like.post_id for like in current_user.likes]
    
    # Calculate category statistics for all posts in category
    all_posts_in_category = Post.query.filter_by(category_id=category.id, is_active=True).all()
    total_comments = sum(len(post.comments) for post in all_posts_in_category)
    total_likes = sum(post.get_like_count() for post in all_posts_in_category)
    
    return render_template('category.html', posts=posts, category=category, categories=categories, 
                         user_likes=user_likes, total_comments=total_comments, total_likes=total_likes)

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
            if user.can_moderate():  # Redirect both admins and moderators
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
        # Generate slug from title
        slug = Post.generate_slug(form.title.data)
        
        post = Post(
            title=form.title.data,
            slug=slug,
            content=form.content.data,
            author=current_user,
            category_id=request.form.get('category_id')
        )
        db.session.add(post)
        db.session.commit()
        flash('Your post has been created!', 'success')
        return redirect(url_for('post_detail', slug=post.slug))
    
    return render_template('create_post.html', form=form, categories=categories)

@app.route('/post/<slug>')
def post_detail(slug):
    post = Post.query.filter_by(slug=slug, is_active=True).first_or_404()
    form = CommentForm()
    
    # Get user's helpful votes if authenticated
    user_helpful_votes = []
    if current_user.is_authenticated:
        user_helpful_votes = [vote.comment_id for vote in CommentHelpful.query.filter_by(user_id=current_user.id).all()]
    
    # Get only top-level comments (no parent_id) and their replies
    top_level_comments = Comment.query.filter_by(post_id=post.id, parent_id=None, is_active=True).order_by(Comment.date_posted.asc()).all()
    
    return render_template('post_detail.html', post=post, form=form, 
                         user_helpful_votes=user_helpful_votes, 
                         top_level_comments=top_level_comments)

@app.route('/add_comment/<slug>', methods=['POST'])
@login_required
def add_comment(slug):
    post = Post.query.filter_by(slug=slug, is_active=True).first_or_404()
    form = CommentForm()
    if form.validate_on_submit():
        comment = Comment(content=form.content.data, author=current_user, post_id=post.id)
        db.session.add(comment)
        db.session.commit()
        flash('Your comment has been added!', 'success')
    return redirect(url_for('post_detail', slug=slug))

@app.route('/like_post/<int:post_id>', methods=['POST'])
@login_required
def like_post(post_id):
    post = Post.query.get_or_404(post_id)
    existing_like = Like.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    
    if existing_like:
        # Unlike the post
        db.session.delete(existing_like)
        flash('Post unliked!', 'info')
    else:
        # Like the post
        like = Like(user_id=current_user.id, post_id=post_id)
        db.session.add(like)
        flash('Post liked!', 'success')
    
    db.session.commit()
    return redirect(request.referrer or url_for('index'))

@app.route('/helpful_comment/<int:comment_id>', methods=['POST'])
@login_required
def helpful_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    existing_vote = CommentHelpful.query.filter_by(user_id=current_user.id, comment_id=comment_id).first()
    
    if existing_vote:
        # Remove helpful vote
        db.session.delete(existing_vote)
        flash('Helpful vote removed!', 'info')
    else:
        # Add helpful vote
        vote = CommentHelpful(user_id=current_user.id, comment_id=comment_id)
        db.session.add(vote)
        flash('Comment marked as helpful!', 'success')
    
    db.session.commit()
    return redirect(request.referrer or url_for('post_detail', slug=comment.post.slug))

@app.route('/reply_comment/<int:comment_id>', methods=['POST'])
@login_required
def reply_comment(comment_id):
    parent_comment = Comment.query.get_or_404(comment_id)
    content = request.form.get('content')
    
    if not content or not content.strip():
        flash('Reply content cannot be empty!', 'danger')
        return redirect(request.referrer or url_for('post_detail', slug=parent_comment.post.slug))
    
    reply = Comment(
        content=content.strip(),
        user_id=current_user.id,
        post_id=parent_comment.post_id,
        parent_id=comment_id
    )
    
    db.session.add(reply)
    db.session.commit()
    flash('Reply added successfully!', 'success')
    return redirect(request.referrer or url_for('post_detail', slug=parent_comment.post.slug))

# Profile Routes
@app.route('/profile')
@app.route('/profile/<username>')
def profile(username=None):
    if username is None:
        if current_user.is_authenticated:
            user = current_user
        else:
            flash('Please log in to view your profile.', 'info')
            return redirect(url_for('login'))
    else:
        user = User.query.filter_by(username=username).first_or_404()
    
    posts = Post.query.filter_by(user_id=user.id, is_active=True).order_by(Post.date_posted.desc()).limit(5).all()
    comments = Comment.query.filter_by(user_id=user.id, is_active=True).order_by(Comment.date_posted.desc()).limit(5).all()
    
    total_posts = Post.query.filter_by(user_id=user.id, is_active=True).count()
    total_comments = Comment.query.filter_by(user_id=user.id, is_active=True).count()
    total_likes = Like.query.join(Post).filter(Post.user_id == user.id).count()
    
    return render_template('profile.html', user=user, posts=posts, comments=comments,
                         total_posts=total_posts, total_comments=total_comments, total_likes=total_likes)

@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = ProfileForm()
    
    if form.validate_on_submit():
        if form.profile_image.data:
            try:
                picture_file = save_profile_picture(form.profile_image.data)
                current_user.profile_image = picture_file
            except Exception as e:
                flash('Error uploading image. Please try again.', 'danger')
                return render_template('edit_profile.html', form=form)
        
        current_user.username = form.username.data
        current_user.email = form.email.data
        current_user.bio = form.bio.data
        current_user.location = form.location.data
        current_user.website = form.website.data
        current_user.twitter_handle = form.twitter_handle.data
        current_user.linkedin_url = form.linkedin_url.data
        current_user.github_url = form.github_url.data
        current_user.birth_date = form.birth_date.data
        current_user.occupation = form.occupation.data
        current_user.interests = form.interests.data
        current_user.profile_updated_at = datetime.utcnow()
        
        db.session.commit()
        flash('Your profile has been updated!', 'success')
        return redirect(url_for('profile'))
    
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
        form.bio.data = current_user.bio
        form.location.data = current_user.location
        form.website.data = current_user.website
        form.twitter_handle.data = current_user.twitter_handle
        form.linkedin_url.data = current_user.linkedin_url
        form.github_url.data = current_user.github_url
        form.birth_date.data = current_user.birth_date
        form.occupation.data = current_user.occupation
        form.interests.data = current_user.interests
    
    return render_template('edit_profile.html', form=form)

# Admin Routes
@app.route('/admin')
@login_required
@admin_or_moderator_required
def admin_dashboard():
    try:
        # Basic counts with error handling
        total_users = User.query.count() or 0
        total_posts = Post.query.count() or 0
        total_comments = Comment.query.count() or 0
        total_categories = Category.query.count() or 0
        
        # Recent data with error handling
        recent_posts = Post.query.order_by(Post.date_posted.desc()).limit(5).all() or []
        recent_users = User.query.order_by(User.date_joined.desc()).limit(5).all() or []
        
        # Weekly statistics with error handling
        week_ago = datetime.utcnow() - timedelta(days=7)
        posts_this_week = Post.query.filter(Post.date_posted >= week_ago).count() or 0
        comments_this_week = Comment.query.filter(Comment.date_posted >= week_ago).count() or 0
        new_users_this_week = User.query.filter(User.date_joined >= week_ago).count() or 0
        
        # Advertisement statistics with error handling
        active_ads_count = Advertisement.query.filter_by(is_active=True).count() or 0
        
        # Categories with post counts
        categories = Category.query.all() or []
        
        # AdSense status
        adsense = AdSense.query.first()
        
        return render_template('admin/dashboard.html', 
                             total_users=total_users, 
                             total_posts=total_posts,
                             total_comments=total_comments, 
                             total_categories=total_categories,
                             recent_posts=recent_posts, 
                             recent_users=recent_users,
                             posts_this_week=posts_this_week,
                             comments_this_week=comments_this_week,
                             new_users_this_week=new_users_this_week,
                             active_ads_count=active_ads_count,
                             categories=categories,
                             adsense=adsense)
    except Exception as e:
        # Log the error and provide fallback data
        print(f"Dashboard error: {e}")
        flash('Dashboard data may be incomplete due to a system error.', 'warning')
        return render_template('admin/dashboard.html', 
                             total_users=0, 
                             total_posts=0,
                             total_comments=0, 
                             total_categories=0,
                             recent_posts=[], 
                             recent_users=[],
                             posts_this_week=0,
                             comments_this_week=0,
                             new_users_this_week=0,
                             active_ads_count=0,
                             categories=[],
                             adsense=None)

@app.route('/admin/users')
@login_required
@admin_or_moderator_required
def admin_users():
    page = request.args.get('page', 1, type=int)
    users = User.query.order_by(User.date_joined.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template('admin/users.html', users=users)

@app.route('/admin/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_or_moderator_required
def admin_edit_user(user_id):
    user = User.query.get_or_404(user_id)
    form = EditUserForm()
    
    if form.validate_on_submit():
        user.username = form.username.data
        user.email = form.email.data
        user.is_admin = form.is_admin.data
        user.is_moderator = form.is_moderator.data
        user.is_active = form.is_active.data
        db.session.commit()
        flash('User updated successfully!', 'success')
        return redirect(url_for('admin_users'))
    
    elif request.method == 'GET':
        form.username.data = user.username
        form.email.data = user.email
        form.is_admin.data = user.is_admin
        form.is_moderator.data = user.is_moderator
        form.is_active.data = user.is_active
    
    return render_template('admin/edit_user.html', form=form, user=user)

@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_or_moderator_required
def admin_delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot delete your own account!', 'danger')
        return redirect(url_for('admin_users'))
    
    db.session.delete(user)
    db.session.commit()
    flash('User deleted successfully!', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/<int:user_id>/toggle_moderator', methods=['POST'])
@login_required
@admin_required
def admin_toggle_moderator(user_id):
    """Toggle moderator status for a user"""
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot change your own moderator status!', 'danger')
        return redirect(request.referrer or url_for('admin_users'))
    
    user.is_moderator = not user.is_moderator
    db.session.commit()
    
    status = 'promoted to moderator' if user.is_moderator else 'removed from moderator role'
    flash(f'User {user.username} has been {status}!', 'success')
    return redirect(request.referrer or url_for('admin_users'))

@app.route('/admin/posts')
@login_required
@admin_or_moderator_required
def admin_posts():
    page = request.args.get('page', 1, type=int)
    posts = Post.query.order_by(Post.date_posted.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template('admin/posts.html', posts=posts)

@app.route('/admin/posts/<int:post_id>/toggle', methods=['POST'])
@login_required
@admin_or_moderator_required
def admin_toggle_post(post_id):
    post = Post.query.get_or_404(post_id)
    post.is_active = not post.is_active
    db.session.commit()
    status = 'activated' if post.is_active else 'deactivated'
    flash(f'Post {status} successfully!', 'success')
    return redirect(url_for('admin_posts'))

@app.route('/admin/posts/<int:post_id>/delete', methods=['POST'])
@login_required
@admin_or_moderator_required
def admin_delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    flash('Post deleted successfully!', 'success')
    return redirect(url_for('admin_posts'))

@app.route('/admin/categories')
@login_required
@admin_or_moderator_required
def admin_categories():
    categories = Category.query.all()
    return render_template('admin/categories.html', categories=categories)

@app.route('/admin/categories/add', methods=['GET', 'POST'])
@login_required
@admin_or_moderator_required
def admin_add_category():
    form = CategoryForm()
    if form.validate_on_submit():
        # Generate slug from name
        slug = Category.generate_slug(form.name.data)
        
        category = Category(
            name=form.name.data, 
            slug=slug,
            description=form.description.data
        )
        db.session.add(category)
        db.session.commit()
        flash('Category added successfully!', 'success')
        return redirect(url_for('admin_categories'))
    return render_template('admin/add_category.html', form=form)

@app.route('/admin/categories/<int:category_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_or_moderator_required
def admin_edit_category(category_id):
    category = Category.query.get_or_404(category_id)
    form = CategoryForm()
    
    if form.validate_on_submit():
        # Regenerate slug if name changed
        if category.name != form.name.data:
            category.slug = Category.generate_slug(form.name.data)
        
        category.name = form.name.data
        category.description = form.description.data
        db.session.commit()
        flash('Category updated successfully!', 'success')
        return redirect(url_for('admin_categories'))
    
    elif request.method == 'GET':
        form.name.data = category.name
        form.description.data = category.description
    
    return render_template('admin/edit_category.html', form=form, category=category)

@app.route('/admin/categories/<int:category_id>/toggle', methods=['POST'])
@login_required
@admin_or_moderator_required
def admin_toggle_category(category_id):
    category = Category.query.get_or_404(category_id)
    category.is_active = not category.is_active
    db.session.commit()
    status = 'activated' if category.is_active else 'deactivated'
    flash(f'Category {status} successfully!', 'success')
    return redirect(url_for('admin_categories'))

@app.route('/admin/comments')
@login_required
@admin_or_moderator_required
def admin_comments():
    page = request.args.get('page', 1, type=int)
    comments = Comment.query.order_by(Comment.date_posted.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template('admin/comments.html', comments=comments)

@app.route('/admin/comments/<int:comment_id>/toggle', methods=['POST'])
@login_required
@admin_or_moderator_required
def admin_toggle_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    comment.is_active = not comment.is_active
    db.session.commit()
    status = 'activated' if comment.is_active else 'deactivated'
    flash(f'Comment {status} successfully!', 'success')
    return redirect(url_for('admin_comments'))

@app.route('/admin/comments/<int:comment_id>/delete', methods=['POST'])
@login_required
@admin_or_moderator_required
def admin_delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    db.session.delete(comment)
    db.session.commit()
    flash('Comment deleted successfully!', 'success')
    return redirect(url_for('admin_comments'))

@app.route('/admin/adsense', methods=['GET', 'POST'])
@login_required
@admin_or_moderator_required
def admin_adsense():
    adsense = AdSense.query.first()
    if not adsense:
        adsense = AdSense()
        db.session.add(adsense)
        db.session.commit()
    
    form = AdSenseForm()
    if form.validate_on_submit():
        adsense.publisher_id = form.publisher_id.data
        adsense.header_ad_code = form.header_ad_code.data
        adsense.sidebar_ad_code = form.sidebar_ad_code.data
        adsense.footer_ad_code = form.footer_ad_code.data
        adsense.post_content_ad_code = form.post_content_ad_code.data
        adsense.category_ad_code = form.category_ad_code.data
        adsense.profile_ad_code = form.profile_ad_code.data
        adsense.is_enabled = form.is_enabled.data
        adsense.auto_ads_enabled = form.auto_ads_enabled.data
        adsense.ad_frequency = form.ad_frequency.data
        adsense.responsive_ads = form.responsive_ads.data
        adsense.updated_at = datetime.utcnow()
        db.session.commit()
        flash('AdSense settings updated successfully!', 'success')
        return redirect(url_for('admin_adsense'))
    
    elif request.method == 'GET':
        form.publisher_id.data = adsense.publisher_id
        form.header_ad_code.data = adsense.header_ad_code
        form.sidebar_ad_code.data = adsense.sidebar_ad_code
        form.footer_ad_code.data = adsense.footer_ad_code
        form.post_content_ad_code.data = adsense.post_content_ad_code
        form.category_ad_code.data = adsense.category_ad_code
        form.profile_ad_code.data = adsense.profile_ad_code
        form.is_enabled.data = adsense.is_enabled
        form.auto_ads_enabled.data = adsense.auto_ads_enabled
        form.ad_frequency.data = adsense.ad_frequency
        form.responsive_ads.data = adsense.responsive_ads
    
    return render_template('admin/adsense.html', form=form, adsense=adsense)

# Advertisement Management Routes
@app.route('/admin/advertisements')
@login_required
@admin_or_moderator_required
def admin_advertisements():
    page = request.args.get('page', 1, type=int)
    advertisements = Advertisement.query.order_by(Advertisement.created_at.desc()).paginate(
        page=page, per_page=10, error_out=False)
    return render_template('admin/advertisements.html', advertisements=advertisements)

@app.route('/admin/advertisements/add', methods=['GET', 'POST'])
@login_required
@admin_or_moderator_required
def admin_add_advertisement():
    form = AdvertisementForm()
    if form.validate_on_submit():
        # Handle image upload
        image_filename = None
        if form.image_file.data:
            image_filename = save_advertisement_image(form.image_file.data)
        
        advertisement = Advertisement(
            title=form.title.data,
            description=form.description.data,
            image_file=image_filename,
            image_url=form.image_url.data,
            link_url=form.link_url.data,
            ad_type=form.ad_type.data,
            placement=form.placement.data,
            target_audience=form.target_audience.data,
            priority=int(form.priority.data),
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            is_active=form.is_active.data,
            created_by=current_user.id
        )
        db.session.add(advertisement)
        db.session.commit()
        flash('Advertisement created successfully!', 'success')
        return redirect(url_for('admin_advertisements'))
    return render_template('admin/add_advertisement.html', form=form)

@app.route('/admin/advertisements/<int:ad_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_or_moderator_required
def admin_edit_advertisement(ad_id):
    advertisement = Advertisement.query.get_or_404(ad_id)
    form = AdvertisementForm()
    
    if form.validate_on_submit():
        # Handle image upload
        if form.image_file.data:
            image_filename = save_advertisement_image(form.image_file.data)
            advertisement.image_file = image_filename
        
        advertisement.title = form.title.data
        advertisement.description = form.description.data
        advertisement.image_url = form.image_url.data
        advertisement.link_url = form.link_url.data
        advertisement.ad_type = form.ad_type.data
        advertisement.placement = form.placement.data
        advertisement.target_audience = form.target_audience.data
        advertisement.priority = int(form.priority.data)
        advertisement.start_date = form.start_date.data
        advertisement.end_date = form.end_date.data
        advertisement.is_active = form.is_active.data
        advertisement.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Advertisement updated successfully!', 'success')
        return redirect(url_for('admin_advertisements'))
    
    elif request.method == 'GET':
        form.title.data = advertisement.title
        form.description.data = advertisement.description
        # Don't populate image_file field for security reasons
        form.image_url.data = advertisement.image_url
        form.link_url.data = advertisement.link_url
        form.ad_type.data = advertisement.ad_type
        form.placement.data = advertisement.placement
        form.target_audience.data = advertisement.target_audience
        form.priority.data = str(advertisement.priority)
        form.start_date.data = advertisement.start_date
        form.end_date.data = advertisement.end_date
        form.is_active.data = advertisement.is_active
    
    return render_template('admin/edit_advertisement.html', form=form, advertisement=advertisement)

@app.route('/admin/advertisements/<int:ad_id>/toggle', methods=['POST'])
@login_required
@admin_or_moderator_required
def admin_toggle_advertisement(ad_id):
    advertisement = Advertisement.query.get_or_404(ad_id)
    advertisement.is_active = not advertisement.is_active
    advertisement.updated_at = datetime.utcnow()
    db.session.commit()
    status = 'activated' if advertisement.is_active else 'deactivated'
    flash(f'Advertisement "{advertisement.title}" has been {status}!', 'success')
    return redirect(url_for('admin_advertisements'))

@app.route('/admin/advertisements/<int:ad_id>/delete', methods=['POST'])
@login_required
@admin_or_moderator_required
def admin_delete_advertisement(ad_id):
    advertisement = Advertisement.query.get_or_404(ad_id)
    db.session.delete(advertisement)
    db.session.commit()
    flash(f'Advertisement "{advertisement.title}" has been deleted!', 'success')
    return redirect(url_for('admin_advertisements'))

@app.route('/admin/advertisements/<int:ad_id>/stats')
@login_required
@admin_or_moderator_required
def admin_advertisement_stats(ad_id):
    advertisement = Advertisement.query.get_or_404(ad_id)
    
    # Get click statistics
    total_clicks = AdClick.query.filter_by(ad_id=ad_id).count()
    recent_clicks = AdClick.query.filter_by(ad_id=ad_id).filter(
        AdClick.clicked_at >= datetime.utcnow() - timedelta(days=30)
    ).count()
    
    # Get daily click data for the last 30 days
    daily_clicks = []
    for i in range(30):
        date = datetime.utcnow() - timedelta(days=i)
        clicks = AdClick.query.filter_by(ad_id=ad_id).filter(
            AdClick.clicked_at >= date.replace(hour=0, minute=0, second=0),
            AdClick.clicked_at < date.replace(hour=23, minute=59, second=59)
        ).count()
        daily_clicks.append({
            'date': date.strftime('%Y-%m-%d'),
            'clicks': clicks
        })
    
    return render_template('admin/advertisement_stats.html', 
                         advertisement=advertisement,
                         total_clicks=total_clicks,
                         recent_clicks=recent_clicks,
                         daily_clicks=daily_clicks)

# Advertisement Click Tracking
@app.route('/ad/click/<int:ad_id>')
def track_ad_click(ad_id):
    ad = Advertisement.query.get_or_404(ad_id)
    
    # Track the click
    ad.click_count += 1
    
    # Create click record
    click = AdClick(
        ad_id=ad.id,
        user_id=current_user.id if current_user.is_authenticated else None,
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent', '')
    )
    
    db.session.add(click)
    db.session.commit()
    
    # Redirect to the ad's link URL or back to home if no URL
    if ad.link_url:
        return redirect(ad.link_url)
    else:
        return redirect(url_for('index'))

# Test routes for error pages (remove in production)
@app.route('/test/404')
def test_404():
    abort(404)

@app.route('/test/403')
def test_403():
    abort(403)

@app.route('/test/500')
def test_500():
    abort(500)

# Catch-all route for handling non-existent pages
@app.route('/<path:path>')
def catch_all(path):
    # Check if it looks like a post slug
    if '/' not in path and '-' in path:
        # Could be a post slug, show 404 with suggestion
        abort(404)
    # For other paths, show generic 404
    abort(404)

# Error Handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(403)
def forbidden_error(error):
    return render_template('errors/403.html'), 403

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500

@app.context_processor
def inject_sidebar_data():
    categories = Category.query.filter_by(is_active=True).all()
    recent_posts = Post.query.filter_by(is_active=True).order_by(Post.date_posted.desc()).limit(5).all()
    
    # Calculate comprehensive forum statistics
    total_posts = Post.query.filter_by(is_active=True).count()
    total_users = User.query.filter_by(is_active=True).count()
    total_comments = Comment.query.filter_by(is_active=True).count()
    total_likes = Like.query.count()
    
    # Get recent activity (posts, comments, likes from last 90 days for better visibility)
    activity_cutoff = datetime.utcnow() - timedelta(days=90)
    
    recent_activity = []
    
    # Recent posts
    recent_new_posts = Post.query.filter(
        Post.is_active == True,
        Post.date_posted >= activity_cutoff
    ).order_by(Post.date_posted.desc()).limit(5).all()
    
    for post in recent_new_posts:
        recent_activity.append({
            'type': 'post',
            'icon': 'fas fa-file-alt',
            'color': 'text-blue-600',
            'bg_color': 'bg-blue-100',
            'title': post.title,
            'user': post.author.username,
            'user_image': post.author.profile_image,
            'date': post.date_posted,
            'url': url_for('post_detail', slug=post.slug),
            'category': post.category.name
        })
    
    # Recent comments
    recent_new_comments = Comment.query.filter(
        Comment.is_active == True,
        Comment.date_posted >= activity_cutoff,
        Comment.parent_id == None  # Only top-level comments
    ).order_by(Comment.date_posted.desc()).limit(5).all()
    
    for comment in recent_new_comments:
        recent_activity.append({
            'type': 'comment',
            'icon': 'fas fa-comment',
            'color': 'text-green-600',
            'bg_color': 'bg-green-100',
            'title': f"Commented on \"{comment.post.title[:30]}...\"",
            'user': comment.author.username,
            'user_image': comment.author.profile_image,
            'date': comment.date_posted,
            'url': url_for('post_detail', slug=comment.post.slug),
            'category': comment.post.category.name
        })
    
    # Recent likes
    recent_new_likes = Like.query.filter(
        Like.date_liked >= activity_cutoff
    ).order_by(Like.date_liked.desc()).limit(3).all()
    
    for like in recent_new_likes:
        recent_activity.append({
            'type': 'like',
            'icon': 'fas fa-heart',
            'color': 'text-red-600',
            'bg_color': 'bg-red-100',
            'title': f"Liked \"{like.post.title[:30]}...\"",
            'user': like.user.username,
            'user_image': like.user.profile_image,
            'date': like.date_liked,
            'url': url_for('post_detail', slug=like.post.slug),
            'category': like.post.category.name
        })
    
    # Sort all activity by date
    recent_activity.sort(key=lambda x: x['date'], reverse=True)
    recent_activity = recent_activity[:8]  # Limit to 8 most recent activities
    
    # Get most active users (by posts + comments in last 90 days, or all time if none)
    activity_period = datetime.utcnow() - timedelta(days=90)
    
    # This is a simplified approach - in production you might want to use raw SQL for better performance
    active_users = []
    users = User.query.filter_by(is_active=True).limit(20).all()  # Limit to avoid performance issues
    
    for user in users:
        recent_posts_count = Post.query.filter(
            Post.user_id == user.id,
            Post.is_active == True,
            Post.date_posted >= activity_period
        ).count()
        
        recent_comments_count = Comment.query.filter(
            Comment.user_id == user.id,
            Comment.is_active == True,
            Comment.date_posted >= activity_period
        ).count()
        
        # If no recent activity, check all-time activity
        if recent_posts_count == 0 and recent_comments_count == 0:
            recent_posts_count = Post.query.filter(
                Post.user_id == user.id,
                Post.is_active == True
            ).count()
            
            recent_comments_count = Comment.query.filter(
                Comment.user_id == user.id,
                Comment.is_active == True
            ).count()
        
        activity_score = recent_posts_count * 3 + recent_comments_count  # Posts worth more
        
        if activity_score > 0:
            active_users.append({
                'user': user,
                'score': activity_score,
                'posts': recent_posts_count,
                'comments': recent_comments_count
            })
    
    # Sort by activity score and get top 5
    active_users.sort(key=lambda x: x['score'], reverse=True)
    top_active_users = active_users[:5]
    
    # Get newest members (last 90 days, or latest 5 if none in that period)
    member_cutoff = datetime.utcnow() - timedelta(days=90)
    newest_members = User.query.filter(
        User.is_active == True,
        User.date_joined >= member_cutoff
    ).order_by(User.date_joined.desc()).limit(5).all()
    
    # If no new members in 90 days, get the 5 most recent members
    if not newest_members:
        newest_members = User.query.filter_by(is_active=True).order_by(User.date_joined.desc()).limit(5).all()
    
    adsense = AdSense.query.first()
    
    forum_stats = {
        'total_posts': total_posts,
        'total_users': total_users,
        'total_comments': total_comments,
        'total_likes': total_likes,
        'posts_this_week': len(recent_new_posts),
        'comments_this_week': len(recent_new_comments),
        'likes_this_week': len(recent_new_likes)
    }
    
    # Get active custom advertisements for all placements
    sidebar_ads = Advertisement.query.filter(
        Advertisement.placement.in_(['sidebar', 'left_sidebar', 'content']),
        Advertisement.is_active == True
    ).filter(
        db.or_(Advertisement.end_date.is_(None), Advertisement.end_date > datetime.utcnow())
    ).order_by(Advertisement.priority.desc()).all()
    
    header_ads = Advertisement.query.filter_by(
        placement='header', 
        is_active=True
    ).filter(
        db.or_(Advertisement.end_date.is_(None), Advertisement.end_date > datetime.utcnow())
    ).order_by(Advertisement.priority.desc()).limit(1).all()
    
    footer_ads = Advertisement.query.filter_by(
        placement='footer', 
        is_active=True
    ).filter(
        db.or_(Advertisement.end_date.is_(None), Advertisement.end_date > datetime.utcnow())
    ).order_by(Advertisement.priority.desc()).limit(2).all()
    
    return dict(
        categories=categories,
        sidebar_categories=categories,
        sidebar_recent_posts=recent_posts,
        forum_stats=forum_stats,
        recent_activity=recent_activity,
        top_active_users=top_active_users,
        newest_members=newest_members,
        adsense=adsense,
        should_display_ads=should_display_ads,
        sidebar_ads=sidebar_ads,
        header_ads=header_ads,
        footer_ads=footer_ads
    )

def init_db():
    """Initialize the database with tables and sample data"""
    db.create_all()
    
    if not Category.query.first():
        categories_data = [
            ('General Discussion', 'General topics and discussions'),
            ('Technology', 'Tech news, programming, and digital trends'),
            ('Culture', 'African culture, traditions, and heritage'),
            ('Business', 'Entrepreneurship and business opportunities'),
            ('Education', 'Learning, schools, and educational resources')
        ]
        
        for name, description in categories_data:
            slug = Category.generate_slug(name)
            category = Category(name=name, slug=slug, description=description)
            db.session.add(category)
        
        db.session.commit()
        print("Sample categories created!")

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True) 