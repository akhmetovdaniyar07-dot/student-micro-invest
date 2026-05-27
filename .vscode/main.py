import os
from app import app, db, User
from engine import InvestEngine # type: ignore
from ai_logic import AIAssistant # type: ignore

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def main():
    ai = AIAssistant()

    with app.app_context():
        print("STUDENT.INVEST Terminal Login")
        phone = input("Телефон: ").strip()
        password = input("Пароль: ")
        
        user = User.query.filter_by(phone=phone).first()
        if not user or not user.check_password(password):
            print("Қате логин немесе құпия сөз!")
            return

        engine = InvestEngine(user)

        while True:
            clear_screen()
            # Получаем свежие данные
            db.session.refresh(user)
            data = user.to_dict()
            
            print("="*40)
            print(f" STUDENT.INVEST: {user.full_name} ")
            print("="*40)
            print(f" Уровень: {user.level} | EXP: {user.exp}/100")
            print(f" Банковский баланс: {user.balance:.2f} ₸")
            print(f" Стоимость портфеля: {user.portfolio:.2f} ₸")
            print(f" Лимит округления: {user.rounding_limit} ₸")
        
            # Отображение первой цели из списка
            goals = data.get("goals", [])
            goal = goals[0] if goals else {"name": "Цель", "target": 100000}
            
            progress = (data["portfolio"] / goal["target"]) * 100 if goal['target'] > 0 else 0
            print(f" Цель: {goal['name']} ({format(progress, '.1f')}%)")
            print(f" [{'#' * int(progress/5)}{'.' * (20 - int(progress/5))}]")
            
            print("-" * 40)
            print(ai.get_advice(data))
            print("-" * 40)
            
            print("\nМеню:")
            print("1. Симуляция покупки (транзакция)")
            print("2. Изменить лимит округления")
            print("3. Симуляция роста рынка (+1%)")
            print("4. История транзакций")
            print("5. Пополнить баланс (Стипендия)")
            print("6. Поставить новую цель")
            print("0. Выход")
            
            choice = input("\nВаш выбор: ")

            if choice == "1":
                try:
                    amt = float(input("Введите сумму покупки (напр., 870): "))
                    invested = engine.process_purchase(amt)
                    if invested > 0:
                        print(f"\nУспешно! {invested} ₸ отправлено в инвест-фонд.")
                    else:
                        print("\nОшибка: Недостаточно средств на балансе!")
                    input("\nНажмите Enter, чтобы продолжить...")
                except ValueError:
                    print("Ошибка: Введите число.")
                    input()

            elif choice == "2":
                print("\nЛимиты: 10, 50, 100, 500, 1000")
                new_limit = input("Новый лимит: ")
                if new_limit in ["10", "50", "100", "500", "1000"]:
                    user.rounding_limit = int(new_limit)
                    db.session.commit()
                    print("Лимит изменен!")
                else:
                    print("Неверный лимит.")
                input()

            elif choice == "3":
                profit = engine.apply_market_growth()
                print(f"\nРынок вырос! Ваш портфель принес прибыль {profit:.2f} ₸.")
                input("\nНажмите Enter, чтобы продолжить...")

            elif choice == "4":
                print("\n--- ПОСЛЕДНИЕ ТРАНЗАКЦИИ ---")
                for item in data['history'][-5:]:
                    print(f"Покупка: {item['purchase']} ₸ | Инвестиция: {item['invested']} ₸")
                input("\nНажмите Enter, чтобы продолжить...")

            elif choice == "5":
                try:
                    dep = float(input("На какую сумму пополнить? "))
                    user.balance += dep
                    db.session.commit()
                    print("Баланс пополнен!")
                except ValueError:
                    print("Некорректное число.")
                input()

            elif choice == "6":
                name = input("Название цели: ")
                target = float(input("Сумма цели: "))
                
                if user.goals:
                    user.goals[0].name = name
                    user.goals[0].target = target
                else:
                    from database import Goal as DBGoal
                    new_goal = DBGoal(user_id=user.id, name=name, target=target, current=0, icon="🎯")
                    db.session.add(new_goal)
                    
                db.session.commit()
                print("Цель изменена!")
                input()

            elif choice == "0":
                print("До свидания!")
                break

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nПрограмма остановлена. До свидания!")
