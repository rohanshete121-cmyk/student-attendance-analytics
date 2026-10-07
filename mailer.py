from datetime import date
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import Config
from db import query_db, modify_db

def is_warning_already_sent_today(student_id, subject_id):
    """
    Checks if a warning email has already been sent to this student
    for this subject on today's date, preventing spam and duplicate emails.
    """
    today = date.today()
    record = query_db(
        """
        SELECT id FROM email_logs 
        WHERE student_id = %s AND subject_id = %s AND sent_date = %s
        """,
        (student_id, subject_id, today),
        one=True
    )
    return record is not None

def log_email_to_db(student_id, subject_id, percentage, status, message_body):
    """
    Records an entry in the email_logs table for audit tracking.
    """
    today = date.today()
    modify_db(
        """
        INSERT INTO email_logs 
        (student_id, subject_id, attendance_percentage, email_status, sent_date, message)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (student_id, subject_id, percentage, status, today, message_body)
    )

def send_attendance_warning_email(student_id, student_email, student_name, subject_id, subject_name, percentage, teacher_name):
    """
    Sends an attendance warning email to students below 75%.
    - Formats required message content.
    - Prevents duplicates for the same day.
    - Uses SMTP if configured in .env, or gracefully simulates delivery for safe local testing.
    """
    # Check for duplicate prevention
    if is_warning_already_sent_today(student_id, subject_id):
        return {
            'status': 'Duplicate',
            'message': f"A warning email was already sent to {student_name} today."
        }

    subject_line = f"Urgent: Attendance Shortage Warning - {subject_name}"
    email_body = (
        f"Dear {student_name},\n\n"
        f"Your attendance in {subject_name} is below 75%. Your current attendance is {percentage}%.\n"
        f"Please attend classes regularly to improve your attendance.\n\n"
        f"Best regards,\n"
        f"{teacher_name}\n"
        f"Department of Computer Applications"
    )

    # Check if SMTP credentials are configured in .env
    is_smtp_configured = bool(Config.MAIL_USERNAME and Config.MAIL_PASSWORD)

    if not is_smtp_configured:
        # Graceful simulation mode for student demo / BCA project defense
        status_text = 'Simulated'
        log_email_to_db(student_id, subject_id, percentage, status_text, email_body)
        return {
            'status': 'Simulated',
            'message': f"[Demo Mode] Warning recorded for {student_name} ({percentage}%). Real email skipped (set MAIL_USERNAME/PASSWORD in .env)."
        }

    try:
        msg = MIMEMultipart()
        msg['From'] = Config.MAIL_DEFAULT_SENDER or Config.MAIL_USERNAME
        msg['To'] = student_email
        msg['Subject'] = subject_line
        msg.attach(MIMEText(email_body, 'plain'))

        server = smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT, timeout=10)
        if Config.MAIL_USE_TLS:
            server.starttls()
        server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
        server.send_message(msg)
        server.quit()

        log_email_to_db(student_id, subject_id, percentage, 'Sent', email_body)
        return {
            'status': 'Sent',
            'message': f"Warning email successfully delivered to {student_name} ({student_email})."
        }
    except Exception as e:
        log_email_to_db(student_id, subject_id, percentage, 'Failed', f"Error: {str(e)}")
        return {
            'status': 'Failed',
            'message': f"Failed to send email to {student_email}: {str(e)}"
        }
