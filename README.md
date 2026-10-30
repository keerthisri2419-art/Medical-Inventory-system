# 💊 MedInventory — Medical Inventory & Sales Management System

A full-stack web application for managing medical store inventory, sales, suppliers, and analytics.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- MySQL 8.0+
- pip

---

### Step 1: Clone / Extract the project

```bash
cd medical_inventory_system
```

### Step 2: Create a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate
```

### Step 3: Install dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Set up the database

Open MySQL and run:

```sql
mysql -u root -p < database.sql
```

Or paste the contents of `database.sql` into MySQL Workbench.

### Step 5: Configure environment (optional)

Create a `.env` file in the root:

```env
SECRET_KEY=your_secret_key_here
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=medical_inventory
```

> If no `.env` file exists, defaults from `config.py` are used.

### Step 6: Seed user passwords

```bash
python seed_passwords.py
```

This sets real bcrypt hashes for the default accounts.

### Step 7: Run the app

```bash
python app.py
```

Open your browser: **http://localhost:5000**

---

## 🔐 Default Login Credentials

| Username | Password  | Role  |
|----------|-----------|-------|
| admin    | admin123  | Admin |
| staff1   | staff123  | Staff |

---

## 📂 Project Structure

```
medical_inventory_system/
├── app.py              ← Flask app factory & page routes
├── config.py           ← Configuration (DB, tax rate, etc.)
├── database.sql        ← Full MySQL schema + sample data
├── requirements.txt    ← Python dependencies
├── seed_passwords.py   ← Password seeder (run once)
│
├── routes/
│   ├── auth.py         ← Login, logout, session management
│   ├── inventory.py    ← Medicine CRUD + stock alerts
│   ├── sales.py        ← Billing, invoices, reports API
│   └── suppliers.py    ← Supplier management
│
├── utils/
│   └── db.py           ← MySQL connection pool + query helper
│
├── static/
│   ├── css/style.css   ← Medical-themed CSS (no frameworks)
│   └── js/main.js      ← Shared JS utilities, API helper
│
└── templates/
    ├── login.html
    ├── dashboard.html
    ├── inventory.html
    ├── sales.html
    ├── suppliers.html
    └── reports.html
```

---

## 🧠 System Flow

```
Browser → Flask Routes (HTML pages)
       → JS fetch() → REST API endpoints → MySQL DB
```

1. **Auth**: User logs in → Flask session stores `user_id`, `role`
2. **Inventory**: Admin adds/edits/deletes medicines → stock tracked via `stock_transactions`
3. **Sales**: Staff creates bill → items added to cart → POST `/api/sales` → stock auto-deducted
4. **Invoice**: Generated client-side from sale data, printable via CSS
5. **Reports**: Aggregated SQL queries → charts drawn on HTML5 Canvas

---

## 🔒 Security Features

- Parameterized SQL queries (SQL injection safe)
- Werkzeug password hashing (bcrypt/scrypt)
- Flask session-based authentication
- Role-based access control (admin vs staff)
- Input validation on both frontend and backend

---

## 📊 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login` | Login |
| POST | `/api/auth/logout` | Logout |
| GET | `/api/inventory` | List medicines |
| POST | `/api/inventory` | Add medicine (admin) |
| PUT | `/api/inventory/<id>` | Update medicine (admin) |
| DELETE | `/api/inventory/<id>` | Delete medicine (admin) |
| GET | `/api/inventory/alerts` | Low stock + expiry alerts |
| GET | `/api/sales` | List sales |
| POST | `/api/sales` | Create new sale/invoice |
| GET | `/api/sales/<id>` | Sale detail with items |
| GET | `/api/suppliers` | List suppliers |
| POST | `/api/suppliers` | Add supplier (admin) |
| PUT | `/api/suppliers/<id>` | Update supplier (admin) |
| DELETE | `/api/suppliers/<id>` | Delete supplier (admin) |
| GET | `/api/reports/summary` | Dashboard analytics |
# cloude1212
