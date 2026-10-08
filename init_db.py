import pymysql
from werkzeug.security import generate_password_hash
from config import Config

def init_database():
    """
    Creates the MySQL database, tables from schema.sql,
    and seeds a sample teacher account so you can log in immediately.
    """
    print(f"Connecting to MySQL server at {Config.DB_HOST}:{Config.DB_PORT} as '{Config.DB_USER}'...")

    # Step 1: Connect to server without database to create the database if missing
    root_conn = pymysql.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        charset='utf8mb4',
ssl={}
    )
    
    with root_conn.cursor() as cur:
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{Config.DB_NAME}` DEFAULT CHARACTER SET utf8mb4;")
        print(f"[SUCCESS] Database '{Config.DB_NAME}' created or verified.")
    root_conn.close()

    # Step 2: Connect to the specific project database and execute schema.sql
    conn = pymysql.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        charset='utf8mb4',
ssl={}
    )

    with open('schema.sql', 'r', encoding='utf-8') as f:
        sql_content = f.read()

    # Split commands by semicolon
    statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]

    with conn.cursor() as cur:
        for stmt in statements:
            cur.execute(stmt)
        conn.commit()
    print("[SUCCESS] All tables (teachers, subjects, students, attendance, email_logs) verified/created.")

    # Step 3: Seed a default teacher account if not exists
    default_email = "teacher@example.com"
    default_password = "teacher123"
    default_name = "Prof. Rajesh Sharma"
    default_department = "Computer Applications"
    hashed_pwd = generate_password_hash(default_password)

    with conn.cursor() as cur:
        cur.execute("SELECT id FROM teachers WHERE email = %s", (default_email,))
        existing_teacher = cur.fetchone()

        if not existing_teacher:
            cur.execute(
                """
                INSERT INTO teachers (name, email, password_hash, department)
                VALUES (%s, %s, %s, %s)
                """,
                (default_name, default_email, hashed_pwd, default_department)
            )
            conn.commit()
            teacher_id = cur.lastrowid
            print(f"[SUCCESS] Default teacher account created!")
            print(f"         Login Email   : {default_email}")
            print(f"         Login Password: {default_password}")

            # Also seed 2 starter subjects for this teacher
            starter_subjects = [
                ("BCA301", "Database Management Systems", "BCA-3"),
                ("BCA302", "Python Programming", "BCA-3"),
                ("BCA501", "Web Development", "BCA-5")
            ]
            for code, name, cls in starter_subjects:
                cur.execute(
                    """
                    INSERT INTO subjects (subject_code, subject_name, teacher_id, class_name)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (code, name, teacher_id, cls)
                )
            conn.commit()
            print("[SUCCESS] Sample subjects seeded for teacher.")

            # Seed 5 sample students
            starter_students = [
                ("BCA2601", "Aarav Sharma", "BCA-3", "aarav.sharma@example.com"),
                ("BCA2602", "Priya Patel", "BCA-3", "priya.patel@example.com"),
                ("BCA2603", "Rohan Verma", "BCA-3", "rohan.verma@example.com"),
                ("BCA2604", "Sneha Gupta", "BCA-3", "sneha.gupta@example.com"),
                ("BCA2605", "Vikram Singh", "BCA-3", "vikram.singh@example.com")
            ]
            for roll, s_name, cls, s_email in starter_students:
                cur.execute(
                    """
                    INSERT INTO students (roll_number, name, class_name, email)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (roll, s_name, cls, s_email)
                )
            conn.commit()
            print("[SUCCESS] Sample students seeded for testing.")
        else:
            print("[INFO] Default teacher account already exists.")

    conn.close()
    print("[DONE] Database initialization completed successfully!")

if __name__ == '__main__':
    init_database()
