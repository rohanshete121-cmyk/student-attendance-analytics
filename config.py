import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Application configuration class loaded from environment variables."""
    SECRET_KEY = os.getenv('SECRET_KEY', 'default-dev-secret-key-change-in-production')
    
    # MySQL Database Settings
    DB_HOST = os.getenv('DB_HOST') or os.getenv('MYSQLHOST', '127.0.0.1')
    DB_PORT = int(os.getenv('DB_PORT') or os.getenv('MYSQLPORT') or 3306)
    DB_USER = os.getenv('DB_USER') or os.getenv('MYSQLUSER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD') if os.getenv('DB_PASSWORD') is not None else os.getenv('MYSQLPASSWORD', '')
    DB_NAME = os.getenv('DB_NAME') or os.getenv('MYSQLDATABASE', 'attendance_analytics_db')

    # Mail / SMTP Settings
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True').lower() in ('true', '1', 't')
    MAIL_USERNAME = os.getenv('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', '')
