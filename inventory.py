# routes/inventory.py - Inventory Management Blueprint

from flask import Blueprint, request, jsonify, session
from utils.db import query
from routes.auth import login_required, admin_required
from datetime import date
import logging

inventory_bp = Blueprint('inventory', __name__)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# GET /api/inventory — List all medicines with supplier name
# ──────────────────────────────────────────────────────────────
@inventory_bp.route('/api/inventory', methods=['GET'])
def get_medicines():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    search = request.args.get('search', '').strip()
    low_stock = request.args.get('low_stock', '')
    expiring = request.args.get('expiring', '')

    sql = """
        SELECT m.id, m.name, m.generic_name, m.category, m.unit,
               m.quantity, m.price, m.cost_price, m.expiry_date,
               m.reorder_level, m.description,
               s.name AS supplier_name, s.id AS supplier_id,
               m.created_at
        FROM medicines m
        LEFT JOIN suppliers s ON m.supplier_id = s.id
        WHERE 1=1
    """
    params = []

    if search:
        sql += " AND (m.name LIKE %s OR m.generic_name LIKE %s OR m.category LIKE %s)"
        like = f'%{search}%'
        params.extend([like, like, like])

    if low_stock == '1':
        sql += " AND m.quantity <= m.reorder_level"

    if expiring == '1':
        sql += " AND m.expiry_date <= DATE_ADD(CURDATE(), INTERVAL 30 DAY) AND m.expiry_date >= CURDATE()"

    sql += " ORDER BY m.name ASC"

    medicines = query(sql, params)

    # Annotate each medicine with alert flags
    today = date.today()
    for m in medicines:
        m['low_stock_alert'] = m['quantity'] <= m['reorder_level']
        if m['expiry_date']:
            days_left = (m['expiry_date'] - today).days
            m['days_to_expiry'] = days_left
            m['expiry_warning']  = days_left <= 30
            m['expiry_date']     = m['expiry_date'].isoformat()
        else:
            m['days_to_expiry'] = None
            m['expiry_warning']  = False
        if m['created_at']:
            m['created_at'] = m['created_at'].isoformat()

    return jsonify(medicines)

# ──────────────────────────────────────────────────────────────
# GET /api/inventory/<id> — Single medicine detail
# ──────────────────────────────────────────────────────────────
@inventory_bp.route('/api/inventory/<int:med_id>', methods=['GET'])
def get_medicine(med_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    m = query("SELECT * FROM medicines WHERE id = %s", (med_id,), fetch='one')
    if not m:
        return jsonify({'error': 'Medicine not found'}), 404

    if m['expiry_date']:
        m['expiry_date'] = m['expiry_date'].isoformat()
    if m['created_at']:
        m['created_at'] = m['created_at'].isoformat()
    if m['updated_at']:
        m['updated_at'] = m['updated_at'].isoformat()
    return jsonify(m)

# ──────────────────────────────────────────────────────────────
# POST /api/inventory — Add new medicine (Admin only)
# ──────────────────────────────────────────────────────────────
@inventory_bp.route('/api/inventory', methods=['POST'])
def add_medicine():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    if session.get('role') != 'admin':
        return jsonify({'error': 'Admin access required'}), 403

    data = request.get_json()
    err = _validate_medicine(data)
    if err:
        return jsonify({'error': err}), 400

    med_id = query(
        """INSERT INTO medicines
           (name, generic_name, category, unit, quantity, price, cost_price,
            expiry_date, reorder_level, supplier_id, description)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (
            data['name'].strip(),
            data.get('generic_name', '').strip(),
            data.get('category', '').strip(),
            data.get('unit', 'pcs').strip(),
            int(data['quantity']),
            float(data['price']),
            float(data.get('cost_price', 0)),
            data.get('expiry_date') or None,
            int(data.get('reorder_level', 10)),
            data.get('supplier_id') or None,
            data.get('description', '').strip()
        ),
        fetch=None,
        commit=True
    )

    # Log stock transaction
    _log_stock(med_id, int(data['quantity']), 'purchase', 'Initial stock entry', session['user_id'])
    logger.info(f"Medicine added: id={med_id}, name={data['name']}")
    return jsonify({'success': True, 'id': med_id}), 201

# ──────────────────────────────────────────────────────────────
# PUT /api/inventory/<id> — Update medicine (Admin only)
# ──────────────────────────────────────────────────────────────
@inventory_bp.route('/api/inventory/<int:med_id>', methods=['PUT'])
def update_medicine(med_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    if session.get('role') != 'admin':
        return jsonify({'error': 'Admin access required'}), 403

    data = request.get_json()
    err = _validate_medicine(data)
    if err:
        return jsonify({'error': err}), 400

    # Fetch old quantity to log delta
    old = query("SELECT quantity FROM medicines WHERE id = %s", (med_id,), fetch='one')
    if not old:
        return jsonify({'error': 'Medicine not found'}), 404

    query(
        """UPDATE medicines SET
           name=%s, generic_name=%s, category=%s, unit=%s, quantity=%s,
           price=%s, cost_price=%s, expiry_date=%s, reorder_level=%s,
           supplier_id=%s, description=%s, updated_at=NOW()
           WHERE id=%s""",
        (
            data['name'].strip(),
            data.get('generic_name', '').strip(),
            data.get('category', '').strip(),
            data.get('unit', 'pcs').strip(),
            int(data['quantity']),
            float(data['price']),
            float(data.get('cost_price', 0)),
            data.get('expiry_date') or None,
            int(data.get('reorder_level', 10)),
            data.get('supplier_id') or None,
            data.get('description', '').strip(),
            med_id
        ),
        fetch=None,
        commit=True
    )

    # Log quantity adjustment if changed
    delta = int(data['quantity']) - old['quantity']
    if delta != 0:
        tx_type = 'adjustment'
        _log_stock(med_id, delta, tx_type, 'Manual stock adjustment', session['user_id'])

    return jsonify({'success': True})

# ──────────────────────────────────────────────────────────────
# DELETE /api/inventory/<id> — Delete medicine (Admin only)
# ──────────────────────────────────────────────────────────────
@inventory_bp.route('/api/inventory/<int:med_id>', methods=['DELETE'])
def delete_medicine(med_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    if session.get('role') != 'admin':
        return jsonify({'error': 'Admin access required'}), 403

    existing = query("SELECT id FROM medicines WHERE id = %s", (med_id,), fetch='one')
    if not existing:
        return jsonify({'error': 'Medicine not found'}), 404

    query("DELETE FROM medicines WHERE id = %s", (med_id,), fetch=None, commit=True)
    logger.info(f"Medicine deleted: id={med_id}")
    return jsonify({'success': True})

# ──────────────────────────────────────────────────────────────
# GET /api/inventory/alerts — Low stock + expiry summary
# ──────────────────────────────────────────────────────────────
@inventory_bp.route('/api/inventory/alerts', methods=['GET'])
def get_alerts():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    low_stock = query(
        "SELECT id, name, quantity, reorder_level FROM medicines WHERE quantity <= reorder_level ORDER BY quantity ASC"
    )
    expiring = query(
        """SELECT id, name, quantity, expiry_date,
                  DATEDIFF(expiry_date, CURDATE()) AS days_left
           FROM medicines
           WHERE expiry_date <= DATE_ADD(CURDATE(), INTERVAL 30 DAY)
             AND expiry_date >= CURDATE()
           ORDER BY expiry_date ASC"""
    )
    expired = query(
        """SELECT id, name, quantity, expiry_date FROM medicines
           WHERE expiry_date < CURDATE() ORDER BY expiry_date ASC"""
    )

    for row in expiring + expired:
        if row.get('expiry_date'):
            row['expiry_date'] = row['expiry_date'].isoformat()

    return jsonify({
        'low_stock': low_stock,
        'expiring_soon': expiring,
        'expired': expired
    })

# ──────────────────────────────────────────────────────────────
# Private helpers
# ──────────────────────────────────────────────────────────────
def _validate_medicine(data):
    """Returns error string or None if valid."""
    if not data:
        return 'No data provided'
    if not data.get('name', '').strip():
        return 'Medicine name is required'
    try:
        qty = int(data.get('quantity', -1))
        if qty < 0:
            raise ValueError
    except (ValueError, TypeError):
        return 'Quantity must be a non-negative integer'
    try:
        price = float(data.get('price', -1))
        if price < 0:
            raise ValueError
    except (ValueError, TypeError):
        return 'Price must be a non-negative number'
    return None

def _log_stock(medicine_id, quantity_change, transaction_type, notes, user_id):
    """Insert a record into stock_transactions."""
    query(
        """INSERT INTO stock_transactions
           (medicine_id, quantity_change, transaction_type, notes, created_by)
           VALUES (%s, %s, %s, %s, %s)""",
        (medicine_id, quantity_change, transaction_type, notes, user_id),
        fetch=None,
        commit=True
    )
