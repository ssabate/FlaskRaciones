from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from .extensions import db

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, index=True, nullable=False)
    email = db.Column(db.String(120), unique=True, index=True, nullable=False)
    password_hash = db.Column(db.String(256))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Food(db.Model):
    __tablename__ = 'foods'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    hidratos_por_100g = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('foods.id'), nullable=True)

    # Relationships
    user = db.relationship('User', backref=db.backref('custom_foods', lazy='dynamic'))
    parent = db.relationship('Food', remote_side=[id], backref=db.backref('overrides', lazy='dynamic'))

    def __repr__(self):
        return f'<Food {self.nombre}>'

class ConsumptionLog(db.Model):
    __tablename__ = 'consumption_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    food_id = db.Column(db.Integer, db.ForeignKey('foods.id'), nullable=False)
    cantidad_gramos = db.Column(db.Float, nullable=False)
    carbohidratos_calculados = db.Column(db.Float, nullable=False)
    fecha_hora = db.Column(db.DateTime, default=datetime.now, index=True)

    user = db.relationship('User', backref=db.backref('logs', lazy='dynamic'))
    food = db.relationship('Food')

    def __repr__(self):
        return f'<ConsumptionLog {self.id} for user {self.user_id}>'

class MealInterval(db.Model):
    __tablename__ = 'meal_intervals'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(64), nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    target_hc = db.Column(db.Float, nullable=True) # Optional target for carbs

    user = db.relationship('User', backref=db.backref('intervals', lazy='dynamic', cascade="all, delete-orphan"))

    def __repr__(self):
        return f'<MealInterval {self.name} ({self.start_time} - {self.end_time})>'
