from flask import Flask, render_template, request, redirect, url_for, jsonify
from database import init_db, get_connection
from ai_helper import categorize_expense, get_spending_insights, calculate_settlements

app = Flask(__name__)

@app.route('/')
def index():
    conn = get_connection()
    groups = conn.execute('SELECT * FROM groups ORDER BY created_at DESC').fetchall()
    conn.close()
    return render_template('index.html', groups=groups)

@app.route('/create-group', methods=['POST'])
def create_group():
    name = request.form['name']
    members = request.form['members']
    conn = get_connection()
    conn.execute('INSERT INTO groups (name, members) VALUES (?, ?)', (name, members))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/group/<int:group_id>')
def group(group_id):
    conn = get_connection()
    grp = conn.execute('SELECT * FROM groups WHERE id = ?', (group_id,)).fetchone()
    expenses = conn.execute(
        'SELECT * FROM expenses WHERE group_id = ? ORDER BY created_at DESC',
        (group_id,)
    ).fetchall()
    conn.close()

    expenses_list = [dict(e) for e in expenses]
    members = grp['members']
    settlements = calculate_settlements(expenses_list, members)

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
def add_expense(group_id):
    description = request.form['description']
    amount = float(request.form['amount'])
    paid_by = request.form['paid_by']

    # AI categorizes the expense automatically
    category = categorize_expense(description, amount)

    conn = get_connection()
    conn.execute(
        'INSERT INTO expenses (group_id, description, amount, paid_by, category) VALUES (?, ?, ?, ?, ?)',
        (group_id, description, amount, paid_by, category)
    )
    conn.commit()
    conn.close()
    return redirect(url_for('group', group_id=group_id))

@app.route('/insights/<int:group_id>')
def insights(group_id):
    conn = get_connection()
    grp = conn.execute('SELECT * FROM groups WHERE id = ?', (group_id,)).fetchone()
    expenses = conn.execute(
        'SELECT * FROM expenses WHERE group_id = ?', (group_id,)
    ).fetchall()
    conn.close()

    expenses_list = [dict(e) for e in expenses]
    ai_insight = get_spending_insights(expenses_list, grp['name'])

    return render_template('insights.html', group=grp, insight=ai_insight)

if __name__ == '__main__':
    init_db()
    app.run(debug=False)

# This runs init_db when gunicorn starts the app too
init_db()