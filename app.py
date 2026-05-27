from flask import Flask, render_template, request, redirect, url_for, flash, session
from database import db, User, Transaction, Goal as DBGoal
from engine import InvestEngine
from ai_logic import AIAssistant
from functools import wraps
from datetime import timedelta
from dotenv import load_dotenv
import random
import os
import json
import string

# Загружаем переменные окружения из файла .env
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

base_dir = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=base_dir, static_folder=base_dir)

# Важно для Vercel: переменная 'application' должна быть доступна на уровне модуля
application = app

print(f">>> Application starting from: {base_dir} in {'Vercel' if os.getenv('VERCEL') else 'Local'} environment.")

# Проверка SECRET_KEY
app.secret_key = os.getenv('SECRET_KEY')
if not app.secret_key:
    if os.getenv('VERCEL'):
        raise RuntimeError("Критическая ошибка: SECRET_KEY не найден в переменных окружения Vercel!")
    print("WARNING: SECRET_KEY not found in environment variables. Using fallback.")
    app.secret_key = 'fallback_secret_key_for_dev' # Fallback for local development if .env is missing

app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

# Настройка базы данных
db_url = os.getenv('DATABASE_URL', 'sqlite:///app.db')

# Исправление для PostgreSQL на Vercel/Heroku
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
# Исправление для Vercel: SQLite не может писать в корень проекта
elif os.getenv('VERCEL') and db_url == 'sqlite:///app.db':
    db_url = 'sqlite:////tmp/app.db'

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

print(f">>> Database URI: {db_url.split('@')[-1] if '@' in db_url else 'SQLite'}")

# Создаем таблицы, если их нет
with app.app_context():
    try:
        db.create_all()
        # Проверка подключения к БД
        db.session.execute(db.text('SELECT 1'))
        print(">>> Database initialized and connected successfully.")
    except Exception as e:
        print(f">>> Database initialization or connection FAILED: {e}")

openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    print("ERROR: OPENAI_API_KEY is missing! AI features will not work.")

try:
    ai = AIAssistant(api_key=openai_api_key)
except Exception as e:
    print(f"Failed to initialize AIAssistant: {e}")
    ai = None # Предотвращаем падение всего приложения

def generate_ref_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def generate_captcha():
    num1 = random.randint(1, 10)
    num2 = random.randint(1, 10)
    session['captcha_answer'] = num1 + num2
    return f"{num1} + {num2}"

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            session.pop('username', None)
            return redirect(url_for('login'))
        # Проверяем, существует ли пользователь в базе (защита от сброса БД)
        user = db.session.get(User, session.get('user_id'))
        if not user:
            session.clear()
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
@login_required
def index():
    user = db.session.get(User, session.get('user_id'))
    if not user.nickname:
        return redirect(url_for('profile_setup'))

    finance = user.to_dict()
    advice = ai.get_advice(finance) if ai else "Советы временно недоступны."
    total_assets = user.balance + user.portfolio + user.deposit
    
    # Накопительный график: считаем рост суммы на основе всей истории
    chart_labels = []
    chart_values = []
    current_sum = 0
    for h in finance['history']:
        current_sum += h['invested']
        chart_labels.append(h['time'])
        chart_values.append(round(current_sum, 2))
    
    # Ограничиваем для первого показа последними 20 точками
    chart_labels = chart_labels[-20:]
    chart_values = chart_values[-20:]
    
    # Геймификация: Определение ранга на основе уровня
    if user.level <= 5:
        badge = {"name": "Новичок", "icon": "🥉"}
    elif user.level <= 15:
        badge = {"name": "Инвестор", "icon": "🥈"}
    else:
        badge = {"name": "Финансовый мастер", "icon": "🥇"}

    # Расчет процента роста (симуляция на основе последней инвестиции)
    growth_pct = 0
    if len(chart_values) >= 2:
        growth_pct = random.uniform(0.1, 2.5) 

    return render_template('index.html', data=finance, profile=user, advice=advice, 
                           pushes=[], badge=badge, 
                           growth_pct=growth_pct, total_assets=total_assets,
                           all_history=finance['history'],
                           chart_labels=chart_labels, chart_values=chart_values)

@app.route('/messages')
@login_required
def messages():
    user = db.session.get(User, session.get('user_id'))
    finance = user.to_dict()
    goals = finance.get('goals', [])
    primary_goal_name = goals[0]['name'] if goals else "цели"
    advice = ai.get_advice(finance) if ai else "Помощник офлайн."

    # Тестовые данные для уведомлений и напоминаний
    notifications = [
        {"icon": "bi-info-circle", "title": "Новый уровень!", "text": f"Вы достигли уровня {finance['level']}. Так держать!", "time": "1ч назад"},
        {"icon": "bi-shield-check", "title": "Безопасность", "text": "Ваш аккаунт защищен. Все системы в норме.", "time": "3ч назад"}
    ]
    
    reminders = [
        {"icon": "bi-calendar-event", "title": "Пополнение баланса", "text": "Не забудьте пополнить баланс после получения стипендии.", "date": "Скоро"},
        {"icon": "bi-bullseye", "title": "Цель близка", "text": f"До вашей цели '{primary_goal_name}' осталось совсем немного!", "date": "Сегодня"}
    ]

    return render_template('messages.html', 
                           advice=advice, 
                           notifications=notifications, 
                           reminders=reminders)

@app.route('/chat', methods=['GET', 'POST'])
@login_required
def chat():
    user = db.session.get(User, session.get('user_id'))
    finance = user.to_dict()
    
    if 'chat_history' not in session:
        session['chat_history'] = []
    
    if request.method == 'POST':
        user_message = request.form.get('message')
        if user_message and ai:
            bot_response = ai.get_chat_response(finance, user_message)
            history = list(session['chat_history'])
            history.append({'sender': 'user', 'text': user_message})
            history.append({'sender': 'bot', 'text': bot_response})
            session['chat_history'] = history[-20:] # Сохраняем последние 20 сообщений
            return redirect(url_for('chat'))
        elif not ai:
            flash("Чат временно недоступен (проверьте API ключ)", "warning")
            return redirect(url_for('chat'))

    return render_template('chat.html', chat_history=session['chat_history'])

@app.route('/history')
@login_required
def history():
    user = db.session.get(User, session.get('user_id'))
    finance = user.to_dict()
    # Передаем всю историю для отображения
    return render_template('history.html', history=finance.get('history', []))

@app.route('/chat/clear')
@login_required
def clear_chat():
    session.pop('chat_history', None)
    return redirect(url_for('chat'))

@app.route('/profile_setup', methods=['GET', 'POST'])
@login_required
def profile_setup():
    user = db.session.get(User, session.get('user_id'))
    if request.method == 'POST':
        user.nickname = request.form.get('nickname')
        user.address = request.form.get('address')
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('profile_setup.html')

@app.route('/profile')
@login_required
def profile():
    user = db.session.get(User, session.get('user_id'))
    if not user.referral_code:
        user.referral_code = generate_ref_code()
        db.session.commit()
    total_assets = user.balance + user.portfolio + user.deposit
    return render_template('profile.html', user=user, finance=user.to_dict(), total_assets=total_assets)

@app.route('/wallet')
@login_required
def wallet():
    user = db.session.get(User, session.get('user_id'))
    return render_template('wallet.html', user=user, finance=user.to_dict())

@app.route('/help')
@login_required
def help_page():
    user = db.session.get(User, session.get('user_id'))
    return render_template('help.html', user=user)

@app.route('/services')
@login_required
def services():
    user = db.session.get(User, session.get('user_id'))
    finance = user.to_dict()
    goals = finance.get("goals", [])
    goal = goals[0] if goals else {"name": "Мақсат", "target": 100000}
    progress = min((finance["portfolio"] / goal["target"]) * 100, 100) if goal['target'] > 0 else 0
    return render_template('services.html', data=finance, profile=user, progress=progress, goal=goal)

@app.route('/leaderboard')
@login_required
def leaderboard():
    users = User.query.all()
    all_users = [{'full_name': u.full_name, 'portfolio': u.portfolio, 'level': u.level} for u in users]
    # Портфель бойынша сұрыптау
    sorted_users = sorted(all_users, key=lambda x: x['portfolio'], reverse=True)
    return render_template('leaderboard.html', users=sorted_users)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        user_captcha = request.form.get('captcha')

        if not user_captcha or int(user_captcha) != session.get('captcha_answer'):
            flash("Неверная капча", "danger")
            return render_template('login.html', captcha=generate_captcha())

        user = User.query.filter_by(phone=phone).first()
        if user and user.check_password(password):
            session.permanent = True # Запоминаем пользователя
            session['user_id'] = user.id
            session['username'] = user.phone
            return redirect(url_for('index'))
        flash("Неверный логин или пароль", "danger")
    return render_template('login.html', captcha=generate_captcha())

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        full_name = request.form.get('full_name', '').strip()
        university = request.form.get('university', '').strip()
        ref_from = request.form.get('ref_code')

        # Валидация: проверяем длину пароля
        if len(password) < 6:
            flash("Пароль должен быть не менее 6 символов", "warning")
            return render_template('register.html')

        if User.query.filter_by(phone=phone).first():
            flash("Этот номер уже зарегистрирован", "danger")
        else:
            new_user = User(phone=phone, full_name=full_name, university=university)
            new_user.set_password(password)
            new_user.referral_code = generate_ref_code()
            
            # Логика реферала
            if ref_from:
                inviter = User.query.filter_by(referral_code=ref_from).first()
                if inviter:
                    inviter.referrals_count += 1
                    inviter.balance += 500 # Бонус пригласившему
                    new_user.balance += 200 # Бонус новичку
            
            db.session.add(new_user)
            db.session.commit()
            flash("Успешно! Теперь войдите.", "success")
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/purchase', methods=['POST'])
@login_required
def purchase():
    user = db.session.get(User, session.get('user_id'))
    engine = InvestEngine(user)
    try:
        amount = float(request.form.get('amount'))
        if amount <= 0:
            flash("Сумма покупки должна быть положительной", "warning")
            return redirect(url_for('index'))
            
        category = request.form.get('category', 'Другое')
        invested = engine.process_purchase(amount, category)
        if invested > 0:
            flash(f"Успешно! Инвестировано {invested:.2f} ₸.", "success")
        else:
            flash("Ошибка: Недостаточно средств на балансе!", "danger")
    except ValueError:
        flash("Ошибка: Введите корректную сумму.", "warning")
    return redirect(request.referrer or url_for('index'))

@app.route('/withdraw', methods=['POST'])
@login_required
def withdraw():
    user = db.session.get(User, session.get('user_id'))
    try:
        amount = float(request.form.get('amount'))
        if user.balance >= amount:
            user.balance -= amount
            db.session.commit()
            flash(f"Выведено {amount} ₸.", "success")
        else:
            flash("Недостаточно средств.", "danger")
    except ValueError:
        pass
    return redirect(url_for('wallet'))

@app.route('/deposit', methods=['POST'])
@login_required
def deposit():
    user = db.session.get(User, session.get('user_id'))
    try:
        amount = float(request.form.get('amount'))
        engine = InvestEngine(user)
        user.balance += amount
        engine.check_auto_sweep()
        db.session.commit()
        flash(f"Баланс пополнен на {amount} ₸.", "info")
    except ValueError:
        flash("Некорректная сумма.", "warning")
    return redirect(url_for('wallet'))

@app.route('/grow', methods=['POST'])
@login_required
def grow():
    user = db.session.get(User, session.get('user_id'))
    engine = InvestEngine(user)
    profit = engine.apply_market_growth()
    if profit >= 0:
        flash(f"Рынок вырос! Прибыль: {profit:.2f} ₸", "success")
    else:
        flash(f"Рынок упал! Убыток: {abs(profit):.2f} ₸", "warning")
    return redirect(url_for('index'))

@app.route('/change_mode', methods=['POST'])
@login_required
def change_mode():
    user = db.session.get(User, session.get('user_id'))
    mode = request.form.get('mode')
    if mode in ['conservative', 'moderate', 'aggressive']:
        user.investment_mode = mode
        db.session.commit()
        flash(f"Режим изменен: {mode}", "info")
    return redirect(url_for('services'))

# (Код сокращен для краткости, остальная логика остается прежней...)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)