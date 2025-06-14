# Profile functionality for AfroPeople Forum
from flask import render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, SubmitField, DateField
from wtforms.validators import Length, Optional, URL
from werkzeug.utils import secure_filename
from PIL import Image
import os
import secrets

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

def save_profile_picture(form_picture):
    """Save and resize profile picture"""
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(current_app.root_path, 'static/uploads/profile_pics', picture_fn)
    
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

# Add these routes to your main app.py file
PROFILE_ROUTES = """
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
    
    # Get user's posts
    posts = Post.query.filter_by(user_id=user.id, is_active=True).order_by(Post.date_posted.desc()).limit(5).all()
    
    # Get user's recent comments
    comments = Comment.query.filter_by(user_id=user.id, is_active=True).order_by(Comment.date_posted.desc()).limit(5).all()
    
    # Calculate user stats
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
        # Handle profile picture upload
        if form.profile_image.data:
            try:
                picture_file = save_profile_picture(form.profile_image.data)
                current_user.profile_image = picture_file
            except Exception as e:
                flash('Error uploading image. Please try again.', 'danger')
                return render_template('edit_profile.html', form=form)
        
        # Update user profile
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
        # Pre-populate form with current user data
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
""" 