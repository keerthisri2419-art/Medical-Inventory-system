# routes/sales.py - Sales & Billing Blueprint

from flask import Blueprint, request, jsonify, session
from utils.db import query, get_db
from routes.inventory import _log_stock
from mysql.connector import Error
import logging

sales_bp = Blueprint('sales', __name__)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# GET /api/sales — List all sales (with optional date filter)
# ──────────────────────────────────────────────────────────────
@sales_bp.route('/api/sales', methods=['GET'])
def get_sales():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    date_from = request.args.get('from', '')
    date_to   = request.args.get('to', '')
    search    = request.args.get('search', '').strip()

    sql = """
        SELECT s.id, s.invoice_number, s.customer_name, s.customer_phone,
               s.subtotal, s.tax_amount, s.total_amount, s.payment_method,
               s.created_at, u.username AS billed_by
        FROM sales s
        LEFT JOIN users u ON s.created_by = u.id
        WHERE 1=1
    """
    params = []

    if date_from:
        sql += " AND DATE(s.created_at) >= %s"
        params.append(date_from)
    if date_to:
        sql += " AND DATE(s.created_at) <= %s"
        params.append(date_to)
    if search:
        sql += " AND (s.invoice_number LIKE %s OR s.customer_name LIKE %s)"
        like = f'%{search}%'
        params.extend([like, like])

    sql += " ORDER BY s.created_at DESC"

    sales = query(sql, params)
    for s in sales:
        if s.get('created_at'):
            s['created_at'] = s['created_at'].isoformat()
        s['subtotal']    = float(s['subtotal'])
        s['tax_amount']  = float(s['tax_amount'])
        s['total_amount']= float(s['total_amount'])

    return jsonify(sales)

# ──────────────────────────────────────────────────────────────
# GET /api/sales/<id> — Single sale with line items
# ──────────────────────────────────────────────────────────────
@sales_bp.route('/api/sales/<int:sale_id>', methods=['GET'])
def get_sale(sale_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    sale = query(
        """SELECT s.*, u.username AS billed_by
           FROM sales s LEFT JOIN users u ON s.created_by = u.id
           WHERE s.id = %s""",
        (sale_id,), fetch='one'
    )
    if not sale:
        return jsonify({'error': 'Sale not found'}), 404

    items = query(
        """SELECT si.*, m.name AS medicine_name, m.unit
           FROM sales_items si
           JOIN medicines m ON si.medicine_id = m.id
           WHERE si.sale_id = %s""",
        (sale_id,)
    )

    # Serialize decimals / dates
    sale['created_at']   = sale['created_at'].isoformat() if sale['created_at'] else None
    sale['subtotal']     = float(sale['subtotal'])
    sale['tax_amount']   = float(sale['tax_amount'])
    sale['total_amount'] = float(sale['total_amount'])
    for item in items:
        item['unit_price']   = float(item['unit_price'])
        item['total_price']  = float(item['total_price'])

    sale['items'] = items
    return jsonify(sale)

# ──────────────────────────────────────────────────────────────
# POST /api/sales — Create new sale / invoice
# ──────────────────────────────────────────────────────────────
@sales_bp.route('/api/sales', methods=['POST'])
def create_sale():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    err = _validate_sale(data)
    if err:
        return jsonify({'error': err}), 400

    items      = data['items']           # list of {medicine_id, quantity, unit_price}
    subtotal   = float(data.get('subtotal', 0))
    tax_amount = float(data.get('tax_amount', 0))
    total      = float(data.get('total_amount', 0))

    # Generate unique invoice number: INV-YYYYMMDD-XXXX
    from datetime import datetime
    today_str = datetime.now().strftime('%Y%m%d')
    last = query(
        "SELECT id FROM sales WHERE invoice_number LIKE %s ORDER BY id DESC LIMIT 1",
        (f'INV-{today_str}-%',), fetch='one'
    )
    seq = (last['id'] % 9999 + 1) if last else 1
    invoice_number = f"INV-{today_str}-{seq:04d}"

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        # ── 1. Validate stock availability for all items ──
        for item in items:
            med = cursor.execute(
                "SELECT id, name, quantity FROM medicines WHERE id = %s FOR UPDATE",
                (item['medicine_id'],)
            ) or cursor.fetchone()
            med = cursor.fetchone()
            if not med:
                raise ValueError(f"Medicine id={item['medicine_id']} not found")
            if med['quantity'] < item['quantity']:
                raise ValueError(f"Insufficient stock for '{med['name']}'. Available: {med['quantity']}")

        # ── 2. Insert sale header ──
        cursor.execute(
            """INSERT INTO sales
               (invoice_number, customer_name, customer_phone,
                subtotal, tax_amount, total_amount, payment_method, created_by)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                invoice_number,
                data.get('customer_name', 'Walk-in Customer').strip(),
                data.get('customer_phone', '').strip(),
                subtotal, tax_amount, total,
                data.get('payment_method', 'cash'),
                session['user_id']
            )
        )
        sale_id = cursor.lastrowid

        # ── 3. Insert line items & deduct stock ──
        for item in items:
            cursor.execute(
                """INSERT INTO sales_items (sale_id, medicine_id, quantity, unit_price, total_price)
                   VALUES (%s, %s, %s, %s, %s)""",
                (sale_id, item['medicine_id'], item['quantity'],
                 item['unit_price'], item['quantity'] * item['unit_price'])
            )
            cursor.execute(
                "UPDATE medicines SET quantity = quantity - %s WHERE id = %s",
                (item['quantity'], item['medicine_id'])
            )
            # Log stock deduction
            cursor.execute(
                """INSERT INTO stock_transactions
                   (medicine_id, quantity_change, transaction_type, notes, created_by)
                   VALUES (%s, %s, 'sale', %s, %s)""",
                (item['medicine_id'], -item['quantity'], f"Sale invoice {invoice_number}", session['user_id'])
            )

        conn.commit()
        logger.info(f"Sale created: invoice={invoice_number}, total={total}")
        return jsonify({'success': True, 'sale_id': sale_id, 'invoice_number': invoice_number}), 201

    except ValueError as ve:
        conn.rollback()
        return jsonify({'error': str(ve)}), 400
    except Error as e:
        conn.rollback()
        logger.error(f"Sale creation error: {e}")
        return jsonify({'error': 'Database error during sale creation'}), 500
    finally:
        cursor.close()

# ──────────────────────────────────────────────────────────────
# GET /api/reports/summary — Dashboard analytics
# ──────────────────────────────────────────────────────────────
@sales_bp.route('/api/reports/summary', methods=['GET'])
def reports_summary():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    # Today's sales
    today = query(
        """SELECT COUNT(*) AS count, COALESCE(SUM(total_amount),0) AS revenue
           FROM sales WHERE DATE(created_at) = CURDATE()""",
        fetch='one'
    )
    # Monthly sales
    monthly = query(
        """SELECT COUNT(*) AS count, COALESCE(SUM(total_amount),0) AS revenue
           FROM sales WHERE MONTH(created_at)=MONTH(CURDATE()) AND YEAR(created_at)=YEAR(CURDATE())""",
        fetch='one'
    )
    # Total medicines
    inv = query(
        "SELECT COUNT(*) AS total, SUM(quantity) AS total_qty FROM medicines",
        fetch='one'
    )
    # Low stock count
    low = query(
        "SELECT COUNT(*) AS count FROM medicines WHERE quantity <= reorder_level",
        fetch='one'
    )
    # Expiring soon
    exp = query(
        """SELECT COUNT(*) AS count FROM medicines
           WHERE expiry_date <= DATE_ADD(CURDATE(), INTERVAL 30 DAY) AND expiry_date >= CURDATE()""",
        fetch='one'
    )
    # Daily sales for last 30 days (chart data)
    daily = query(
        """SELECT DATE(created_at) AS sale_date,
                  COUNT(*) AS num_sales,
                  COALESCE(SUM(total_amount),0) AS revenue
           FROM sales
           WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
           GROUP BY DATE(created_at)
           ORDER BY sale_date ASC"""
    )
    for row in daily:
        row['sale_date'] = row['sale_date'].isoformat()
        row['revenue']   = float(row['revenue'])

    # Top selling medicines
    top_medicines = query(
        """SELECT m.name, SUM(si.quantity) AS total_sold
           FROM sales_items si
           JOIN medicines m ON si.medicine_id = m.id
           GROUP BY m.id, m.name
           ORDER BY total_sold DESC
           LIMIT 5"""
    )

    return jsonify({
        'today':         {**today, 'revenue': float(today['revenue'])},
        'monthly':       {**monthly, 'revenue': float(monthly['revenue'])},
        'inventory':     {**inv, 'total_qty': int(inv['total_qty'] or 0)},
        'low_stock':     low['count'],
        'expiring_soon': exp['count'],
        'daily_sales':   daily,
        'top_medicines': top_medicines
    })

# ──────────────────────────────────────────────────────────────
# Private helpers
# ──────────────────────────────────────────────────────────────
def _validate_sale(data):
    if not data:
        return 'No data provided'
    items = data.get('items', [])
    if not items:
        return 'At least one item is required'
    for i, item in enumerate(items):
        if not item.get('medicine_id'):
            return f'Item {i+1}: medicine_id is required'
        try:
            qty = int(item.get('quantity', 0))
            if qty <= 0:
                raise ValueError
        except (ValueError, TypeError):
            return f'Item {i+1}: quantity must be a positive integer'
        try:
            price = float(item.get('unit_price', -1))
            if price < 0:
                raise ValueError
        except (ValueError, TypeError):
            return f'Item {i+1}: unit_price must be non-negative'
    return None
