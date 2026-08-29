from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required, get_jwt_identity
)
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_connection
from ai_helper import categorize_expense, get_spending_insights, calculate_settlements

# Blueprint — keeps all API routes organized separately from main app
api = Blueprint('api', __name__, url_prefix='/api')


# ── HELPER FUNCTIONS ──

def get_category_totals_api(group_id):
    conn = get_connection()
    expenses = conn.execute(
        'SELECT * FROM expenses WHERE group_id = ?', (group_id,)
    ).fetchall()
    conn.close()
    totals = {}
    for e in expenses:
        totals[e['category']] = totals.get(e['category'], 0) + e['amount']
    return totals

def error_response(message, status_code):
    return jsonify({'success': False, 'error': message}), status_code

def success_response(data, status_code=200):
    return jsonify({'success': True, **data}), status_code


# ── AUTH ENDPOINTS ──

@api.route('/auth/register', methods=['POST'])
def api_register():
    data = request.get_json()

    if not data:
        return error_response('Request body must be JSON', 400)

    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not name or not email or not password:
        return error_response('Name, email and password are required', 400)

    if len(password) < 6:
        return error_response('Password must be at least 6 characters', 400)

    conn = get_connection()
    existing = conn.execute(
        'SELECT id FROM users WHERE email = ?', (email,)
    ).fetchone()

    if existing:
        conn.close()
        return error_response('Email already registered', 409)

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

    token = create_access_token(identity=str(user['id']))

    return success_response({
        'message': 'Account created successfully',
        'token': token,
        'user': {
            'id': user['id'],
            'name': user['name'],
            'email': user['email']
        }
    }, 201)


@api.route('/auth/login', methods=['POST'])
def api_login():
    data = request.get_json()

    if not data:
        return error_response('Request body must be JSON', 400)

    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return error_response('Email and password are required', 400)

    conn = get_connection()
    user = conn.execute(
        'SELECT * FROM users WHERE email = ?', (email,)
    ).fetchone()
    conn.close()

    if not user or not check_password_hash(user['password'], password):
        return error_response('Invalid email or password', 401)

    token = create_access_token(identity=str(user['id']))

    return success_response({
        'message': 'Login successful',
        'token': token,
        'user': {
            'id': user['id'],
            'name': user['name'],
            'email': user['email']
        }
    })


# ── GROUP ENDPOINTS ──

@api.route('/groups', methods=['GET'])
@jwt_required()
def api_get_groups():
    user_id = int(get_jwt_identity())
    conn = get_connection()
    groups = conn.execute(
        'SELECT * FROM groups WHERE user_id = ? ORDER BY created_at DESC',
        (user_id,)
    ).fetchall()
    conn.close()

    return success_response({
        'groups': [{
            'id': g['id'],
            'name': g['name'],
            'members': g['members'],
            'created_at': g['created_at']
        } for g in groups]
    })


@api.route('/groups', methods=['POST'])
@jwt_required()
def api_create_group():
    user_id = int(get_jwt_identity())
    data = request.get_json()

    if not data:
        return error_response('Request body must be JSON', 400)

    name = data.get('name', '').strip()
    members = data.get('members', '').strip()

    if not name or not members:
        return error_response('Group name and members are required', 400)

    conn = get_connection()
    cursor = conn.execute(
        'INSERT INTO groups (user_id, name, members) VALUES (?, ?, ?)',
        (user_id, name, members)
    )
    group_id = cursor.lastrowid
    conn.commit()

    group = conn.execute(
        'SELECT * FROM groups WHERE id = ?', (group_id,)
    ).fetchone()
    conn.close()

    return success_response({
        'message': 'Group created successfully',
        'group': {
            'id': group['id'],
            'name': group['name'],
            'members': group['members'],
            'created_at': group['created_at']
        }
    }, 201)


@api.route('/groups/<int:group_id>', methods=['GET'])
@jwt_required()
def api_get_group(group_id):
    user_id = int(get_jwt_identity())
    conn = get_connection()

    grp = conn.execute(
        'SELECT * FROM groups WHERE id = ? AND user_id = ?',
        (group_id, user_id)
    ).fetchone()

    if not grp:
        conn.close()
        return error_response('Group not found', 404)

    expenses = conn.execute(
        'SELECT * FROM expenses WHERE group_id = ? ORDER BY created_at DESC',
        (group_id,)
    ).fetchall()
    conn.close()

    expenses_list = [dict(e) for e in expenses]
    settlements = calculate_settlements(expenses_list, grp['members'])
    category_totals = get_category_totals_api(group_id)
    total = sum(e['amount'] for e in expenses_list)

    return success_response({
        'group': {
            'id': grp['id'],
            'name': grp['name'],
            'members': grp['members'],
            'created_at': grp['created_at']
        },
        'expenses': expenses_list,
        'settlements': settlements,
        'summary': {
            'total_amount': total,
            'total_expenses': len(expenses_list),
            'category_totals': category_totals
        }
    })


# ── EXPENSE ENDPOINTS ──

@api.route('/groups/<int:group_id>/expenses', methods=['POST'])
@jwt_required()
def api_add_expense(group_id):
    user_id = int(get_jwt_identity())
    conn = get_connection()

    grp = conn.execute(
        'SELECT * FROM groups WHERE id = ? AND user_id = ?',
        (group_id, user_id)
    ).fetchone()

    if not grp:
        conn.close()
        return error_response('Group not found', 404)

    data = request.get_json()
    if not data:
        return error_response('Request body must be JSON', 400)

    description = data.get('description', '').strip()
    amount = data.get('amount')
    paid_by = data.get('paid_by', '').strip()

    if not description or amount is None or not paid_by:
        return error_response('Description, amount and paid_by are required', 400)

    try:
        amount = float(amount)
    except:
        return error_response('Amount must be a number', 400)

    # AI categorization
    category = categorize_expense(description, amount)

    cursor = conn.execute(
        'INSERT INTO expenses (group_id, description, amount, paid_by, category) VALUES (?, ?, ?, ?, ?)',
        (group_id, description, amount, paid_by, category)
    )
    expense_id = cursor.lastrowid
    conn.commit()

    expense = conn.execute(
        'SELECT * FROM expenses WHERE id = ?', (expense_id,)
    ).fetchone()
    conn.close()

    return success_response({
        'message': 'Expense added successfully',
        'expense': dict(expense)
    }, 201)


@api.route('/expenses/<int:expense_id>', methods=['PUT'])
@jwt_required()
def api_edit_expense(expense_id):
    user_id = int(get_jwt_identity())
    conn = get_connection()

    expense = conn.execute('''
        SELECT e.* FROM expenses e
        JOIN groups g ON e.group_id = g.id
        WHERE e.id = ? AND g.user_id = ?
    ''', (expense_id, user_id)).fetchone()

    if not expense:
        conn.close()
        return error_response('Expense not found', 404)

    data = request.get_json()
    if not data:
        return error_response('Request body must be JSON', 400)

    description = data.get('description', expense['description']).strip()
    amount = float(data.get('amount', expense['amount']))
    paid_by = data.get('paid_by', expense['paid_by']).strip()

    # Re-categorize with AI
    category = categorize_expense(description, amount)

    conn.execute('''
        UPDATE expenses
        SET description = ?, amount = ?, paid_by = ?, category = ?
        WHERE id = ?
    ''', (description, amount, paid_by, category, expense_id))
    conn.commit()

    updated = conn.execute(
        'SELECT * FROM expenses WHERE id = ?', (expense_id,)
    ).fetchone()
    conn.close()

    return success_response({
        'message': 'Expense updated successfully',
        'expense': dict(updated)
    })


@api.route('/expenses/<int:expense_id>', methods=['DELETE'])
@jwt_required()
def api_delete_expense(expense_id):
    user_id = int(get_jwt_identity())
    conn = get_connection()

    expense = conn.execute('''
        SELECT e.* FROM expenses e
        JOIN groups g ON e.group_id = g.id
        WHERE e.id = ? AND g.user_id = ?
    ''', (expense_id, user_id)).fetchone()

    if not expense:
        conn.close()
        return error_response('Expense not found', 404)

    conn.execute('DELETE FROM expenses WHERE id = ?', (expense_id,))
    conn.commit()
    conn.close()

    return success_response({'message': 'Expense deleted successfully'})


# ── INSIGHTS ENDPOINT ──

@api.route('/groups/<int:group_id>/insights', methods=['GET'])
@jwt_required()
def api_get_insights(group_id):
    user_id = int(get_jwt_identity())
    conn = get_connection()

    grp = conn.execute(
        'SELECT * FROM groups WHERE id = ? AND user_id = ?',
        (group_id, user_id)
    ).fetchone()

    if not grp:
        conn.close()
        return error_response('Group not found', 404)

    expenses = conn.execute(
        'SELECT * FROM expenses WHERE group_id = ?', (group_id,)
    ).fetchall()
    conn.close()

    expenses_list = [dict(e) for e in expenses]
    insight = get_spending_insights(expenses_list, grp['name'])

    return success_response({'insight': insight})


# ── SETTLEMENTS ENDPOINT ──

@api.route('/groups/<int:group_id>/settlements', methods=['GET'])
@jwt_required()
def api_get_settlements(group_id):
    user_id = int(get_jwt_identity())
    conn = get_connection()

    grp = conn.execute(
        'SELECT * FROM groups WHERE id = ? AND user_id = ?',
        (group_id, user_id)
    ).fetchone()

    if not grp:
        conn.close()
        return error_response('Group not found', 404)

    expenses = conn.execute(
        'SELECT * FROM expenses WHERE group_id = ?', (group_id,)
    ).fetchall()
    conn.close()

    expenses_list = [dict(e) for e in expenses]
    settlements = calculate_settlements(expenses_list, grp['members'])
    total = sum(e['amount'] for e in expenses_list)
    members = len([m.strip() for m in grp['members'].split(',')])

    return success_response({
        'settlements': settlements,
        'summary': {
            'total_amount': total,
            'per_person_share': round(total / members, 2) if members > 0 else 0
        }
    })