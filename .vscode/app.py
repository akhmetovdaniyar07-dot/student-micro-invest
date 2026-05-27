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

app = Flask(__name__, template_folder='.', static_folder='.')
app.secret_key = os.getenv('SECRET_KEY', 'fallback_secret_key_for_dev')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

# Настройка базы данных
db_url = os.getenv('DATABASE_URL', 'sqlite:///app.db')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# Создаем таблицы
with app.app_context():
    try:
        db.create_all()
    except Exception as e:
        print(f"Database sync error: {e}")

ai = AIAssistant(api_key=os.getenv("OPENAI_API_KEY"))

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
    advice = ai.get_advice(finance)
    total_assets = user.balance + user.portfolio + user.deposit
    
    chart_labels = []
    chart_values = []
    current_sum = 0
    for h in finance['history']:
        current_sum += h['invested']
        chart_labels.append(h['time'])
        chart_values.append(round(current_sum, 2))
    
    chart_labels = chart_labels[-20:]
    chart_values = chart_values[-20:]
    
    if user.level <= 5:
        badge = {"name": "Новичок", "icon": "🥉"}
    elif user.level <= 15:
        badge = {"name": "Инвестор", "icon": "🥈"}
    else:
        badge = {"name": "Финансовый мастер", "icon": "🥇"}

    growth_pct = random.uniform(0.1, 2.5) if len(chart_values) >= 2 else 0

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
    advice = ai.get_advice(finance)
    notifications = [
        {"icon": "bi-info-circle", "title": "Новый уровень!", "text": f"Вы достигли уровня {finance['level']}.", "time": "1ч назад"},
        {"icon": "bi-shield-check", "title": "Безопасность", "text": "Ваш аккаунт защищен.", "time": "3ч назад"}
    ]
    reminders = [
        {"icon": "bi-calendar-event", "title": "Пополнение баланса", "text": "Не забудьте про стипендию.", "date": "Скоро"}
    ]
    return render_template('messages.html', advice=advice, notifications=notifications, reminders=reminders)

@app.route('/chat', methods=['GET', 'POST'])
@login_required
def chat():
    user = db.session.get(User, session.get('user_id'))
    if 'chat_history' not in session: session['chat_history'] = []
    if request.method == 'POST':
        msg = request.form.get('message')
        if msg:
            res = ai.get_chat_response(user.to_dict(), msg)
            history = list(session['chat_history'])
            history.append({'sender': 'user', 'text': msg})
            history.append({'sender': 'bot', 'text': res})
            session['chat_history'] = history[-20:]
            return redirect(url_for('chat'))
    return render_template('chat.html', chat_history=session['chat_history'])

@app.route('/history')
@login_required
def history():
    user = db.session.get(User, session.get('user_id'))
    return render_template('history.html', history=user.to_dict().get('history', []))

@app.route('/chat/clear_receipt')
@login_required
def clear_receipt():
    session.pop('last_receipt', None)
    return "OK", 200

@app.route('/profile_setup', methods=['GET', 'POST'])
@login_required
def profile_setup():
    user = db.session.get(User, session.get('user_id'))
    if request.method == 'POST':
        user.nickname = request.form.get('nickname')
        user.address = request.form.get('address')
        user.university = request.form.get('university')
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
    stats = {}
    for tx in user.history:
        if tx.type == 'round_up':
            cat = tx.category or "Другое"
            stats[cat] = stats.get(cat, 0) + tx.purchase_amount
    achievements = [
        {"id": "first_1k", "icon": "💰", "name": "Первая тысяча", "text": "Накоплено 1,000 ₸", "active": user.portfolio >= 1000},
        {"id": "streak_7", "icon": "🔥", "name": "Неделя", "text": "Серия 7 дней", "active": user.streak >= 7},
        {"id": "level_5", "icon": "🎓", "name": "Магистр", "text": "Достигнут 5 уровень", "active": user.level >= 5}
    ]
    total_assets = user.balance + user.portfolio + user.deposit
    return render_template('profile.html', user=user, finance=user.to_dict(), total_assets=total_assets, 
                           cat_labels=list(stats.keys()), cat_values=list(stats.values()), achievements=achievements)

@app.route('/leaderboard')
@login_required
def leaderboard():
    user = db.session.get(User, session.get('user_id'))
    show_my_uni = request.args.get('filter') == 'my_uni'
    sort_by = request.args.get('sort', 'portfolio')
    query = User.query
    if show_my_uni and user.university: query = query.filter_by(university=user.university)
    if sort_by == 'university':
        users = query.order_by(User.university.asc(), User.portfolio.desc()).limit(50).all()
    else:
        users = query.order_by(User.portfolio.desc()).limit(50).all()
    return render_template('leaderboard.html', users=users, current_user=user, is_filtered=show_my_uni, current_sort=sort_by)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        captcha = request.form.get('captcha')
        if not captcha or int(captcha) != session.get('captcha_answer'):
            flash("Неверная капча", "danger")
            return render_template('login.html', captcha=generate_captcha())
        user = User.query.filter_by(phone=phone).first()
        if user and user.check_password(password):
            session.permanent = True
            session['user_id'] = user.id
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
        if len(password) < 6:
            flash("Пароль слишком короткий", "warning")
            return render_template('register.html')
        if User.query.filter_by(phone=phone).first():
            flash("Номер уже занят", "danger")
        else:
            new_user = User(phone=phone, full_name=full_name, university=university)
            new_user.set_password(password)
            new_user.referral_code = generate_ref_code()
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/purchase', methods=['POST'])
@login_required
def purchase():
    user = db.session.get(User, session.get('user_id'))
    engine = InvestEngine(user)
    try:
        amt = float(request.form.get('amount'))
        cat = request.form.get('category', 'Другое')
        res = engine.process_purchase(amt, cat)
        if res['status'] == 'success':
            session['last_receipt'] = res
            flash("Успешно инвестировано!", "success")
        else:
            flash("Ошибка транзакции", "danger")
    except: flash("Ошибка суммы", "warning")
    return redirect(url_for('index'))

@app.route('/grow', methods=['POST'])
@login_required
def grow():
    InvestEngine(db.session.get(User, session.get('user_id'))).apply_market_growth()
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(e):
    db.session.rollback()
    return render_template('500.html'), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
