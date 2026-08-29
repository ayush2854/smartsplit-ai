from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from database import init_db, get_connection
from ai_helper import categorize_expense, get_spending_insights, calculate_settlements, analyze_receipt
from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response
from pdf_generator import generate_settlement_pdf
from flask_jwt_extended import JWTManager
from api import api as api_blueprint
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'smartsplit-secret-key-2025')
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'smartsplit-jwt-secret-2025')

jwt = JWTManager(app)
app.register_blueprint(api_blueprint)

# Call init_db() directly when the application starts
init_db()

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
        conn.close()
        flash('Group not found.', 'error')
        return redirect(url_for('index'))

    expenses = conn.execute(
        'SELECT * FROM expenses WHERE group_id = ? ORDER BY created_at DESC',
        (group_id,)
    ).fetchall()
    conn.close()

    expenses_list = [dict(e) for e in expenses]
    settlements = calculate_settlements(expenses_list, grp['members'])
    category_totals = get_category_totals(group_id)

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
        conn.close()
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
        conn.close()
        return redirect(url_for('index'))

    expenses = conn.execute(
        'SELECT * FROM expenses WHERE group_id = ?', (group_id,)
    ).fetchall()
    conn.close()

    expenses_list = [dict(e) for e in expenses]
    ai_insight = get_spending_insights(expenses_list, grp['name'])
    return render_template('insights.html', group=grp, insight=ai_insight)

@app.route('/edit-expense/<int:expense_id>', methods=['GET', 'POST'])
@login_required
def edit_expense(expense_id):
    conn = get_connection()

    # Get expense and verify it belongs to current user's group
    expense = conn.execute('''
        SELECT e.* FROM expenses e
        JOIN groups g ON e.group_id = g.id
        WHERE e.id = ? AND g.user_id = ?
    ''', (expense_id, current_user.id)).fetchone()

    if not expense:
        conn.close()
        flash('Expense not found.', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        description = request.form['description']
        amount = float(request.form['amount'])
        paid_by = request.form['paid_by']

        # Re-categorize with AI since description may have changed
        category = categorize_expense(description, amount)

        conn.execute('''
            UPDATE expenses
            SET description = ?, amount = ?, paid_by = ?, category = ?
            WHERE id = ?
        ''', (description, amount, paid_by, category, expense_id))
        conn.commit()
        conn.close()

        flash('Expense updated successfully.', 'success')
        return redirect(url_for('group', group_id=expense['group_id']))

    conn.close()
    return render_template('edit_expense.html', expense=expense)

@app.route('/delete-expense/<int:expense_id>', methods=['POST'])
@login_required
def delete_expense(expense_id):
    conn = get_connection()

    # Verify expense belongs to current user's group
    expense = conn.execute('''
        SELECT e.* FROM expenses e
        JOIN groups g ON e.group_id = g.id
        WHERE e.id = ? AND g.user_id = ?
    ''', (expense_id, current_user.id)).fetchone()

    if not expense:
        conn.close()
        flash('Expense not found.', 'error')
        return redirect(url_for('index'))

    group_id = expense['group_id']
    conn.execute('DELETE FROM expenses WHERE id = ?', (expense_id,))
    conn.commit()
    conn.close()

    flash('Expense deleted.', 'success')
    return redirect(url_for('group', group_id=group_id))

@app.route('/scan-receipt/<int:group_id>', methods=['POST'])
@login_required
def scan_receipt(group_id):
    conn = get_connection()
    grp = conn.execute(
        'SELECT * FROM groups WHERE id = ? AND user_id = ?',
        (group_id, current_user.id)
    ).fetchone()

    if not grp:
        conn.close()
        return redirect(url_for('index'))

    if 'receipt' not in request.files or request.files['receipt'].filename == '':
        conn.close()
        flash('⚠️ Please select an image before clicking Scan.', 'error')
        return redirect(url_for('group', group_id=group_id))

    file = request.files['receipt']

    # Check file type
    allowed = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    extension = file.filename.rsplit('.', 1)[-1].lower()
    if extension not in allowed:
        conn.close()
        flash('Please upload an image file (JPG, PNG, etc.)', 'error')
        return redirect(url_for('group', group_id=group_id))

    # Analyze with AI
    result = analyze_receipt(file)

    # Fetch remaining data for template render
    expenses = conn.execute(
        'SELECT * FROM expenses WHERE group_id = ? ORDER BY created_at DESC',
        (group_id,)
    ).fetchall()
    expenses_list = [dict(e) for e in expenses]
    
    conn.close()

    # Send extracted data back to the group page for confirmation
    return render_template('group.html',
        group=grp,
        expenses=expenses_list,
        settlements=calculate_settlements(expenses_list, grp['members']),
        category_totals=get_category_totals(group_id),
        scanned=result
    )

def get_category_totals(group_id):
    conn = get_connection()
    expenses = conn.execute(
        'SELECT * FROM expenses WHERE group_id = ?', (group_id,)
    ).fetchall()
    conn.close()
    totals = {}
    for e in expenses:
        totals[e['category']] = totals.get(e['category'], 0) + e['amount']
    return totals

@app.route('/export-pdf/<int:group_id>')
@login_required
def export_pdf(group_id):
    conn = get_connection()
    grp = conn.execute(
        'SELECT * FROM groups WHERE id = ? AND user_id = ?',
        (group_id, current_user.id)
    ).fetchone()

    if not grp:
        flash('Group not found.', 'error')
        return redirect(url_for('index'))

    expenses = conn.execute(
        'SELECT * FROM expenses WHERE group_id = ? ORDER BY created_at ASC',
        (group_id,)
    ).fetchall()
    conn.close()

    expenses_list = [dict(e) for e in expenses]
    settlements = calculate_settlements(expenses_list, grp['members'])
    category_totals = get_category_totals(group_id)

    pdf_buffer = generate_settlement_pdf(
        dict(grp), expenses_list, settlements, category_totals
    )

    response = make_response(pdf_buffer.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = \
        f'attachment; filename="{grp["name"]}_settlement.pdf"'
    return response

if __name__ == '__main__':
    init_db()
    app.run(debug=True)