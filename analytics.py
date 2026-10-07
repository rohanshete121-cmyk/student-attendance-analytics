import pandas as pd
from db import query_db

def get_attendance_analytics(teacher_id, subject_id=None, class_name=None):
    """
    Computes comprehensive attendance analytics using Pandas for a teacher's subjects.
    
    Guarantees:
    - Every student/subject attendance record belongs strictly to either:
        * Eligible (>= 75%)
        * At-Risk (< 75%)
    - The two categories are 100% mutually exclusive (zero overlap).
    - total_records = count_high + count_low
    """
    # 1. Fetch raw attendance records joined with student and subject details
    query = """
        SELECT 
            a.id AS attendance_id,
            a.student_id,
            s.roll_number,
            s.name AS student_name,
            s.class_name,
            s.email AS student_email,
            a.subject_id,
            sub.subject_code,
            sub.subject_name,
            a.attendance_date,
            a.status
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        JOIN subjects sub ON a.subject_id = sub.id
        WHERE sub.teacher_id = %s
    """
    params = [teacher_id]

    if subject_id:
        query += " AND sub.id = %s"
        params.append(subject_id)
        
    if class_name:
        query += " AND s.class_name = %s"
        params.append(class_name)

    raw_records = query_db(query, tuple(params))

    # Empty fallback structure if no attendance records exist yet
    default_response = {
        'total_records': 0,
        'total_students': 0,
        'count_high': 0,
        'count_low': 0,
        'overall_avg_percentage': 0.0,
        'students_high': [],
        'students_low': [],
        'subject_stats': [],
        'class_stats': [],
        'chart_data': {
            'subject_labels': [],
            'subject_percentages': [],
            'class_labels': [],
            'class_percentages': [],
            'distribution_labels': ['>= 75% (Eligible)', '< 75% (At Risk)'],
            'distribution_data': [0, 0]
        }
    }

    if not raw_records:
        return default_response

    # 2. Load into Pandas DataFrame for analysis
    df = pd.DataFrame(raw_records)

    # 3. Student-Subject Level Attendance Aggregation
    # Formula: Attendance % = (Present Days / Total Days) * 100
    student_subject_group = df.groupby([
        'student_id', 'roll_number', 'student_name', 
        'class_name', 'student_email', 'subject_id', 
        'subject_code', 'subject_name'
    ])

    student_records = []
    for (s_id, roll, s_name, cls, s_email, sub_id, sub_code, sub_name), group in student_subject_group:
        total_days = len(group)
        present_days = int((group['status'] == 'Present').sum())
        absent_days = int((group['status'] == 'Absent').sum())
        percentage = round((present_days / total_days) * 100.0, 2) if total_days > 0 else 0.0

        student_records.append({
            'student_id': int(s_id),
            'roll_number': str(roll),
            'student_name': str(s_name),
            'class_name': str(cls),
            'student_email': str(s_email),
            'subject_id': int(sub_id),
            'subject_code': str(sub_code),
            'subject_name': str(sub_name),
            'total_days': total_days,
            'present_days': present_days,
            'absent_days': absent_days,
            'percentage': percentage,
            'is_at_risk': percentage < 75.0
        })

    students_df = pd.DataFrame(student_records)

    # Strict segmentation: Eligible (>= 75.0%) and At-Risk (< 75.0%)
    # Guaranteed mutually exclusive and non-overlapping
    high_df = students_df[students_df['percentage'] >= 75.0]
    low_df = students_df[students_df['percentage'] < 75.0]

    students_high = high_df.sort_values(by='percentage', ascending=False).to_dict('records')
    students_low = low_df.sort_values(by='percentage', ascending=True).to_dict('records')

      # Overall student-level attendance for Dashboard KPI
    student_overall = (
        students_df
        .groupby(
            ['student_id', 'roll_number', 'student_name', 'class_name'],
            as_index=False
        )
        .agg(
            total_days=('total_days', 'sum'),
            present_days=('present_days', 'sum')
        )
    )

    student_overall['percentage'] = (
        student_overall['present_days'] /
        student_overall['total_days'] * 100.0
    ).round(2)

    # Count each student only once
    overall_high_df = student_overall[
        student_overall['percentage'] >= 75.0
    ]

    overall_low_df = student_overall[
        student_overall['percentage'] < 75.0
    ]

    count_high = len(overall_high_df)
    count_low = len(overall_low_df)
    total_students = len(student_overall)
    total_records = len(students_df)

    # Safety check
    assert count_high + count_low == total_students, \
        "Eligible and At-Risk counts must equal total unique students."    # 4. Subject-wise Analysis
    subject_group = df.groupby(['subject_code', 'subject_name'])
    subject_stats = []
    for (code, name), group in subject_group:
        sub_total = len(group)
        sub_present = (group['status'] == 'Present').sum()
        sub_pct = round((sub_present / sub_total) * 100.0, 1) if sub_total > 0 else 0.0
        subject_stats.append({
            'subject_code': code,
            'subject_name': name,
            'total_entries': sub_total,
            'percentage': sub_pct
        })
    subject_stats.sort(key=lambda x: x['percentage'], reverse=True)

    # 5. Class-wise Analysis
    class_group = df.groupby('class_name')
    class_stats = []
    for cls, group in class_group:
        cls_total = len(group)
        cls_present = (group['status'] == 'Present').sum()
        cls_pct = round((cls_present / cls_total) * 100.0, 1) if cls_total > 0 else 0.0
        class_stats.append({
            'class_name': cls,
            'total_entries': cls_total,
            'percentage': cls_pct
        })
    class_stats.sort(key=lambda x: x['class_name'])

    # 6. Overall Metrics
    total_entries = len(df)
    overall_present = int((df['status'] == 'Present').sum())
    overall_avg_percentage = round((overall_present / total_entries) * 100.0, 1) if total_entries > 0 else 0.0

    # Prepare Chart.js data
    chart_data = {
        'subject_labels': [f"{s['subject_code']} - {s['subject_name']}" for s in subject_stats],
        'subject_percentages': [s['percentage'] for s in subject_stats],
        'class_labels': [c['class_name'] for c in class_stats],
        'class_percentages': [c['percentage'] for c in class_stats],
        'distribution_labels': ['>= 75% (Eligible)', '< 75% (At Risk)'],
        'distribution_data': [count_high, count_low]
    }

    return {
        'total_records': total_records,
        'total_students': len(students_df['student_id'].unique()),
        'count_high': count_high,
        'count_low': count_low,
        'overall_avg_percentage': overall_avg_percentage,
        'students_high': students_high,
        'students_low': students_low,
        'subject_stats': subject_stats,
        'class_stats': class_stats,
        'chart_data': chart_data
    }
