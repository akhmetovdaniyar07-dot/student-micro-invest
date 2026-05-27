from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(100))
    university = db.Column(db.String(100))
    nickname = db.Column(db.String(50))
    address = db.Column(db.String(200))
    
    # Финансы
    balance = db.Column(db.Float, default=0.0)
    portfolio = db.Column(db.Float, default=0.0)
    deposit = db.Column(db.Float, default=0.0)
    level = db.Column(db.Integer, default=1)
    exp = db.Column(db.Integer, default=0)
    streak = db.Column(db.Integer, default=0)
    rounding_limit = db.Column(db.Integer, default=100)
    auto_sweep_threshold = db.Column(db.Float, default=5000.0) # Порог для авто-перевода
    referral_code = db.Column(db.String(10), unique=True)
    referrals_count = db.Column(db.Integer, default=0)
    achievements_json = db.Column(db.Text, default='[]') # Хранение списка достижений
    investment_mode = db.Column(db.String(20), default='moderate')
    safe_mode = db.Column(db.Boolean, default=True)
    linked_cards_json = db.Column(db.Text, default='[]')
    
    # Связи (История и Цели)
    history = db.relationship('Transaction', backref='user', lazy=True, cascade="all, delete-orphan")
    goals = db.relationship('Goal', backref='user', lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "balance": self.balance,
            "portfolio": self.portfolio,
            "deposit": self.deposit,
            "level": self.level,
            "exp": self.exp,
            "streak": self.streak,
            "rounding_limit": self.rounding_limit,
            "auto_sweep_threshold": self.auto_sweep_threshold,
            "referral_code": self.referral_code,
            "achievements": json.loads(self.achievements_json),
            "investment_mode": self.investment_mode,
            "safe_mode": self.safe_mode,
            "history": [{"time": t.timestamp.isoformat(), "type": t.type, "purchase": t.purchase_amount, "invested": t.invested_amount, "category": t.category} for t in self.history],
            "goals": [{"name": g.name, "target": g.target, "current": g.current, "icon": g.icon} for g in self.goals],
            "linked_cards": json.loads(self.linked_cards_json)
        }

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    type = db.Column(db.String(50)) 
    category = db.Column(db.String(50), default="Другое")
    purchase_amount = db.Column(db.Float)
    invested_amount = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Goal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100))
    target = db.Column(db.Float)
    current = db.Column(db.Float, default=0.0)
    icon = db.Column(db.String(10))