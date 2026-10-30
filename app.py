# app.py - Application entry point and Flask app factory

from flask import Flask, render_template, session, redirect, url_for
from config import Config
from utils.db import init_pool, close_db
from routes.auth import auth_bp
from routes.inventory import inventory_bp
from routes.sales import sales_bp
from routes.suppliers import suppliers_bp
import logging

# ── Logging setup ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

def create_app():
    """App factory — creates and configures the Flask application."""
    app = Flask(__name__)
    app.config.from_object(Config)

    # ── Initialize DB connection pool ──
    with app.app_context():
        init_pool(app)

    # ── Register teardown to release DB connections ──
    app.teardown_appcontext(close_db)

    # ── Register Blueprints ──
    app.register_blueprint(auth_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(sales_bp)
    app.register_blueprint(suppliers_bp)

    # ── Page routes (render HTML templates) ──

    @app.route('/dashboard')
    def dashboard():
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return render_template('dashboard.html',
                               username=session['username'],
                               role=session['role'])

    @app.route('/inventory')
    def inventory_page():
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return render_template('inventory.html',
                               username=session['username'],
                               role=session['role'])

    @app.route('/sales')
    def sales_page():
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return render_template('sales.html',
                               username=session['username'],
                               role=session['role'])

    @app.route('/suppliers')
    def suppliers_page():
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return render_template('suppliers.html',
                               username=session['username'],
                               role=session['role'])

    @app.route('/reports')
    def reports_page():
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return render_template('reports.html',
                               username=session['username'],
                               role=session['role'])

    # ── Global error handlers ──
    @app.errorhandler(404)
    def not_found(e):
        return {'error': 'Resource not found'}, 404

    @app.errorhandler(500)
    def server_error(e):
        return {'error': 'Internal server error'}, 500

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
