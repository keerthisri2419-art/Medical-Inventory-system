# config.py - Application configuration settings

import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Flask secret key for session management
    SECRET_KEY = os.environ.get('SECRET_KEY', 'med_inv_secret_2024_change_in_production')

    # MySQL Database configuration
    DB_HOST     = os.environ.get('DB_HOST', 'localhost')
    DB_USER     = os.environ.get('DB_USER', 'root')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', '8o78o78O!')
    DB_NAME     = os.environ.get('DB_NAME', 'medical_inventory')
    DB_PORT     = int(os.environ.get('DB_PORT', 3306))

    # App settings
    LOW_STOCK_THRESHOLD = 10        # Alert when quantity <= this value
    EXPIRY_WARNING_DAYS = 30        # Warn if medicine expires within this many days
    TAX_RATE            = 0.18      # GST rate (18%)
