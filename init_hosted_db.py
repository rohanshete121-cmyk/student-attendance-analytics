import pymysql
from werkzeug.security import generate_password_hash
from config import Config

def main():
    print(f"Connecting to {Config.DB_HOST}:{Config.DB_PORT}/{Config.DB_NAME}...")
    conn = pymysql.connect(host=Config.DB_HOST, port=Config.DB_PORT, user=Config.DB_USER, password=Config.DB_PASSWORD, database=Config.DB_NAME, charset="utf8mb4")
    with conn.cursor() as cur:
        with open("schema.sql", "r", encoding="utf-8") as f:
            statements = [s.strip() for s in f.read().split(";") if s.strip()]
        for stmt in statements:
            cur.execute(stmt)
        email = "teacher@example.com"
        cur.execute("SELECT id FROM teachers WHERE email=%s", (email,))
        teacher = cur.fetchone()
        if not teacher:
            cur.execute("INSERT INTO teachers (name,email,password_hash,department) VALUES (%s,%s,%s,%s)", ("Prof. Rajesh Sharma", email, generate_password_hash("teacher123"), "Computer Applications"))
            teacher_id = cur.lastrowid
            subjects=[("BCA301","Database Management Systems","BCA-3"),("BCA302","Python Programming","BCA-3"),("BCA501","Web Development","BCA-5")]
            for code,name,cls in subjects: cur.execute("INSERT INTO subjects (subject_code,subject_name,teacher_id,class_name) VALUES (%s,%s,%s,%s)",(code,name,teacher_id,cls))
            students=[("BCA2601","Aarav Sharma","BCA-3","aarav.sharma@example.com"),("BCA2602","Priya Patel","BCA-3","priya.patel@example.com"),("BCA2603","Rohan Verma","BCA-3","rohan.verma@example.com"),("BCA2604","Sneha Gupta","BCA-3","sneha.gupta@example.com"),("BCA2605","Vikram Singh","BCA-3","vikram.singh@example.com")]
            for roll,name,cls,email2 in students: cur.execute("INSERT INTO students (roll_number,name,class_name,email) VALUES (%s,%s,%s,%s)",(roll,name,cls,email2))
    conn.commit(); conn.close(); print("Hosted database initialized successfully.")

if __name__ == "__main__": main()
