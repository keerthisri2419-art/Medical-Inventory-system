# routes/auth.py - Authentication Blueprint (Login / Logout)

from flask import Blueprint, request, session, redirect, url_for, render_template, jsonify
from utils.db import query
from werkzeug.security import check_password_hash
import logging

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Helper: require login for protected routes
# ──────────────────────────────────────────────────────────────
def login_required(f):
    """Decorator — redirects to login if session has no user_id."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    """Decorator — returns 403 if user is not admin."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated

# ──────────────────────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────────────────────
@auth_bp.route('/', methods=['GET'])
@auth_bp.route('/login', methods=['GET'])
def login():
    """Show login page (redirect to dashboard if already logged in)."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@auth_bp.route('/api/auth/login', methods=['POST'])
def api_login():
    """
    POST /api/auth/login
    Body: { username, password }
    Returns: { success, role, username } or { error }
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid JSON'}), 400

    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()

    # Basic validation
    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400

    # Fetch user by username (parameterized — SQL-injection safe)
    user = query(
        "SELECT id, username, password_hash, role, is_active FROM users WHERE username = %s",
        (username,),
        fetch='one'
    )

    if not user:
        return jsonify({'error': 'Invalid credentials'}), 401

    if not user['is_active']:
        return jsonify({'error': 'Account is disabled. Contact admin.'}), 403

    if not check_password_hash(user['password_hash'], password):
        return jsonify({'error': 'Invalid credentials'}), 401

    # Store user info in session
    session.permanent = True
    session['user_id']  = user['id']
    session['username'] = user['username']
    session['role']     = user['role']

    logger.info(f"User '{username}' logged in successfully.")
    return jsonify({'success': True, 'role': user['role'], 'username': user['username']})

@auth_bp.route('/api/auth/logout', methods=['POST'])
def api_logout():
    """POST /api/auth/logout — clears session."""
    username = session.get('username', 'Unknown')
    session.clear()
    logger.info(f"User '{username}' logged out.")
    return jsonify({'success': True})

@auth_bp.route('/api/auth/me', methods=['GET'])
def api_me():
    """GET /api/auth/me — returns current logged-in user info."""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    return jsonify({
        'user_id':  session['user_id'],
        'username': session['username'],
        'role':     session['role']
    })
