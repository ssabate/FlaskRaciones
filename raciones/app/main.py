from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import and_, func, or_
from .extensions import db
from .models import Food, ConsumptionLog, MealInterval
from datetime import datetime, timedelta, date, time

bp = Blueprint('main', __name__)
RC_GRAMS = 10.0


def _interval_window_for_reference(now, interval):
    today = now.date()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)

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

    return start_dt, end_dt


def _time_is_in_interval(interval, target_time):
    if interval.start_time <= interval.end_time:
        return interval.start_time <= target_time <= interval.end_time
    return target_time >= interval.start_time or target_time <= interval.end_time


def _get_interval_for_timestamp(intervals, timestamp):
    target_time = timestamp.time()
    for interval in intervals:
        if _time_is_in_interval(interval, target_time):
            return interval
    return None


def _service_date_for_log(interval, timestamp):
    service_date = timestamp.date()
    if interval and interval.start_time > interval.end_time and timestamp.time() <= interval.end_time:
        service_date = service_date - timedelta(days=1)
    return service_date


def _is_valid_half_step(value):
    return abs((value * 2) - round(value * 2)) < 1e-9


def _get_display_foods_for_user():
    base_foods = db.session.scalars(db.select(Food).where(Food.user_id == None)).all()
    user_overrides = {f.parent_id: f for f in current_user.custom_foods if f.parent_id is not None}

    display_foods = []
    for food in base_foods:
        if food.id in user_overrides:
            display_foods.append(user_overrides[food.id])
        else:
            display_foods.append(food)

    user_custom = db.session.scalars(
        db.select(Food).where((Food.user_id == current_user.id) & (Food.parent_id == None))
    ).all()
    display_foods.extend(user_custom)
    display_foods.sort(key=lambda food: food.nombre.lower())
    return display_foods


def _get_food_family_ids_for_user(food):
    """Return IDs that represent the same logical food for the current user."""
    root_food_id = food.parent_id if food.parent_id is not None else food.id
    return db.session.scalars(
        db.select(Food.id).where(
            and_(
                or_(Food.id == root_food_id, Food.parent_id == root_food_id),
                or_(Food.user_id == None, Food.user_id == current_user.id),
            )
        )
    ).all()

@bp.route('/')
def index():
    if current_user.is_authenticated:
        now = datetime.now()
        intervals_data = []
        active_interval_id = None
        
        for interval in current_user.intervals.order_by(MealInterval.start_time).all():
            start_dt, end_dt = _interval_window_for_reference(now, interval)
                    
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
            is_active = start_dt <= now <= end_dt
            if is_active:
                active_interval_id = interval.id

            intervals_data.append({
                'interval': interval,
                'grouped_logs': list(grouped_logs.values()),
                'total_carbos': total_carbos,
                'target_hc': interval.target_hc,
                'remaining_hc': (interval.target_hc - total_carbos) if interval.target_hc is not None else None,
                'percentage': percentage,
                'is_active': is_active
            })

        if active_interval_id is None and intervals_data:
            active_interval_id = intervals_data[0]['interval'].id
            
        return render_template('index.html', intervals_data=intervals_data, active_interval_id=active_interval_id)
    return render_template('index.html')

@bp.route('/foods')
@login_required
def foods():
    return render_template('foods.html', foods=_get_display_foods_for_user())


@bp.route('/consume')
@login_required
def consume():
    return render_template('consume.html', foods=_get_display_foods_for_user(), rc_grams=RC_GRAMS)

@bp.route('/log_consumption', methods=['POST'])
@login_required
def log_consumption():
    food_id = request.form.get('food_id', type=int)
    if not food_id:
        flash('Selecciona un alimento para registrar el consumo.')
        return redirect(url_for('main.consume'))

    food = db.session.get(Food, food_id)
    if not food or (food.user_id is not None and food.user_id != current_user.id):
        flash('Alimento no encontrado.')
        return redirect(url_for('main.consume'))

    input_mode = request.form.get('input_mode', 'grams')
    cantidad_gramos = 0.0
    carbos = 0.0

    try:
        if input_mode == 'rc':
            cantidad_rc = float(request.form.get('cantidad_rc', 0))
            if cantidad_rc <= 0 or not _is_valid_half_step(cantidad_rc):
                flash('Las RC deben ser mayores que cero y avanzar de 0.5 en 0.5.')
                return redirect(url_for('main.consume'))
            if food.hidratos_por_100g <= 0:
                flash('No se puede calcular gramos para un alimento con hidratos no positivos.')
                return redirect(url_for('main.consume'))

            carbos = cantidad_rc * RC_GRAMS
            cantidad_gramos = (carbos * 100.0) / food.hidratos_por_100g
        else:
            cantidad_gramos = float(request.form.get('cantidad_gramos', 0))
            if cantidad_gramos <= 0:
                flash('La cantidad en gramos debe ser mayor que cero.')
                return redirect(url_for('main.consume'))
            carbos = (food.hidratos_por_100g / 100) * cantidad_gramos
    except (TypeError, ValueError):
        flash('Datos de consumo no validos.')
        return redirect(url_for('main.consume'))
    
    log = ConsumptionLog(
        user_id=current_user.id,
        food_id=food.id,
        cantidad_gramos=cantidad_gramos,
        carbohidratos_calculados=carbos,
        fecha_hora=datetime.now()
    )
    db.session.add(log)
    db.session.commit()
    flash(f'Has registrado {cantidad_gramos:.1f}g de {food.nombre} ({carbos:.1f}g de HC).')
    return redirect(url_for('main.index'))

@bp.route('/add_food', methods=['POST'])
@login_required
def add_food():
    nombre = (request.form.get('nombre') or '').strip()
    hidratos_str = request.form.get('hidratos', '0')
    parent_id = request.form.get('parent_id')

    try:
        hidratos = float(hidratos_str)
    except (TypeError, ValueError):
        flash('El valor de hidratos no es valido.')
        return redirect(url_for('main.foods'))

    if not nombre:
        flash('El nombre del alimento es obligatorio.')
        return redirect(url_for('main.foods'))
    if hidratos <= 0:
        flash('Los hidratos por 100g deben ser mayores que cero.')
        return redirect(url_for('main.foods'))
    
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
        duplicate_name = db.session.scalar(
            db.select(Food).where(
                and_(
                    func.lower(Food.nombre) == nombre.lower(),
                    or_(Food.user_id == None, Food.user_id == current_user.id),
                )
            )
        )
        if duplicate_name:
            flash('Ya existe un alimento con ese nombre. Editalo en lugar de crear uno nuevo.')
            return redirect(url_for('main.foods'))

        new_food = Food(nombre=nombre, hidratos_por_100g=hidratos, user_id=current_user.id)
        db.session.add(new_food)
        flash('Nuevo alimento añadido.')
        
    db.session.commit()
    return redirect(url_for('main.foods'))


@bp.route('/edit_food/<int:food_id>', methods=['POST'])
@login_required
def edit_food(food_id):
    food = db.session.get(Food, food_id)
    if not food:
        flash('Alimento no encontrado.')
        return redirect(url_for('main.foods'))

    nombre = (request.form.get('nombre') or '').strip()
    hidratos_str = request.form.get('hidratos', '0')

    try:
        hidratos = float(hidratos_str)
    except (TypeError, ValueError):
        flash('El valor de hidratos no es valido.')
        return redirect(url_for('main.foods'))

    if not nombre:
        flash('El nombre del alimento es obligatorio.')
        return redirect(url_for('main.foods'))
    if hidratos <= 0:
        flash('Los hidratos por 100g deben ser mayores que cero.')
        return redirect(url_for('main.foods'))

    duplicate_query = db.select(Food).where(
        and_(
            func.lower(Food.nombre) == nombre.lower(),
            or_(Food.user_id == None, Food.user_id == current_user.id),
            Food.id != food_id,
        )
    )
    duplicate_name = db.session.scalar(duplicate_query)

    if food.user_id is None:
        existing_override = db.session.scalar(
            db.select(Food).where(
                and_(Food.user_id == current_user.id, Food.parent_id == food.id)
            )
        )
        if duplicate_name and (not existing_override or duplicate_name.id != existing_override.id):
            flash('Ya existe un alimento con ese nombre. Elige otro para la sobrescritura.')
            return redirect(url_for('main.foods'))

        if existing_override:
            existing_override.nombre = nombre
            existing_override.hidratos_por_100g = hidratos
            flash('Sobrescritura actualizada.')
        else:
            db.session.add(Food(nombre=nombre, hidratos_por_100g=hidratos, user_id=current_user.id, parent_id=food.id))
            flash('Sobrescritura creada.')
    else:
        if food.user_id != current_user.id:
            flash('No tienes permiso para modificar este alimento.')
            return redirect(url_for('main.foods'))
        if duplicate_name:
            flash('Ya existe un alimento con ese nombre. Elige otro.')
            return redirect(url_for('main.foods'))

        food.nombre = nombre
        food.hidratos_por_100g = hidratos
        flash('Alimento actualizado.')

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


@bp.route('/api/last_consumption/<int:food_id>')
@login_required
def api_last_consumption(food_id):
    from flask import jsonify
    now = datetime.now()
    intervals = current_user.intervals.order_by(MealInterval.start_time).all()
    selected_food = db.session.get(Food, food_id)

    if not selected_food or (selected_food.user_id is not None and selected_food.user_id != current_user.id):
        return jsonify({'found': False, 'cantidad_gramos': 100.0, 'cantidad_rc': 1.0})

    family_food_ids = _get_food_family_ids_for_user(selected_food)

    # Determinar la ingesta actual
    current_interval = None
    for interval in intervals:
        if _time_is_in_interval(interval, now.time()):
            current_interval = interval
            break

    last_log = None

    if current_interval:
        # Buscar la última consumición en la misma franja horaria (últimos 60 días)
        search_start = now - timedelta(days=60)
        logs_same_food = (
            current_user.logs
            .filter(
                ConsumptionLog.food_id.in_(family_food_ids),
                ConsumptionLog.fecha_hora >= search_start,
            )
            .order_by(ConsumptionLog.fecha_hora.desc())
            .all()
        )
        for log in logs_same_food:
            log_interval = _get_interval_for_timestamp(intervals, log.fecha_hora)
            if log_interval and log_interval.id == current_interval.id:
                last_log = log
                break

    if not last_log:
        # Fallback: cualquier consumición previa del alimento
        last_log = (
            current_user.logs
            .filter(ConsumptionLog.food_id.in_(family_food_ids))
            .order_by(ConsumptionLog.fecha_hora.desc())
            .first()
        )

    if last_log:
        rc_raw = last_log.carbohidratos_calculados / RC_GRAMS if RC_GRAMS > 0 else 0
        # Redondear al 0.5 más cercano
        rc_value = round(rc_raw * 2) / 2
        if rc_value <= 0:
            rc_value = 0.5
        return jsonify({
            'found': True,
            'cantidad_gramos': round(last_log.cantidad_gramos, 1),
            'cantidad_rc': rc_value,
        })

    return jsonify({'found': False, 'cantidad_gramos': 100.0, 'cantidad_rc': 1.0})


@bp.route('/history')
@login_required
def history():
    intervals = current_user.intervals.order_by(MealInterval.start_time).all()

    today_str = date.today().isoformat()
    from_date_str = request.args.get('from_date', today_str)
    to_date_str = request.args.get('to_date', today_str)
    interval_id = request.args.get('interval_id', type=int)
    selected_view = request.args.get('view', 'consumption')

    if selected_view not in {'consumption', 'interval'}:
        selected_view = 'consumption'

    try:
        from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
        to_date = datetime.strptime(to_date_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Formato de fecha no valido.')
        return redirect(url_for('main.history'))

    if from_date > to_date:
        from_date, to_date = to_date, from_date

    has_overnight_intervals = any(interval.start_time > interval.end_time for interval in intervals)
    query_from_date = from_date - timedelta(days=1) if has_overnight_intervals else from_date
    query_to_date = to_date + timedelta(days=1) if has_overnight_intervals else to_date

    start_dt = datetime.combine(query_from_date, time.min)
    end_dt = datetime.combine(query_to_date, time.max)

    logs = current_user.logs.filter(
        ConsumptionLog.fecha_hora >= start_dt,
        ConsumptionLog.fecha_hora <= end_dt,
    ).order_by(ConsumptionLog.fecha_hora.desc()).all()

    logs_data = []
    grouped_map = {}
    for log in logs:
        interval = _get_interval_for_timestamp(intervals, log.fecha_hora)
        service_date = _service_date_for_log(interval, log.fecha_hora)

        if not (from_date <= service_date <= to_date):
            continue
        if interval_id and (not interval or interval.id != interval_id):
            continue

        logs_data.append({
            'log': log,
            'interval': interval,
            'service_date': service_date,
        })

        group_key = (service_date, interval.id if interval else None)
        if group_key not in grouped_map:
            grouped_map[group_key] = {
                'service_date': service_date,
                'interval': interval,
                'total_hc': 0.0,
                'total_grams': 0.0,
                'items_count': 0,
                'foods_map': {},
            }

        group = grouped_map[group_key]
        group['total_hc'] += log.carbohidratos_calculados
        group['total_grams'] += log.cantidad_gramos
        group['items_count'] += 1

        food_entry = group['foods_map'].setdefault(
            log.food_id,
            {
                'food_name': log.food.nombre,
                'grams': 0.0,
                'hc': 0.0,
            }
        )
        food_entry['grams'] += log.cantidad_gramos
        food_entry['hc'] += log.carbohidratos_calculados

    total_hc = sum(item['log'].carbohidratos_calculados for item in logs_data)
    grouped_data = sorted(
        [
            {
                'service_date': group['service_date'],
                'interval': group['interval'],
                'total_hc': group['total_hc'],
                'total_grams': group['total_grams'],
                'items_count': group['items_count'],
                'foods': sorted(group['foods_map'].values(), key=lambda item: item['food_name'].lower()),
            }
            for group in grouped_map.values()
        ],
        key=lambda item: (
            item['service_date'],
            item['interval'].start_time if item['interval'] else time.min,
        ),
        reverse=True,
    )

    return render_template(
        'history.html',
        logs_data=logs_data,
        grouped_data=grouped_data,
        intervals=intervals,
        selected_interval_id=interval_id,
        selected_view=selected_view,
        from_date=from_date.isoformat(),
        to_date=to_date.isoformat(),
        total_hc=total_hc,
    )

