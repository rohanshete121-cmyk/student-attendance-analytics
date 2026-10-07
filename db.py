import pymysql
from pymysql.cursors import DictCursor
from config import Config

def get_db_connection(use_database=True):
    """
    Establish and return a new MySQL connection.
    Uses DictCursor so results can be accessed like dictionaries (e.g. row['name']).
    """
    connection_params = {
        'host': Config.DB_HOST,
        'port': Config.DB_PORT,
        'user': Config.DB_USER,
        'password': Config.DB_PASSWORD,
        'cursorclass': DictCursor,
        'autocommit': False,
        'charset': 'utf8mb4'
    }
    
    if use_database:
        connection_params['database'] = Config.DB_NAME
        
    return pymysql.connect(**connection_params)

def query_db(query, args=(), one=False):
    """
    Execute a SELECT query with parameterized inputs (preventing SQL injection).
    Returns a single dict if one=True, or a list of dicts if one=False.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, args)
            results = cursor.fetchall()
            return (results[0] if results else None) if one else results
    finally:
        conn.close()

def modify_db(query, args=()):
    """
    Execute an INSERT, UPDATE, or DELETE query with parameterized inputs.
    Commits the transaction and returns the last inserted row ID or affected rows count.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, args)
            last_id = cursor.lastrowid
            affected = cursor.rowcount
        conn.commit()
        return last_id if last_id else affected
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
