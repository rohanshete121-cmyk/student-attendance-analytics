import io
from datetime import date, datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, Response
from werkzeug.security import check_password_hash
import pandas as pd
from config import Config
from db import query_db, modify_db
from analytics import get_attendance_analytics
from mailer import send_attendance_warning_email

app = Flask(
    __name__,
    template_folder='templates',
    static_folder='static'
)
app.config.from_object(Config)

# -------------------------------------------------------------
# Authentication Guard / Decorator
# -------------------------------------------------------------
def login_required(f):
    """
    Decorator to ensure only logged-in teachers can access protected views.
    Redirects unauthenticated users to the login page.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'teacher_id' not in session:
            flash('Please log in to access the teacher portal.', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# -------------------------------------------------------------
# 1. Authentication Routes
# -------------------------------------------------------------
@app.route('/')
def index():
    if 'teacher_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'teacher_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Please enter both your email and password.', 'danger')
            return render_template('login.html', email=email)

        try:
            # Secure parameterized lookup
            teacher = query_db(
                "SELECT * FROM teachers WHERE email = %s",
                (email,),
                one=True
            )

            if teacher and check_password_hash(teacher['password_hash'], password):
                session.clear()
                session['teacher_id'] = teacher['id']
                session['teacher_name'] = teacher['name']
                session['teacher_email'] = teacher['email']
                session['teacher_department'] = teacher.get('department', 'Computer Applications')

                flash(f"Welcome back, {teacher['name']}!", 'success')
                next_page = request.args.get('next')
                return redirect(next_page or url_for('dashboard'))
            else:
                flash('Invalid email or password. Please try again.', 'danger')
        except Exception as e:
            flash(f"Database connection error: {str(e)}", 'danger')

        return render_template('login.html', email=email)

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))

# -------------------------------------------------------------
# 2. Teacher Dashboard
# -------------------------------------------------------------
@app.route('/dashboard')
@login_required
def dashboard():
    teacher_id = session.get('teacher_id')
    subject_id = request.args.get('subject_id')

    teacher = query_db("SELECT * FROM teachers WHERE id = %s", (teacher_id,), one=True)
    teacher_subjects = query_db("SELECT id, subject_code, subject_name, class_name FROM subjects WHERE teacher_id = %s ORDER BY subject_name", (teacher_id,))

    analytics_data = get_attendance_analytics(teacher_id, subject_id=subject_id if subject_id else None)

    recent_sessions_query = """
        SELECT 
            a.attendance_date,
            sub.subject_code,
            sub.subject_name,
            sub.class_name,
            COUNT(a.id) AS total_marked,
            SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS present_count
        FROM attendance a
        JOIN subjects sub ON a.subject_id = sub.id
        WHERE sub.teacher_id = %s
    """
    params = [teacher_id]
    if subject_id:
        recent_sessions_query += " AND sub.id = %s"
        params.append(subject_id)

    recent_sessions_query += """
        GROUP BY a.attendance_date, sub.id, sub.subject_code, sub.subject_name, sub.class_name
        ORDER BY a.attendance_date DESC
        LIMIT 5
    """
    recent_sessions = query_db(recent_sessions_query, tuple(params))

    return render_template(
        'dashboard.html',
        teacher=teacher,
        teacher_subjects=teacher_subjects,
        selected_subject_id=subject_id,
        analytics=analytics_data,
        recent_sessions=recent_sessions,
        today=date.today().strftime('%d %B %Y')
    )

# -------------------------------------------------------------
# 3. Student Management (CRUD)
# -------------------------------------------------------------
@app.route('/students')
@login_required
def students_list():
    search = request.args.get('search', '').strip()
    selected_class = request.args.get('class_name', '').strip()

    classes_rows = query_db("SELECT DISTINCT class_name FROM students ORDER BY class_name")
    available_classes = [r['class_name'] for r in classes_rows]

    query = "SELECT * FROM students WHERE 1=1"
    params = []

    if search:
        query += " AND (roll_number LIKE %s OR name LIKE %s)"
        search_pattern = f"%{search}%"
        params.extend([search_pattern, search_pattern])

    if selected_class:
        query += " AND class_name = %s"
        params.append(selected_class)

    query += " ORDER BY class_name, roll_number"
    students = query_db(query, tuple(params))

    return render_template(
        'students/index.html',
        students=students,
        available_classes=available_classes,
        search=search,
        selected_class=selected_class
    )

@app.route('/students/view/<int:id>')
@login_required
def students_view(id):
    student = query_db("SELECT * FROM students WHERE id = %s", (id,), one=True)
    if not student:
        flash('Student record not found.', 'danger')
        return redirect(url_for('students_list'))

    # Fetch daily logs
    daily_logs = query_db(
        """
        SELECT a.attendance_date, sub.subject_code, sub.subject_name, a.status
        FROM attendance a
        JOIN subjects sub ON a.subject_id = sub.id
        WHERE a.student_id = %s
        ORDER BY a.attendance_date DESC
        """,
        (id,)
    )

    # Compute subject-wise breakdown
    sub_map = {}
    for log in daily_logs:
        code = log['subject_code']
        if code not in sub_map:
            sub_map[code] = {
                'subject_code': code,
                'subject_name': log['subject_name'],
                'total': 0,
                'present': 0,
                'absent': 0
            }
        sub_map[code]['total'] += 1
        if log['status'] == 'Present':
            sub_map[code]['present'] += 1
        else:
            sub_map[code]['absent'] += 1

    subject_breakdown = []
    for sb in sub_map.values():
        sb['percentage'] = round((sb['present'] / sb['total'] * 100.0), 2) if sb['total'] > 0 else 0.0
        subject_breakdown.append(sb)

    total_days = len(daily_logs)
    present_days = sum(1 for l in daily_logs if l['status'] == 'Present')
    overall_percentage = round((present_days / total_days * 100.0), 2) if total_days > 0 else 0.0

    return render_template(
        'students/view.html',
        student=student,
        subject_breakdown=subject_breakdown,
        daily_logs=daily_logs,
        total_days=total_days,
        present_days=present_days,
        overall_percentage=overall_percentage
    )

@app.route('/students/add', methods=['GET', 'POST'])
@login_required
def students_add():
    if request.method == 'POST':
        roll_number = request.form.get('roll_number', '').strip()
        name = request.form.get('name', '').strip()
        class_name = request.form.get('class_name', '').strip()
        email = request.form.get('email', '').strip()

        if not (roll_number and name and class_name and email):
            flash('All fields are required. Please fill out the form completely.', 'danger')
            return render_template('students/form.html', is_edit=False, student=request.form)

        existing = query_db("SELECT id FROM students WHERE roll_number = %s", (roll_number,), one=True)
        if existing:
            flash(f"A student with Roll Number '{roll_number}' already exists!", 'danger')
            return render_template('students/form.html', is_edit=False, student=request.form)

        try:
            modify_db(
                "INSERT INTO students (roll_number, name, class_name, email) VALUES (%s, %s, %s, %s)",
                (roll_number, name, class_name, email)
            )
            flash(f"Student '{name}' ({roll_number}) added successfully!", 'success')
            return redirect(url_for('students_list'))
        except Exception as e:
            flash(f"Error adding student: {str(e)}", 'danger')

    return render_template('students/form.html', is_edit=False, student=None)

@app.route('/students/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def students_edit(id):
    student = query_db("SELECT * FROM students WHERE id = %s", (id,), one=True)
    if not student:
        flash('Student record not found.', 'danger')
        return redirect(url_for('students_list'))

    if request.method == 'POST':
        roll_number = request.form.get('roll_number', '').strip()
        name = request.form.get('name', '').strip()
        class_name = request.form.get('class_name', '').strip()
        email = request.form.get('email', '').strip()

        if not (roll_number and name and class_name and email):
            flash('All fields are required.', 'danger')
            return render_template('students/form.html', is_edit=True, student=request.form)

        existing = query_db("SELECT id FROM students WHERE roll_number = %s AND id != %s", (roll_number, id), one=True)
        if existing:
            flash(f"Roll Number '{roll_number}' is already assigned to another student.", 'danger')
            return render_template('students/form.html', is_edit=True, student=request.form)

        try:
            modify_db(
                "UPDATE students SET roll_number = %s, name = %s, class_name = %s, email = %s WHERE id = %s",
                (roll_number, name, class_name, email, id)
            )
            flash(f"Student '{name}' updated successfully!", 'success')
            return redirect(url_for('students_list'))
        except Exception as e:
            flash(f"Error updating student: {str(e)}", 'danger')

    return render_template('students/form.html', is_edit=True, student=student)

@app.route('/students/delete/<int:id>', methods=['POST'])
@login_required
def students_delete(id):
    try:
        student = query_db("SELECT name FROM students WHERE id = %s", (id,), one=True)
        name = student['name'] if student else 'Student'
        modify_db("DELETE FROM students WHERE id = %s", (id,))
        flash(f"Student record '{name}' and associated attendance have been removed.", 'success')
    except Exception as e:
        flash(f"Error deleting student: {str(e)}", 'danger')
    return redirect(url_for('students_list'))

# -------------------------------------------------------------
# 4. Subject Management
# -------------------------------------------------------------
@app.route('/subjects')
@login_required
def subjects_list():
    teacher_id = session.get('teacher_id')
    subjects = query_db(
        "SELECT * FROM subjects WHERE teacher_id = %s ORDER BY class_name, subject_code",
        (teacher_id,)
    )
    return render_template('subjects/index.html', subjects=subjects)

@app.route('/subjects/add', methods=['GET', 'POST'])
@login_required
def subjects_add():
    teacher_id = session.get('teacher_id')

    if request.method == 'POST':
        subject_code = request.form.get('subject_code', '').strip().upper()
        subject_name = request.form.get('subject_name', '').strip()
        class_name = request.form.get('class_name', '').strip()

        if not (subject_code and subject_name and class_name):
            flash('All fields are required.', 'danger')
            return render_template('subjects/add.html', subject_code=subject_code, subject_name=subject_name, class_name=class_name)

        existing = query_db("SELECT id FROM subjects WHERE subject_code = %s", (subject_code,), one=True)
        if existing:
            flash(f"Subject Code '{subject_code}' already exists.", 'danger')
            return render_template('subjects/add.html', subject_code=subject_code, subject_name=subject_name, class_name=class_name)

        try:
            modify_db(
                "INSERT INTO subjects (subject_code, subject_name, teacher_id, class_name) VALUES (%s, %s, %s, %s)",
                (subject_code, subject_name, teacher_id, class_name)
            )
            flash(f"Subject '{subject_name}' ({subject_code}) created and assigned to you!", 'success')
            return redirect(url_for('subjects_list'))
        except Exception as e:
            flash(f"Error creating subject: {str(e)}", 'danger')

    return render_template('subjects/add.html')

# -------------------------------------------------------------
# 5. Attendance Marking, Updating & History
# -------------------------------------------------------------
@app.route('/attendance/mark')
@login_required
def attendance_mark():
    teacher_id = session.get('teacher_id')
    teacher_subjects = query_db("SELECT * FROM subjects WHERE teacher_id = %s ORDER BY subject_name", (teacher_id,))

    subject_id_arg = request.args.get('subject_id')
    date_arg = request.args.get('attendance_date')
    is_edit_mode = (request.args.get('edit') == '1')

    selected_subject = None
    students = []
    is_already_marked = False
    existing_records = {}

    selected_date = date_arg if date_arg else date.today().strftime('%Y-%m-%d')

    if subject_id_arg:
        selected_subject = query_db(
            "SELECT * FROM subjects WHERE id = %s AND teacher_id = %s",
            (subject_id_arg, teacher_id),
            one=True
        )

        if selected_subject:
            students = query_db(
                "SELECT * FROM students WHERE class_name = %s ORDER BY roll_number",
                (selected_subject['class_name'],)
            )

            already_marked_rows = query_db(
                "SELECT student_id, status FROM attendance WHERE subject_id = %s AND attendance_date = %s",
                (selected_subject['id'], selected_date)
            )

            if already_marked_rows:
                is_already_marked = True
                existing_records = {row['student_id']: row['status'] for row in already_marked_rows}

    return render_template(
        'attendance/mark.html',
        teacher_subjects=teacher_subjects,
        selected_subject=selected_subject,
        selected_date=selected_date,
        today_date=date.today().strftime('%Y-%m-%d'),
        students=students,
        is_already_marked=is_already_marked,
        is_edit_mode=is_edit_mode,
        existing_records=existing_records
    )

@app.route('/attendance/save', methods=['POST'])
@login_required
def attendance_save():
    teacher_id = session.get('teacher_id')
    subject_id = request.form.get('subject_id')
    attendance_date = request.form.get('attendance_date')

    if not (subject_id and attendance_date):
        flash('Invalid submission parameters.', 'danger')
        return redirect(url_for('attendance_mark'))

    subject = query_db("SELECT * FROM subjects WHERE id = %s AND teacher_id = %s", (subject_id, teacher_id), one=True)
    if not subject:
        flash('Unauthorized subject.', 'danger')
        return redirect(url_for('attendance_mark'))

    existing = query_db(
        "SELECT id FROM attendance WHERE subject_id = %s AND attendance_date = %s LIMIT 1",
        (subject_id, attendance_date),
        one=True
    )
    if existing:
        flash(f"Attendance for '{subject['subject_name']}' on {attendance_date} has already been recorded! Duplicate entries are prevented.", 'warning')
        return redirect(url_for('attendance_mark', subject_id=subject_id, attendance_date=attendance_date))

    students = query_db("SELECT id, name FROM students WHERE class_name = %s", (subject['class_name'],))

    if not students:
        flash('No students to mark attendance for.', 'warning')
        return redirect(url_for('attendance_mark', subject_id=subject_id))

    try:
        saved_count = 0
        for student in students:
            status = request.form.get(f"status_{student['id']}", 'Absent')
            modify_db(
                """
                INSERT INTO attendance (student_id, subject_id, attendance_date, status)
                VALUES (%s, %s, %s, %s)
                """,
                (student['id'], subject_id, attendance_date, status)
            )
            saved_count += 1

        flash(f"Successfully recorded attendance for {saved_count} students on {attendance_date}!", 'success')
        return redirect(url_for('attendance_history'))
    except Exception as e:
        flash(f"Error saving attendance: {str(e)}", 'danger')
        return redirect(url_for('attendance_mark', subject_id=subject_id, attendance_date=attendance_date))

@app.route('/attendance/update', methods=['POST'])
@login_required
def attendance_update():
    teacher_id = session.get('teacher_id')
    subject_id = request.form.get('subject_id')
    attendance_date = request.form.get('attendance_date')

    if not (subject_id and attendance_date):
        flash('Invalid parameters for update.', 'danger')
        return redirect(url_for('attendance_mark'))

    subject = query_db("SELECT * FROM subjects WHERE id = %s AND teacher_id = %s", (subject_id, teacher_id), one=True)
    if not subject:
        flash('Unauthorized subject.', 'danger')
        return redirect(url_for('attendance_mark'))

    students = query_db("SELECT id, name FROM students WHERE class_name = %s", (subject['class_name'],))

    try:
        updated_count = 0
        for student in students:
            status = request.form.get(f"status_{student['id']}", 'Absent')
            modify_db(
                """
                UPDATE attendance 
                SET status = %s 
                WHERE student_id = %s AND subject_id = %s AND attendance_date = %s
                """,
                (status, student['id'], subject_id, attendance_date)
            )
            updated_count += 1

        flash(f"Successfully updated attendance records for {updated_count} students on {attendance_date}!", 'success')
        return redirect(url_for('attendance_mark', subject_id=subject_id, attendance_date=attendance_date))
    except Exception as e:
        flash(f"Error updating attendance: {str(e)}", 'danger')
        return redirect(url_for('attendance_mark', subject_id=subject_id, attendance_date=attendance_date))

@app.route('/attendance/history')
@login_required
def attendance_history():
    teacher_id = session.get('teacher_id')

    sessions = query_db(
        """
        SELECT 
            a.attendance_date,
            sub.id AS subject_id,
            sub.subject_code,
            sub.subject_name,
            sub.class_name,
            COUNT(a.id) AS total_marked,
            SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS present_count,
            SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) AS absent_count
        FROM attendance a
        JOIN subjects sub ON a.subject_id = sub.id
        WHERE sub.teacher_id = %s
        GROUP BY a.attendance_date, sub.id, sub.subject_code, sub.subject_name, sub.class_name
        ORDER BY a.attendance_date DESC
        """,
        (teacher_id,)
    )

    return render_template('attendance/history.html', sessions=sessions)

# -------------------------------------------------------------
# 6. Analytics Views & CSV Export
# -------------------------------------------------------------
@app.route('/analytics/high')
@login_required
def analytics_high():
    teacher_id = session.get('teacher_id')
    analytics_data = get_attendance_analytics(teacher_id)
    return render_template('analytics/high.html', analytics=analytics_data)

@app.route('/analytics/low')
@login_required
def analytics_low():
    teacher_id = session.get('teacher_id')
    analytics_data = get_attendance_analytics(teacher_id)

    today_records = query_db(
        "SELECT COUNT(*) AS total FROM email_logs WHERE sent_date = %s",
        (date.today(),),
        one=True
    )
    sent_today_count = today_records['total'] if today_records else 0

    return render_template(
        'analytics/low.html',
        analytics=analytics_data,
        sent_today_count=sent_today_count
    )

@app.route('/analytics/export-csv')
@login_required
def export_csv():
    teacher_id = session.get('teacher_id')
    analytics_data = get_attendance_analytics(teacher_id)
    all_students = analytics_data['students_high'] + analytics_data['students_low']

    if not all_students:
        flash('No attendance records available to export.', 'info')
        return redirect(url_for('dashboard'))

    export_rows = []
    for s in all_students:
        export_rows.append({
            'Roll Number': s['roll_number'],
            'Student Name': s['student_name'],
            'Class': s['class_name'],
            'Subject Code': s['subject_code'],
            'Subject Name': s['subject_name'],
            'Total Lectures': s['total_days'],
            'Present Days': s['present_days'],
            'Absent Days': s['absent_days'],
            'Attendance %': s['percentage'],
            'Compliance Status': 'Eligible (>=75%)' if s['percentage'] >= 75.0 else 'Shortage (<75%)'
        })

    df_export = pd.DataFrame(export_rows)
    csv_buffer = io.StringIO()
    df_export.to_csv(csv_buffer, index=False)

    return Response(
        csv_buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename=attendance_report_{date.today()}.csv"}
    )

# -------------------------------------------------------------
# 7. Warning Email Dispatches & Audit Logs
# -------------------------------------------------------------
@app.route('/warning-email/send-single', methods=['POST'])
@login_required
def send_single_warning_email():
    student_id = request.form.get('student_id')
    student_email = request.form.get('student_email')
    student_name = request.form.get('student_name')
    subject_id = request.form.get('subject_id')
    subject_name = request.form.get('subject_name')
    percentage = request.form.get('percentage')
    teacher_name = session.get('teacher_name')

    result = send_attendance_warning_email(
        student_id=student_id,
        student_email=student_email,
        student_name=student_name,
        subject_id=subject_id,
        subject_name=subject_name,
        percentage=percentage,
        teacher_name=teacher_name
    )

    category = 'success' if result['status'] in ('Sent', 'Simulated') else ('warning' if result['status'] == 'Duplicate' else 'danger')
    flash(result['message'], category)
    return redirect(url_for('analytics_low'))

@app.route('/warning-email/send-bulk', methods=['POST'])
@login_required
def send_bulk_warning_emails():
    teacher_id = session.get('teacher_id')
    teacher_name = session.get('teacher_name')
    analytics_data = get_attendance_analytics(teacher_id)

    at_risk_students = analytics_data['students_low']
    if not at_risk_students:
        flash('No at-risk students found below 75% attendance.', 'info')
        return redirect(url_for('analytics_low'))

    sent_count = 0
    duplicate_count = 0

    for st in at_risk_students:
        res = send_attendance_warning_email(
            student_id=st['student_id'],
            student_email=st['student_email'],
            student_name=st['student_name'],
            subject_id=st['subject_id'],
            subject_name=st['subject_name'],
            percentage=st['percentage'],
            teacher_name=teacher_name
        )
        if res['status'] in ('Sent', 'Simulated'):
            sent_count += 1
        elif res['status'] == 'Duplicate':
            duplicate_count += 1

    flash(f"Warning email process complete: {sent_count} warnings dispatched/logged, {duplicate_count} skipped (already sent today).", 'info')
    return redirect(url_for('email_logs_view'))

@app.route('/email-logs')
@login_required
def email_logs_view():
    logs = query_db(
        """
        SELECT 
            el.id,
            el.student_id,
            s.name AS student_name,
            s.roll_number,
            sub.subject_name,
            el.attendance_percentage,
            el.email_status,
            el.sent_date,
            el.message
        FROM email_logs el
        JOIN students s ON el.student_id = s.id
        JOIN subjects sub ON el.subject_id = sub.id
        ORDER BY el.id DESC
        """
    )
    return render_template('email_logs.html', logs=logs)

# -------------------------------------------------------------
# Error Handlers
# -------------------------------------------------------------
@app.errorhandler(404)
def page_not_found(e):
    return render_template('base.html', error_code=404, message="Requested page was not found."), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('base.html', error_code=500, message="An internal server error occurred."), 500

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)