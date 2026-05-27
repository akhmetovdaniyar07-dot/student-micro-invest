import math
import random
import string
from datetime import datetime
from database import db, Transaction

class InvestEngine:
    def __init__(self, db_user):
        self.user = db_user

    def process_purchase(self, amount, category="Другое"):
        limit = self.user.rounding_limit

        # "Student Safe Mode" фишка
        # Если баланс < 2000 ₸ и включен Safe Mode, минимизируем инвестиции до округления по 10 ₸
        if self.user.safe_mode and self.user.balance < 2000:
            limit = 10
        
        # Логика округления: например, 870 -> 1000
        rounded_amount = math.ceil(amount / limit) * limit
        if rounded_amount == amount: # Если сумма уже круглая, добавляем шаг лимита
            rounded_amount += limit
            
        round_up = rounded_amount - amount
        tx_id = "TX-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        # Проверка: есть ли деньги на балансе для инвестиции?
        if self.user.balance < round_up:
            return {
                "status": "insufficient_funds",
                "invested": 0,
                "amount": amount,
                "id": tx_id
            }

        # Обновляем данные
        self.user.balance -= round_up
        self.user.portfolio += round_up
        self.user.exp += 5
        
        new_tx = Transaction(user_id=self.user.id, type="round_up", 
                             purchase_amount=amount, invested_amount=round_up,
                             category=category)
        db.session.add(new_tx)
        
        # Проверка уровня
        leveled_up = False
        if self.user.exp >= 100:
            self.user.level += 1
            self.user.exp = 0
            leveled_up = True
            
        self.check_auto_sweep()
        db.session.commit()

        return {
            "status": "success",
            "invested": round_up,
            "rounded": rounded_amount,
            "amount": amount,
            "id": tx_id,
            "leveled_up": leveled_up,
            "new_level": self.user.level
        }

    def check_auto_sweep(self):
        """Автоматический перевод излишков в депозит (10к или 30к)"""
        balance = self.user.balance
        surplus = 0

        if balance > 30000:
            surplus = balance - 30000
            self.user.balance = 30000
        elif balance > 10000:
            surplus = balance - 10000
            self.user.balance = 10000

        if surplus > 0:
            self.user.deposit += surplus
            new_tx = Transaction(user_id=self.user.id, type="auto_deposit", 
                                 purchase_amount=0, invested_amount=round(surplus, 2))
            db.session.add(new_tx)

    def apply_market_growth(self):
        """Симуляция роста рынка в зависимости от режима"""
        mode = self.user.investment_mode
        
        if mode == "conservative":
            # Стабильный рост, очень редкие и мелкие просадки
            multiplier = random.uniform(-0.0002, 0.0012) 
        elif mode == "moderate":
            # Умеренные колебания: от -0.15% до +0.45%
            multiplier = random.uniform(-0.0015, 0.0045)
        else: # aggressive
            # Высокая волатильность: риск упасть на 1% или вырасти на 2.5%
            multiplier = random.uniform(-0.01, 0.025)

        profit = self.user.portfolio * multiplier
        self.user.portfolio += profit
        
        if self.user.portfolio < 0:
            self.user.portfolio = 0
            
        db.session.commit()
        return profit

    def record_snapshot(self): pass
