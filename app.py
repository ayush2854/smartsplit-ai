from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from database import init_db, get_connection
from ai_helper import categorize_expense, get_spending_insights, calculate_settlements
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'smartsplit-secret-key-2025')

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access your groups.'

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, id, name, email):
        self.id = id
        self.name = name
        self.email = email

@login_manager.user_loader
def load_user(user_id):
    conn = get_connection()
    user = conn.execute(
        'SELECT * FROM users WHERE id = ?', (user_id,)
    ).fetchone()
    conn.close()
    if user:
        return User(user['id'], user['name'], user['email'])
    return None

# ── AUTH ROUTES ──

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']

        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return render_template('signup.html')

        conn = get_connection()
        existing = conn.execute(
            'SELECT id FROM users WHERE email = ?', (email,)
        ).fetchone()

        if existing:
            flash('An account with this email already exists.', 'error')
            conn.close()
            return render_template('signup.html')

        hashed = generate_password_hash(password)
        conn.execute(
            'INSERT INTO users (name, email, password) VALUES (?, ?, ?)',
            (name, email, hashed)
        )
        conn.commit()

        user = conn.execute(
            'SELECT * FROM users WHERE email = ?', (email,)
        ).fetchone()
        conn.close()

        login_user(User(user['id'], user['name'], user['email']))
        flash(f'Welcome, {name}! Your account has been created.', 'success')
        return redirect(url_for('index'))

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']

        conn = get_connection()
        user = conn.execute(
            'SELECT * FROM users WHERE email = ?', (email,)
        ).fetchone()
        conn.close()

        if not user or not check_password_hash(user['password'], password):
            flash('Invalid email or password.', 'error')
            return render_template('login.html')

        login_user(User(user['id'], user['name'], user['email']))
        return redirect(url_for('index'))

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ── MAIN ROUTES ──

@app.route('/')
@login_required
def index():
    conn = get_connection()
    groups = conn.execute(
        'SELECT * FROM groups WHERE user_id = ? ORDER BY created_at DESC',
        (current_user.id,)
    ).fetchall()
    conn.close()
    return render_template('index.html', groups=groups)

@app.route('/create-group', methods=['POST'])
@login_required
def create_group():
    name = request.form['name']
    members = request.form['members']
    conn = get_connection()
    conn.execute(
        'INSERT INTO groups (user_id, name, members) VALUES (?, ?, ?)',
        (current_user.id, name, members)
    )
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/group/<int:group_id>')
@login_required
def group(group_id):
    conn = get_connection()
    grp = conn.execute(
        'SELECT * FROM groups WHERE id = ? AND user_id = ?',
        (group_id, current_user.id)
    ).fetchone()

    if not grp:
        flash('Group not found.', 'error')
        return redirect(url_for('index'))

    expenses = conn.execute(
        'SELECT * FROM expenses WHERE group_id = ? ORDER BY created_at DESC',
        (group_id,)
    ).fetchall()
    conn.close()

    expenses_list = [dict(e) for e in expenses]
    settlements = calculate_settlements(expenses_list, grp['members'])

    category_totals = {}
    for e in expenses_list:
        cat = e['category']
        category_totals[cat] = category_totals.get(cat, 0) + e['amount']

    return render_template('group.html',
        group=grp,
        expenses=expenses_list,
        settlements=settlements,
        category_totals=category_totals
    )

@app.route('/add-expense/<int:group_id>', methods=['POST'])
@login_required
def add_expense(group_id):
    conn = get_connection()
    grp = conn.execute(
        'SELECT * FROM groups WHERE id = ? AND user_id = ?',
        (group_id, current_user.id)
    ).fetchone()
    if not grp:
        return redirect(url_for('index'))

    description = request.form['description']
    amount = float(request.form['amount'])
    paid_by = request.form['paid_by']
    category = categorize_expense(description, amount)

    conn.execute(
        'INSERT INTO expenses (group_id, description, amount, paid_by, category) VALUES (?, ?, ?, ?, ?)',
        (group_id, description, amount, paid_by, category)
    )
    conn.commit()
    conn.close()
    return redirect(url_for('group', group_id=group_id))

@app.route('/insights/<int:group_id>')
@login_required
def insights(group_id):
    conn = get_connection()
    grp = conn.execute(
        'SELECT * FROM groups WHERE id = ? AND user_id = ?',
        (group_id, current_user.id)
    ).fetchone()
    if not grp:
        return redirect(url_for('index'))

    expenses = conn.execute(
        'SELECT * FROM expenses WHERE group_id = ?', (group_id,)
    ).fetchall()
    conn.close()

    expenses_list = [dict(e) for e in expenses]
    ai_insight = get_spending_insights(expenses_list, grp['name'])
    return render_template('insights.html', group=grp, insight=ai_insight)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)

init_db()