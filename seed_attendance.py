from datetime import date, timedelta
from db import query_db, modify_db

def seed_sample_attendance():
    """
    Seeds realistic attendance records across 10 previous lecture dates
    for testing the analytics engine, Chart.js graphs, and warning email dispatches.
    """
    students = query_db("SELECT id, roll_number, name FROM students WHERE class_name = 'BCA-3' ORDER BY roll_number")
    subjects = query_db("SELECT id, subject_code, subject_name FROM subjects WHERE class_name = 'BCA-3'")

    if not students or not subjects:
        print("[ERROR] Students or subjects not found for class BCA-3.")
        return

    today = date.today()
    # 10 lecture dates excluding today (so today can be marked fresh by the teacher)
    dates = [today - timedelta(days=i) for i in range(1, 11)]

    # Pre-planned attendance patterns so we have both >=75% and <75% students:
    # Student 1 (Aarav): 9 Present, 1 Absent => 90% (Safe)
    # Student 2 (Priya): 8 Present, 2 Absent => 80% (Safe)
    # Student 3 (Rohan): 6 Present, 4 Absent => 60% (At Risk)
    # Student 4 (Sneha): 10 Present, 0 Absent => 100% (Safe)
    # Student 5 (Vikram): 5 Present, 5 Absent => 50% (At Risk)
    attendance_pattern = {
        0: [1, 1, 1, 1, 1, 1, 1, 1, 1, 0], # 90%
        1: [1, 1, 1, 1, 1, 1, 0, 1, 1, 0], # 80%
        2: [1, 0, 1, 0, 1, 0, 1, 0, 1, 1], # 60% (At Risk)
        3: [1, 1, 1, 1, 1, 1, 1, 1, 1, 1], # 100%
        4: [0, 1, 0, 1, 0, 1, 0, 1, 0, 1], # 50% (At Risk)
    }

    inserted_count = 0
    for sub in subjects:
        for day_idx, att_date in enumerate(dates):
            for s_idx, st in enumerate(students):
                # Check if record already exists
                existing = query_db(
                    "SELECT id FROM attendance WHERE student_id = %s AND subject_id = %s AND attendance_date = %s",
                    (st['id'], sub['id'], att_date),
                    one=True
                )
                if not existing:
                    status = 'Present' if attendance_pattern[s_idx % len(attendance_pattern)][day_idx] == 1 else 'Absent'
                    modify_db(
                        "INSERT INTO attendance (student_id, subject_id, attendance_date, status) VALUES (%s, %s, %s, %s)",
                        (st['id'], sub['id'], att_date, status)
                    )
                    inserted_count += 1

    print(f"[SUCCESS] Seeded {inserted_count} sample attendance records across 10 lecture dates.")

if __name__ == '__main__':
    seed_sample_attendance()
