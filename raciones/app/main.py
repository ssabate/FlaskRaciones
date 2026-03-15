from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from .extensions import db
from .models import Food, ConsumptionLog
from datetime import datetime

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    if current_user.is_authenticated:
        logs = current_user.logs.order_by(ConsumptionLog.fecha_hora.desc()).limit(10).all()
        return render_template('index.html', logs=logs)
    return render_template('index.html')

@bp.route('/foods')
@login_required
def foods():
    # Obtener todos los alimentos base (sin user_id)
    base_foods = db.session.scalars(db.select(Food).where(Food.user_id == None)).all()
    # Obtener las sobrescrituras del usuario actual
    user_overrides = {f.parent_id: f for f in current_user.custom_foods if f.parent_id is not None}
    
    display_foods = []
    for food in base_foods:
        if food.id in user_overrides:
            display_foods.append(user_overrides[food.id])
        else:
            display_foods.append(food)
            
    # Añadir los alimentos que son completamente nuevos del usuario (parent_id es None pero user_id es el id)
    user_custom = db.session.scalars(db.select(Food).where((Food.user_id == current_user.id) & (Food.parent_id == None))).all()
    display_foods.extend(user_custom)
    
    return render_template('foods.html', foods=display_foods)

@bp.route('/log_consumption/<int:food_id>', methods=['POST'])
@login_required
def log_consumption(food_id):
    cantidad = float(request.form.get('cantidad', 0))
    if cantidad <= 0:
        flash('La cantidad debe ser mayor que cero.')
        return redirect(url_for('main.foods'))
        
    food = db.session.get(Food, food_id)
    if not food:
        flash('Alimento no encontrado.')
        return redirect(url_for('main.foods'))
        
    carbos = (food.hidratos_por_100g / 100) * cantidad
    
    log = ConsumptionLog(
        user_id=current_user.id,
        food_id=food.id,
        cantidad_gramos=cantidad,
        carbohidratos_calculados=carbos,
        fecha_hora=datetime.utcnow()
    )
    db.session.add(log)
    db.session.commit()
    flash(f'Has registrado {cantidad}g de {food.nombre} ({carbos:.1f}g de HC).')
    return redirect(url_for('main.index'))

@bp.route('/add_food', methods=['POST'])
@login_required
def add_food():
    nombre = request.form.get('nombre')
    hidratos = float(request.form.get('hidratos', 0))
    parent_id = request.form.get('parent_id')
    
    if parent_id:
        parent_id = int(parent_id)
        # Chequear si ya hay una sobrescritura
        existing = db.session.scalar(db.select(Food).where((Food.user_id == current_user.id) & (Food.parent_id == parent_id)))
        if existing:
            existing.nombre = nombre
            existing.hidratos_por_100g = hidratos
            flash('Sobrescritura actualizada.')
        else:
            override = Food(nombre=nombre, hidratos_por_100g=hidratos, user_id=current_user.id, parent_id=parent_id)
            db.session.add(override)
            flash('Alimento sobrescrito exitosamente.')
    else:
        new_food = Food(nombre=nombre, hidratos_por_100g=hidratos, user_id=current_user.id)
        db.session.add(new_food)
        flash('Nuevo alimento añadido.')
        
    db.session.commit()
    return redirect(url_for('main.foods'))

