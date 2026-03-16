from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from .extensions import db
from .models import Food, ConsumptionLog, MealInterval
from datetime import datetime, timedelta, date

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    if current_user.is_authenticated:
        now = datetime.utcnow()
        today = now.date()
        yesterday = today - timedelta(days=1)
        tomorrow = today + timedelta(days=1)
        
        intervals_data = []
        
        for interval in current_user.intervals.order_by(MealInterval.start_time).all():
            if interval.start_time <= interval.end_time:
                start_dt = datetime.combine(today, interval.start_time)
                end_dt = datetime.combine(today, interval.end_time)
            else:
                if now.time() <= interval.end_time:
                    start_dt = datetime.combine(yesterday, interval.start_time)
                    end_dt = datetime.combine(today, interval.end_time)
                else:
                    start_dt = datetime.combine(today, interval.start_time)
                    end_dt = datetime.combine(tomorrow, interval.end_time)
                    
            logs = current_user.logs.filter(
                ConsumptionLog.fecha_hora >= start_dt,
                ConsumptionLog.fecha_hora <= end_dt
            ).all()
            
            # Group by food
            grouped_logs = {}
            total_carbos = 0.0
            
            for log in logs:
                total_carbos += log.carbohidratos_calculados
                if log.food_id in grouped_logs:
                    grouped_logs[log.food_id]['cantidad_gramos'] += log.cantidad_gramos
                    grouped_logs[log.food_id]['carbohidratos'] += log.carbohidratos_calculados
                else:
                    grouped_logs[log.food_id] = {
                        'food': log.food,
                        'cantidad_gramos': log.cantidad_gramos,
                        'carbohidratos': log.carbohidratos_calculados
                    }
                    
            percentage = (total_carbos / interval.target_hc * 100) if interval.target_hc else 0

            intervals_data.append({
                'interval': interval,
                'grouped_logs': list(grouped_logs.values()),
                'total_carbos': total_carbos,
                'target_hc': interval.target_hc,
                'remaining_hc': (interval.target_hc - total_carbos) if interval.target_hc is not None else None,
                'percentage': percentage,
                'is_active': start_dt <= now <= end_dt
            })
            
        return render_template('index.html', intervals_data=intervals_data)
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

@bp.route('/intervals')
@login_required
def intervals():
    user_intervals = current_user.intervals.order_by(MealInterval.start_time).all()
    return render_template('intervals.html', intervals=user_intervals)

@bp.route('/add_interval', methods=['POST'])
@login_required
def add_interval():
    name = request.form.get('name')
    start_time_str = request.form.get('start_time')
    end_time_str = request.form.get('end_time')
    target_hc_str = request.form.get('target_hc')
    
    try:
        start_time = datetime.strptime(start_time_str, '%H:%M').time()
        end_time = datetime.strptime(end_time_str, '%H:%M').time()
        target_hc = float(target_hc_str) if target_hc_str else None
        
        new_interval = MealInterval(
            user_id=current_user.id,
            name=name,
            start_time=start_time,
            end_time=end_time,
            target_hc=target_hc
        )
        db.session.add(new_interval)
        db.session.commit()
        flash('Intervalo añadido exitosamente.')
    except Exception as e:
        flash('Error al añadir el intervalo. Verifica los datos.')
        
    return redirect(url_for('main.intervals'))

@bp.route('/edit_interval/<int:interval_id>', methods=['POST'])
@login_required
def edit_interval(interval_id):
    interval = db.session.get(MealInterval, interval_id)
    if not interval or interval.user_id != current_user.id:
        flash('Intervalo no encontrado o acceso denegado.')
        return redirect(url_for('main.intervals'))
        
    name = request.form.get('name')
    start_time_str = request.form.get('start_time')
    end_time_str = request.form.get('end_time')
    target_hc_str = request.form.get('target_hc')
    
    try:
        interval.name = name
        interval.start_time = datetime.strptime(start_time_str, '%H:%M').time()
        interval.end_time = datetime.strptime(end_time_str, '%H:%M').time()
        interval.target_hc = float(target_hc_str) if target_hc_str else None
        
        db.session.commit()
        flash('Intervalo actualizado exitosamente.')
    except Exception as e:
        flash('Error al actualizar el intervalo. Verifica los datos.')
        
    return redirect(url_for('main.intervals'))

@bp.route('/delete_interval/<int:interval_id>', methods=['POST'])
@login_required
def delete_interval(interval_id):
    interval = db.session.get(MealInterval, interval_id)
    if not interval or interval.user_id != current_user.id:
        flash('Intervalo no encontrado o acceso denegado.')
        return redirect(url_for('main.intervals'))
        
    db.session.delete(interval)
    db.session.commit()
    flash('Intervalo eliminado exitosamente.')
    return redirect(url_for('main.intervals'))
