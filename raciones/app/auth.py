from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from urllib.parse import urlsplit
from .extensions import db
from .models import User

bp = Blueprint('auth', __name__)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    if request.method == 'POST':
        login_input = request.form['username'].strip()
        user = db.session.scalar(db.select(User).where(
            (User.username == login_input) | (User.email == login_input)
        ))
        if user is None or not user.check_password(request.form['password']):
            flash('Usuario o contraseña no válidos')
            return redirect(url_for('auth.login'))
        login_user(user, remember='remember_me' in request.form)
        next_page = request.args.get('next')
        if not next_page or urlsplit(next_page).netloc != '':
            next_page = url_for('main.index')
        return redirect(next_page)
    return render_template('auth/login.html')

@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('main.index'))

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip()
        password = request.form['password']
        
        user = db.session.scalar(db.select(User).where((User.username == username) | (User.email == email)))
        if user:
            flash('El usuario o email ya existe.')
            return redirect(url_for('auth.register'))
            
        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash('¡Felicidades, te has registrado correctamente!')
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html')

@bp.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    if request.method == 'POST':
        email = request.form['email'].strip()
        user = db.session.scalar(db.select(User).where(User.email == email))
        if user:
            # En un entorno real se enviaría un email con un token.
            # Aquí, redirigimos directamente a la vista para restablecer la contraseña por simplicidad.
            return redirect(url_for('auth.reset_password', id=user.id))
        else:
            flash('No se ha encontrado ninguna cuenta con ese correo electrónico.')
            return redirect(url_for('auth.forgot_password'))
    return render_template('auth/forgot_password.html')

@bp.route('/reset_password/<int:id>', methods=['GET', 'POST'])
def reset_password(id):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    user = db.session.get(User, id)
    if not user:
        flash('Usuario no válido para reestablecer contraseña.')
        return redirect(url_for('auth.login'))
        
    if request.method == 'POST':
        password = request.form['password']
        user.set_password(password)
        db.session.commit()
        flash('Tu contraseña se ha restablecido correctamente. Ya puedes iniciar sesión.')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/reset_password.html', user=user)
