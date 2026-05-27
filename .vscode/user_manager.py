import json
import os
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

class UserManager:
    def __init__(self):
        base_path = os.path.dirname(os.path.abspath(__file__))
        self.filename = os.path.join(base_path, "student_data.json")
        self.users = self.load_users()

    def load_users(self):
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r', encoding='utf-8') as f:
                    users = json.load(f)
                    # Миграция: добавляем недостающие поля для старых пользователей
                    for user in users.values():
                        finance = user.get('finance', {})
                        if 'deposit' not in finance:
                            finance['deposit'] = 0.0
                        if 'goals' not in finance:
                            finance['goals'] = []
                    return users
        except (json.JSONDecodeError, IOError):
            pass
        return {}

    def create_user(self, phone, password, full_name, university):
        if phone in self.users:
            return False
        self.users[phone] = {
            "password": generate_password_hash(password),
            "profile": {
                "full_name": full_name, 
                "university": university,
                "kyc_status": "Не верифицирован",
                "phone": phone,
                "nickname": "",
                "address": ""
            },
            "finance": {
                "balance": 0.0,
                "portfolio": 0.0,
                "deposit": 0.0,
                "rounding_limit": 100,
                "history": [],
                "portfolio_history": [],
                "level": 1,
                "exp": 0,
                "streak": 0,
                "last_active": "",
                "friends": [],
                "goals": [
                    {"name": "Ноутбук", "target": 200000, "current": 80000, "icon": "🎓"},
                    {"name": "Путешествие", "target": 500000, "current": 125000, "icon": "✈️"}
                ],
                "investment_mode": "moderate",
                "safe_mode": True,
                "linked_cards": []
            },
            "security": {"pin_enabled": False, "biometrics_sim": False}
        }
        self.save()
        return True

    def update_streak(self, phone):
        user = self.users.get(phone)
        if not user: return
        
        finance = user["finance"]
        now = datetime.now()
        last_active_str = finance.get("last_active")
        
        if last_active_str:
            last_active = datetime.strptime(last_active_str, "%Y-%m-%d")
            diff = (now.date() - last_active.date()).days
            
            if diff == 1:
                finance["streak"] += 1
            elif diff > 1:
                finance["streak"] = 1
        else:
            finance["streak"] = 1
            
        finance["last_active"] = now.strftime("%Y-%m-%d")
        self.save()

    def verify_user(self, phone, password):
        user = self.users.get(phone)
        if user and check_password_hash(user['password'], password):
            return user
        return None

    def save(self):
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(self.users, f, ensure_ascii=False, indent=4)