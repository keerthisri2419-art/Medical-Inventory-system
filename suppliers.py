# routes/suppliers.py - Supplier Management Blueprint

from flask import Blueprint, request, jsonify, session
from utils.db import query
import logging

suppliers_bp = Blueprint('suppliers', __name__)
logger = logging.getLogger(__name__)

@suppliers_bp.route('/api/suppliers', methods=['GET'])
def get_suppliers():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    search = request.args.get('search', '').strip()
    sql = "SELECT * FROM suppliers WHERE 1=1"
    params = []
    if search:
        sql += " AND (name LIKE %s OR contact_person LIKE %s OR email LIKE %s)"
        like = f'%{search}%'
        params.extend([like, like, like])
    sql += " ORDER BY name ASC"

    suppliers = query(sql, params)
    for s in suppliers:
        if s.get('created_at'):
            s['created_at'] = s['created_at'].isoformat()
    return jsonify(suppliers)

@suppliers_bp.route('/api/suppliers/<int:sup_id>', methods=['GET'])
def get_supplier(sup_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    s = query("SELECT * FROM suppliers WHERE id = %s", (sup_id,), fetch='one')
    if not s:
        return jsonify({'error': 'Supplier not found'}), 404
    if s.get('created_at'):
        s['created_at'] = s['created_at'].isoformat()

    # Also return medicines supplied by this supplier
    medicines = query(
        "SELECT id, name, quantity, price FROM medicines WHERE supplier_id = %s",
        (sup_id,)
    )
    s['medicines'] = medicines
    return jsonify(s)

@suppliers_bp.route('/api/suppliers', methods=['POST'])
def add_supplier():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    if session.get('role') != 'admin':
        return jsonify({'error': 'Admin access required'}), 403

    data = request.get_json()
    err = _validate_supplier(data)
    if err:
        return jsonify({'error': err}), 400

    sup_id = query(
        """INSERT INTO suppliers (name, contact_person, phone, email, address, gst_number)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (
            data['name'].strip(),
            data.get('contact_person', '').strip(),
            data.get('phone', '').strip(),
            data.get('email', '').strip(),
            data.get('address', '').strip(),
            data.get('gst_number', '').strip()
        ),
        fetch=None,
        commit=True
    )
    logger.info(f"Supplier added: id={sup_id}")
    return jsonify({'success': True, 'id': sup_id}), 201

@suppliers_bp.route('/api/suppliers/<int:sup_id>', methods=['PUT'])
def update_supplier(sup_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    if session.get('role') != 'admin':
        return jsonify({'error': 'Admin access required'}), 403

    data = request.get_json()
    err = _validate_supplier(data)
    if err:
        return jsonify({'error': err}), 400

    existing = query("SELECT id FROM suppliers WHERE id = %s", (sup_id,), fetch='one')
    if not existing:
        return jsonify({'error': 'Supplier not found'}), 404

    query(
        """UPDATE suppliers SET name=%s, contact_person=%s, phone=%s,
           email=%s, address=%s, gst_number=%s WHERE id=%s""",
        (
            data['name'].strip(),
            data.get('contact_person', '').strip(),
            data.get('phone', '').strip(),
            data.get('email', '').strip(),
            data.get('address', '').strip(),
            data.get('gst_number', '').strip(),
            sup_id
        ),
        fetch=None,
        commit=True
    )
    return jsonify({'success': True})

@suppliers_bp.route('/api/suppliers/<int:sup_id>', methods=['DELETE'])
def delete_supplier(sup_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    if session.get('role') != 'admin':
        return jsonify({'error': 'Admin access required'}), 403

    existing = query("SELECT id FROM suppliers WHERE id = %s", (sup_id,), fetch='one')
    if not existing:
        return jsonify({'error': 'Supplier not found'}), 404

    # Set supplier_id to NULL on linked medicines instead of blocking delete
    query("UPDATE medicines SET supplier_id = NULL WHERE supplier_id = %s", (sup_id,), fetch=None, commit=True)
    query("DELETE FROM suppliers WHERE id = %s", (sup_id,), fetch=None, commit=True)
    return jsonify({'success': True})

def _validate_supplier(data):
    if not data:
        return 'No data provided'
    if not data.get('name', '').strip():
        return 'Supplier name is required'
    email = data.get('email', '').strip()
    if email and '@' not in email:
        return 'Invalid email address'
    return None
