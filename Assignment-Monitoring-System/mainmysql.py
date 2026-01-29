from flask import Flask,Response, make_response, render_template, request, redirect, url_for, session, flash, make_response
import mysql.connector
import os
import io
from datetime import datetime, date
import csv
from io import StringIO
from twilio.rest import Client
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
app.secret_key = 'superadmin123'

# MySQL configuration
MYSQL_CONFIG = {
    'host': 'localhost',
    'user': 'root',  
    'password': '',  
    'database': 'assignment_monitoring_system_db',  
    'raise_on_warnings': True
}

# Helper to get college name
def get_college_name():
    if 'college_code' in session:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        c = conn.cursor()
        c.execute('SELECT college_name FROM colleges WHERE college_code = %s', (session['college_code'],))
        result = c.fetchone()
        conn.close()
        return result[0] if result else ''
    return ''

@app.route('/static/<path:filename>')
def static_files(filename):
    response = app.send_static_file(filename)
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response

# Home page
@app.route('/')
def home():
    return render_template('home.html')

# Admin login
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        c = conn.cursor()
        c.execute('SELECT * FROM colleges WHERE username = %s AND password = %s', (username, password))
        admin = c.fetchone()
        conn.close()
        if admin:
            session['user_type'] = 'admin'
            session['college_code'] = admin[0]
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid username or password')
    return render_template('admin_login.html')

# Admin create account
@app.route('/admin_create_account', methods=['GET', 'POST'])
def admin_create_account():
    if request.method == 'POST':
        college_code = request.form['college_code']
        college_name = request.form['college_name']
        university = request.form['university']
        admin_name = request.form['admin_name']
        username = request.form['username']
        password = request.form['password']
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        c = conn.cursor()
        try:
            c.execute('INSERT INTO colleges (college_code, college_name, university, admin_name, username, password) VALUES (%s, %s, %s, %s, %s, %s)',
                      (college_code, college_name, university, admin_name, username, password))
            conn.commit()
            return redirect(url_for('admin_login'))
        except mysql.connector.IntegrityError:
            flash('Username or college code already exists')
        finally:
            conn.close()
    return render_template('admin_create_account.html')

# Staff login
# Staff login
@app.route('/staff_login', methods=['GET', 'POST'])
def staff_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        c = conn.cursor()
        # Check tutor (academic year)
        c.execute('SELECT department_id, start_year FROM academic_years WHERE username = %s AND password = %s', (username, password))
        tutor = c.fetchone()
        if tutor:
            session['user_type'] = 'tutor'
            session['department_id'] = tutor[0]
            session['start_year'] = tutor[1]
            conn.close()
            return redirect(url_for('department_page', department_id=tutor[0], start_year=tutor[1]))
        # Check subject staff
        c.execute('SELECT subject_code, semester_number, department_id, start_year FROM subjects WHERE username = %s AND password = %s', (username, password))
        subject = c.fetchone()
        if subject:
            session['user_type'] = 'staff'
            session['subject_code'] = subject[0]
            session['semester_number'] = subject[1]
            session['department_id'] = subject[2]
            session['start_year'] = subject[3]
            conn.close()
            # Redirect to staff dashboard instead of assignment page
            return redirect(url_for('staff_dashboard'))
        flash('Invalid username or password')
        conn.close()
    return render_template('staff_login.html')


# Admin Dashboard
@app.route('/admin_dashboard')
def admin_dashboard():
    if 'user_type' not in session or session['user_type'] != 'admin':
        return redirect(url_for('home'))

    conn = mysql.connector.connect(**MYSQL_CONFIG)
    c = conn.cursor()

    # Get total departments count
    c.execute('SELECT COUNT(*) FROM departments WHERE college_code = %s', (session['college_code'],))
    department_count = c.fetchone()[0]

    # Get total staff count
    c.execute('SELECT COUNT(*) FROM subjects s JOIN departments d ON s.department_id = d.department_id WHERE d.college_code = %s', (session['college_code'],))
    staff_count = c.fetchone()[0]

    # Get total students count
    c.execute('SELECT COUNT(*) FROM students s JOIN departments d ON s.department_id = d.department_id WHERE d.college_code = %s', (session['college_code'],))
    student_count = c.fetchone()[0]

    conn.close()

    college_name = get_college_name()

    return render_template(
        'admin_dashboard.html',
        college_name=college_name,
        department_count=department_count,
        staff_count=staff_count,
        student_count=student_count
    )
    
    
# Staff Dashboard Route
@app.route('/staff_dashboard')
def staff_dashboard():
    if 'user_type' not in session or session['user_type'] != 'staff':
        return redirect(url_for('home'))

    conn = mysql.connector.connect(**MYSQL_CONFIG)
    c = conn.cursor()

    # Fetch department and staff info
    department_id = session.get('department_id')
    start_year = session.get('start_year')
    subject_code = session.get('subject_code')
    semester_number = session.get('semester_number')

    c.execute('SELECT department_name FROM departments WHERE department_id = %s', (department_id,))
    department_name = c.fetchone()[0]

    # Subject name & staff name
    c.execute('SELECT subject_name, staff_name FROM subjects WHERE subject_code = %s', (subject_code,))
    subject_info = c.fetchone()
    subject_name = subject_info[0]
    staff_name = subject_info[1]


    conn.close()

    return render_template('staff_dashboard.html',
                           department_name=department_name,
                           subject_name=subject_name,
                           staff_name=staff_name,  
                           department_id=department_id,
                           start_year=start_year,
                           semester_number=semester_number,
                           subject_code=subject_code)


# Departments page
@app.route('/departments')
def departments():
    if 'user_type' not in session or session['user_type'] != 'admin':
        return redirect(url_for('home'))
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    c = conn.cursor()
    college_name = get_college_name()
    c.execute('SELECT department_id, department_name FROM departments WHERE college_code = %s', (session['college_code'],))
    departments = c.fetchall()
    conn.close()
    return render_template('departments.html', college_name=college_name, departments=departments)

# Add department
@app.route('/add_department', methods=['POST'])
def add_department():
    if 'user_type' not in session or session['user_type'] != 'admin':
        return redirect(url_for('home'))
    department_id = request.form['department_id']
    department_name = request.form['department_name']
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO departments (department_id, department_name, college_code) VALUES (%s, %s, %s)',
                  (department_id, department_name, session['college_code']))
        conn.commit()
    except mysql.connector.IntegrityError:
        flash('Department ID already exists')
    conn.close()
    return redirect(url_for('departments'))

# Edit department
@app.route('/edit_department/<old_department_id>', methods=['POST'])
def edit_department(old_department_id):
    if 'user_type' not in session or session['user_type'] != 'admin':
        return redirect(url_for('home'))

    new_department_id = request.form['department_id']
    new_department_name = request.form['department_name']

    conn = mysql.connector.connect(**MYSQL_CONFIG)
    c = conn.cursor()
    try:
        c.execute('''UPDATE departments 
                     SET department_id = %s, department_name = %s 
                     WHERE department_id = %s''',
                  (new_department_id, new_department_name, old_department_id))
        conn.commit()
    except mysql.connector.IntegrityError:
        flash("Department ID already exists! Please choose another ID.", "error")
        conn.close()
        return redirect(url_for('departments'))

    conn.close()
    flash("Department updated successfully!", "success")
    return redirect(url_for('departments', department_id=new_department_id))

# Delete department
@app.route('/delete_department/<department_id>')
def delete_department(department_id):
    if 'user_type' not in session or session['user_type'] != 'admin':
        return redirect(url_for('home'))
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    c = conn.cursor()
    c.execute('DELETE FROM departments WHERE department_id = %s', (department_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('departments'))

# Academic years page
@app.route('/academic_years/<department_id>')
def academic_years(department_id):
    if 'user_type' not in session or session['user_type'] != 'admin':
        return redirect(url_for('home'))
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    c = conn.cursor()
    college_name = get_college_name()
    c.execute('SELECT department_name FROM departments WHERE department_id = %s', (department_id,))
    department_name = c.fetchone()[0]
    c.execute('SELECT start_year, end_year, tutor_name, username FROM academic_years WHERE department_id = %s', (department_id,))
    years = c.fetchall()
    conn.close()
    return render_template('academic_years.html', college_name=college_name, department_name=department_name, department_id=department_id, years=years)

# Add academic year
@app.route('/add_academic_year/<department_id>', methods=['POST'])
def add_academic_year(department_id):
    if 'user_type' not in session or session['user_type'] != 'admin':
        return redirect(url_for('home'))
    start_year = int(request.form['start_year'])
    end_year = int(request.form['end_year'])
    tutor_name = request.form['tutor_name']
    username = request.form['username']
    password = request.form['password']
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO academic_years (start_year, end_year, tutor_name, username, password, department_id) VALUES (%s, %s, %s, %s, %s, %s)',
                  (start_year, end_year, tutor_name, username, password, department_id))
        conn.commit()
        # Auto-add semesters
        total_years = end_year - start_year
        num_semesters = 6 if total_years == 3 else 8
        for sem in range(1, num_semesters + 1):
            c.execute('INSERT IGNORE INTO semesters (semester_number, department_id, start_year) VALUES (%s, %s, %s)',
                      (sem, department_id, start_year))
        conn.commit()
    except mysql.connector.IntegrityError:
        flash('Username or academic year (start-end) already exists')
    conn.close()
    return redirect(url_for('academic_years', department_id=department_id))

# Edit academic year
@app.route('/edit_academic_year/<department_id>/<start_year>', methods=['POST'])
def edit_academic_year(department_id, start_year):
    if 'user_type' not in session or session['user_type'] != 'admin':
        return redirect(url_for('home'))
    end_year = int(request.form['end_year'])
    tutor_name = request.form['tutor_name']
    username = request.form['username']
    password = request.form['password']
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    c = conn.cursor()
    c.execute('UPDATE academic_years SET end_year = %s, tutor_name = %s, username = %s, password = %s WHERE department_id = %s AND start_year = %s',
              (end_year, tutor_name, username, password, department_id, start_year))
    conn.commit()
    conn.close()
    return redirect(url_for('academic_years', department_id=department_id))

# Delete academic year
@app.route('/delete_academic_year/<department_id>/<start_year>')
def delete_academic_year(department_id, start_year):
    if 'user_type' not in session or session['user_type'] != 'admin':
        return redirect(url_for('home'))
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    c = conn.cursor()
    c.execute('DELETE FROM academic_years WHERE department_id = %s AND start_year = %s', (department_id, start_year))
    conn.commit()
    conn.close()
    return redirect(url_for('academic_years', department_id=department_id))

# Department page
@app.route('/department_page/<department_id>/<start_year>')
def department_page(department_id, start_year):
    if 'user_type' not in session:
        return redirect(url_for('home'))
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    c = conn.cursor()
    college_name = get_college_name() if session['user_type'] == 'admin' else ''
    c.execute('SELECT department_name FROM departments WHERE department_id = %s', (department_id,))
    department_name = c.fetchone()[0]
    c.execute('SELECT tutor_name FROM academic_years WHERE department_id = %s AND start_year = %s', (department_id, start_year))
    tutor_name = c.fetchone()[0]
    conn.close()
    return render_template('department_page.html', college_name=college_name, department_name=department_name,
                           tutor_name=tutor_name, department_id=department_id, start_year=start_year)

# Student list page
@app.route('/student_list/<department_id>/<start_year>')
def student_list(department_id, start_year):
    if 'user_type' not in session:
        return redirect(url_for('home'))
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    c = conn.cursor()
    college_name = get_college_name() if session['user_type'] == 'admin' else ''
    c.execute('SELECT department_name FROM departments WHERE department_id = %s', (department_id,))
    department_name = c.fetchone()[0]
    c.execute('SELECT regno, name, phone FROM students WHERE department_id = %s AND start_year = %s', (department_id, start_year))
    students = c.fetchall()
    conn.close()
    return render_template('student_list.html', college_name=college_name, department_name=department_name,
                           start_year=start_year, department_id=department_id, students=students)

# Add student
@app.route('/add_student/<department_id>/<start_year>', methods=['POST'])
def add_student(department_id, start_year):
    if 'user_type' not in session:
        return redirect(url_for('home'))
    regno = request.form['regno']
    name = request.form['name']
    phone = request.form['phone']
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO students (regno, name, phone, department_id, start_year) VALUES (%s, %s, %s, %s, %s)',
                  (regno, name, phone, department_id, start_year))
        conn.commit()
    except mysql.connector.IntegrityError:
        flash('Registration number already exists')
    conn.close()
    return redirect(url_for('student_list', department_id=department_id, start_year=start_year))

# Edit student
@app.route('/edit_student/<department_id>/<start_year>/', methods=['POST'])
def edit_student(department_id, start_year):
    if 'user_type' not in session:
        return redirect(url_for('home'))

    old_regno = request.form['old_regno']  
    new_regno = request.form['regno']       
    name = request.form['name']
    phone = request.form['phone']

    try:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        c = conn.cursor()
        c.execute(
            'UPDATE students SET regno=%s, name=%s, phone=%s WHERE regno=%s',
            (new_regno, name, phone, old_regno)
        )
        conn.commit()
    except mysql.connector.IntegrityError:
        flash("RegNo already exists. Please use a different one.", "error")
    finally:
        conn.close()

    return redirect(url_for('student_list', department_id=department_id, start_year=start_year))


# Delete student
@app.route('/delete_student/<department_id>/<start_year>/<regno>')
def delete_student(department_id, start_year, regno):
    if 'user_type' not in session:
        return redirect(url_for('home'))
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    c = conn.cursor()
    c.execute('DELETE FROM students WHERE regno = %s', (regno,))
    conn.commit()
    conn.close()
    return redirect(url_for('student_list', department_id=department_id, start_year=start_year))

# Semester page
@app.route('/semester/<department_id>/<start_year>')
def semester(department_id, start_year):
    if 'user_type' not in session:
        return redirect(url_for('home'))
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    c = conn.cursor()
    college_name = get_college_name() if session['user_type'] == 'admin' else ''
    c.execute('SELECT department_name FROM departments WHERE department_id = %s', (department_id,))
    department_name = c.fetchone()[0]
    c.execute('SELECT semester_number FROM semesters WHERE department_id = %s AND start_year = %s ORDER BY semester_number', (department_id, start_year))
    semesters = c.fetchall()
    conn.close()
    return render_template('semester.html', college_name=college_name, department_name=department_name,
                           start_year=start_year, department_id=department_id, semesters=semesters)


# Subjects page
@app.route('/subjects/<department_id>/<start_year>/<semester_number>')
def subjects(department_id, start_year, semester_number):
    if 'user_type' not in session:
        return redirect(url_for('home'))
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    c = conn.cursor()
    college_name = get_college_name()
    c.execute('SELECT department_name FROM departments WHERE department_id = %s', (department_id,))
    department_name = c.fetchone()[0]
    c.execute( '''
    SELECT subject_code, subject_name, staff_name, username
    FROM subjects
    WHERE department_id = %s AND start_year = %s AND semester_number = %s
    ORDER BY subject_name ASC
    ''', (department_id, start_year, semester_number))


    subject_list = c.fetchall()
    conn.close()
    return render_template('subjects.html', college_name=college_name, department_name=department_name,
                           start_year=start_year, semester_number=semester_number, department_id=department_id, subjects=subject_list)

# Add subject
@app.route('/add_subject/<department_id>/<start_year>/<semester_number>', methods=['POST'])
def add_subject(department_id, start_year, semester_number):
    if 'user_type' not in session:
        return redirect(url_for('home'))
    subject_code = request.form['subject_code']
    subject_name = request.form['subject_name']
    staff_name = request.form['staff_name']
    username = request.form['username']
    password = request.form['password']
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO subjects (subject_code, subject_name, staff_name, username, password, semester_number, department_id, start_year) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
                  (subject_code, subject_name, staff_name, username, password, semester_number, department_id, start_year))
        conn.commit()
    except mysql.connector.IntegrityError:
        flash('Subject code or username already exists')
    conn.close()
    return redirect(url_for('subjects', department_id=department_id, start_year=start_year, semester_number=semester_number))

#edit subject 
@app.route('/edit_subject/<department_id>/<start_year>/<semester_number>', methods=['POST'])
def edit_subject(department_id, start_year, semester_number):
    if 'user_type' not in session:
        return redirect(url_for('home'))

    old_code = request.form['old_subject_code']
    new_code = request.form['subject_code']
    subject_name = request.form['subject_name']
    staff_name = request.form['staff_name']
    username = request.form['username']
    password = request.form['password']

    conn = mysql.connector.connect(**MYSQL_CONFIG)
    c = conn.cursor()

    # Check if new_code already exists and is different from old_code
    c.execute('SELECT COUNT(*) FROM subjects WHERE subject_code = %s', (new_code,))
    count = c.fetchone()[0]

    if count > 0 and new_code != old_code:
        conn.close()
        flash(f"Subject Code '{new_code}' already exists!", "error")
        return redirect(url_for('subjects', department_id=department_id, start_year=start_year, semester_number=semester_number))

    # Update subject
    c.execute('''
        UPDATE subjects
        SET subject_code=%s, subject_name=%s, staff_name=%s, username=%s, password=%s
        WHERE subject_code=%s
    ''', (new_code, subject_name, staff_name, username, password, old_code))
    conn.commit()
    conn.close()

    flash("Subject updated successfully!", "success")
    return redirect(url_for('subjects', department_id=department_id, start_year=start_year, semester_number=semester_number))

# Delete subject
@app.route('/delete_subject/<department_id>/<start_year>/<semester_number>/<subject_code>')
def delete_subject(department_id, start_year, semester_number, subject_code):
    if 'user_type' not in session:
        return redirect(url_for('home'))
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    c = conn.cursor()
    c.execute('DELETE FROM subjects WHERE subject_code = %s', (subject_code,))
    conn.commit()
    conn.close()
    return redirect(url_for('subjects', department_id=department_id, start_year=start_year, semester_number=semester_number))

# Subject assignment page
@app.route('/subject_assignment/<subject_code>/<semester_number>/<department_id>/<start_year>')
def subject_assignment(subject_code, semester_number, department_id, start_year):
    if 'user_type' not in session:
        return redirect(url_for('home'))
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    c = conn.cursor()
    c.execute('SELECT subject_name FROM subjects WHERE subject_code = %s', (subject_code,))
    subject_name = c.fetchone()[0]
    c.execute('SELECT department_name FROM departments WHERE department_id = %s', (department_id,))
    department_name = c.fetchone()[0]
    c.execute('SELECT assignment_num, assignment_name, due_date FROM assignments WHERE subject_code = %s', (subject_code,))
    assignments = c.fetchall()
    conn.close()
    return render_template('subject_assignment.html', subject_name=subject_name, department_name=department_name,
                           semester_number=semester_number, start_year=start_year, department_id=department_id,
                           subject_code=subject_code, assignments=assignments)

# Add assignment
@app.route('/add_assignment/<subject_code>/<semester_number>/<department_id>/<start_year>', methods=['POST'])
def add_assignment(subject_code, semester_number, department_id, start_year):
    if 'user_type' not in session:
        return redirect(url_for('home'))
    
    assignment_num = request.form['assignment_num']
    assignment_name = request.form['assignment_name']
    due_date = request.form['due_date']

    conn = mysql.connector.connect(**MYSQL_CONFIG)
    c = conn.cursor()

    try:
        #  Insert assignment
        c.execute('INSERT INTO assignments (assignment_num, assignment_name, due_date, subject_code) VALUES (%s, %s, %s, %s)',
                  (assignment_num, assignment_name, due_date, subject_code))
        conn.commit()

        # Insert all students as "Not Submitted" in student_assignments table
        c.execute('SELECT regno, name, phone FROM students')  # Get phone from students table
        students = c.fetchall()
        for regno, name, phone in students:
            c.execute('INSERT INTO submissions (regno, assignment_num, subject_code, submitted) VALUES (%s,%s,%s,%s)',
                      (regno, assignment_num, subject_code, 0))
        conn.commit()

        # Send WhatsApp notification to all students
        message_body = f'New Assignment "{assignment_name}" (A{assignment_num}) is now available for subject {subject_code}. Submit before {due_date}.'
        for regno, name, phone in students:
            client.messages.create(
                body=message_body,
                from_='whatsapp:+14155238886',  # Twilio WhatsApp number
                to=f'whatsapp:+91{phone}'
            )

        flash('Assignment added and students notified via WhatsApp', 'success')

    except mysql.connector.IntegrityError:
        flash('Assignment number already exists for this subject', 'error')

    conn.close()
    return redirect(url_for('subject_assignment', subject_code=subject_code, semester_number=semester_number, department_id=department_id, start_year=start_year))

# Edit assignment

@app.route('/edit_assignment/<subject_code>/<semester_number>/<department_id>/<start_year>', methods=['POST'])
def edit_assignment(subject_code, semester_number, department_id, start_year):
    if 'user_type' not in session:
        return redirect(url_for('home'))

    original_num = request.form['original_assignment_num']
    new_num = request.form['assignment_num']
    assignment_name = request.form['assignment_name']
    due_date = request.form['due_date']

    conn = mysql.connector.connect(**MYSQL_CONFIG)
    c = conn.cursor()
    try:
        c.execute('''
            UPDATE assignments
            SET assignment_num = %s, assignment_name = %s, due_date = %s
            WHERE subject_code = %s AND assignment_num = %s
        ''', (new_num, assignment_name, due_date, subject_code, original_num))
        conn.commit()
        flash('Assignment updated successfully!', 'success')
    except mysql.connector.errors.IntegrityError as e:
        if e.errno == 1062:  # Duplicate entry
            flash(f'Error: Assignment number "{new_num}" already exists for this subject!', 'danger')
        else:
            flash('An error occurred while updating assignment.', 'danger')
    finally:
        conn.close()

    return redirect(url_for('subject_assignment', subject_code=subject_code, semester_number=semester_number, department_id=department_id, start_year=start_year))

# Delete assignment
@app.route('/delete_assignment/<subject_code>/<assignment_num>/<semester_number>/<department_id>/<start_year>')
def delete_assignment(subject_code, assignment_num, semester_number, department_id, start_year):
    if 'user_type' not in session:
        return redirect(url_for('home'))
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    c = conn.cursor()
    c.execute('DELETE FROM assignments WHERE subject_code = %s AND assignment_num = %s', (subject_code, assignment_num))
    conn.commit()
    conn.close()
    return redirect(url_for('subject_assignment', subject_code=subject_code, semester_number=semester_number, department_id=department_id, start_year=start_year))

# Download CSV
@app.route('/download_csv/<subject_code>/<semester_number>/<department_id>/<start_year>')
def download_csv(subject_code, semester_number, department_id, start_year):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    c = conn.cursor()

    # Subject name
    c.execute('SELECT subject_name FROM subjects WHERE subject_code = %s', (subject_code,))
    subject_name = c.fetchone()[0]

    # Department name
    c.execute('SELECT department_name FROM departments WHERE department_id = %s', (department_id,))
    dept_name = c.fetchone()[0]

    # Academic year
    c.execute('SELECT start_year, end_year FROM academic_years WHERE start_year = %s AND department_id = %s', (start_year, department_id))
    ay = c.fetchone()
    academic_year = f"{ay[0]}-{ay[1]}" if ay else ""

    # Assignments for this subject
    c.execute('SELECT assignment_num, assignment_name FROM assignments WHERE subject_code = %s ORDER BY assignment_num', (subject_code,))
    assignments = c.fetchall()  # tuples (assignment_num, assignment_name)

    # Students in this department & start_year
    c.execute('SELECT regno, name FROM students WHERE department_id = %s AND start_year = %s', (department_id, start_year))
    students = c.fetchall()

    # Prepare CSV rows
    rows = []
    for regno, name in students:
        row = [f"{regno}", name]
        for ass_num, ass_name in assignments:
            c.execute('SELECT submitted FROM submissions WHERE regno = %s AND assignment_num = %s AND subject_code = %s', (regno, ass_num, subject_code))
            stat = c.fetchone()
            row.append('Submitted' if stat and stat[0] else 'Not Submitted')
        rows.append(row)

    conn.close()

    # Write CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Title rows
    writer.writerow([f"Academic Year: {academic_year}"])
    writer.writerow([f"Department: {dept_name}"])
    writer.writerow([f"Semester: {semester_number}"])
    writer.writerow([f"Subject: {subject_name}"])
    writer.writerow([])

    # Headers
    headers = ['RegNo', 'Name'] + [f"{num}-{name}" for num, name in assignments]
    writer.writerow(headers)

    # Student rows
    writer.writerows(rows)

    # Response
    response = Response(output.getvalue(), mimetype="text/csv")
    filename = f"{subject_name}_{datetime.now().strftime('%Y%m%d')}.csv"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response


# Assignment page
@app.route('/assignment/<subject_code>/<assignment_num>/<semester_number>/<department_id>/<start_year>')
def assignment(subject_code, assignment_num, semester_number, department_id, start_year):
    if 'user_type' not in session:
        return redirect(url_for('home'))
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    c = conn.cursor()
    c.execute('SELECT subject_name FROM subjects WHERE subject_code = %s', (subject_code,))
    subject_name = c.fetchone()[0]
    c.execute('SELECT department_name FROM departments WHERE department_id = %s', (department_id,))
    department_name = c.fetchone()[0]
    c.execute('SELECT assignment_name, due_date FROM assignments WHERE subject_code = %s AND assignment_num = %s', (subject_code, assignment_num))
    assignment_info = c.fetchone()
    assignment_name, due_date = assignment_info if assignment_info else ('', '')
    c.execute('''
        SELECT s.regno, s.name, sub.submitted
        FROM students s
        LEFT JOIN submissions sub ON s.regno = sub.regno AND sub.assignment_num = %s AND sub.subject_code = %s
        WHERE s.department_id = %s AND s.start_year = %s
    ''', (assignment_num, subject_code, department_id, start_year))
    submissions = c.fetchall()
    conn.close()
    return render_template('assignment.html', subject_name=subject_name, department_name=department_name,
                           semester_number=semester_number, start_year=start_year, department_id=department_id,
                           subject_code=subject_code, assignment_num=assignment_num, assignment_name=assignment_name,
                           due_date=due_date, submissions=submissions)

# Toggle submission
@app.route('/toggle_submission/<regno>/<assignment_num>/<subject_code>', methods=['POST'])
def toggle_submission(regno, assignment_num, subject_code):
    if 'user_type' not in session:
        return redirect(url_for('home'))
    submitted = request.form['submitted'] == 'true'
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    c = conn.cursor()
    c.execute('INSERT INTO submissions (regno, assignment_num, subject_code, submitted) VALUES (%s, %s, %s, %s) ON DUPLICATE KEY UPDATE submitted = %s',
              (regno, assignment_num, subject_code, submitted, submitted))
    conn.commit()
    conn.close()
    return 'OK'

# Submit all
@app.route('/submit_all/<subject_code>/<assignment_num>/<semester_number>/<department_id>/<start_year>', methods=['POST'])
def submit_all(subject_code, assignment_num, semester_number, department_id, start_year):
    if 'user_type' not in session:
        return redirect(url_for('home'))
    submit = request.form['submit_all'] == 'true'
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    c = conn.cursor()
    c.execute('SELECT regno FROM students WHERE department_id = %s AND start_year = %s', (department_id, start_year))
    students = c.fetchall()
    for student in students:
        c.execute('INSERT INTO submissions (regno, assignment_num, subject_code, submitted) VALUES (%s, %s, %s, %s) ON DUPLICATE KEY UPDATE submitted = %s',
                  (student[0], assignment_num, subject_code, submit, submit))
    conn.commit()
    conn.close()
    return redirect(url_for('assignment', subject_code=subject_code, assignment_num=assignment_num, semester_number=semester_number, department_id=department_id, start_year=start_year))

# Save submissions
@app.route('/save_submissions/<subject_code>/<assignment_num>/<semester_number>/<department_id>/<start_year>')
def save_submissions(subject_code, assignment_num, semester_number, department_id, start_year):
    flash('Submitted successfully', 'success')
    return redirect(url_for('assignment', subject_code=subject_code, assignment_num=assignment_num, semester_number=semester_number, department_id=department_id, start_year=start_year))

# Send reminder
account_sid = "your account_sid" #i am remove my sid for security
auth_token = "your auth token"   #i am remove my token for security
client = Client(account_sid, auth_token)

# @app.route('/send_reminder/<subject_code>/<assignment_num>', methods=['POST'])
# def send_reminder(subject_code, assignment_num):
#     print("[CRON] send_reminder triggered")
#     conn = mysql.connector.connect(**MYSQL_CONFIG)
#     c = conn.cursor()

#     # Get assignment details
#     c.execute("""
#         SELECT a.assignment_num, a.assignment_name, s.subject_name, a.due_date
#         FROM assignments a
#         JOIN subjects s ON a.subject_code = s.subject_code
#         WHERE a.assignment_num = %s AND a.subject_code = %s
#     """, (assignment_num, subject_code))
#     assignment = c.fetchone()

#     if not assignment:
#         conn.close()
#         return "Invalid assignment"

#     assignment_num, assignment_name, subject_name, due_date = assignment
#     due_date = due_date if due_date else "no due date"

#     # Only students who haven't submitted
#     c.execute('''
#         SELECT st.regno, st.name, st.phone
#         FROM students st
#         JOIN submissions sub 
#           ON st.regno = sub.regno
#         WHERE sub.assignment_num = %s 
#           AND sub.subject_code = %s 
#           AND (sub.submitted = 0 OR sub.submitted IS NULL)
#     ''', (assignment_num, subject_code))
#     students = c.fetchall()

#     if not students:
#         print("[INFO] No pending students")
#         conn.close()
#         return "No pending students"

#     for regno, name, phone in students:
#         try:
#             message = client.messages.create(
#                 from_='whatsapp:+14155238886',
#                 body=f"{name}, you have not submitted {subject_name} {assignment_name} (A{assignment_num}). Submit soon on {due_date}.",
#                 to=f"whatsapp:+91{phone}"
#             )
#             print(f"[SENT] Reminder to {name} ({phone}) | SID: {message.sid}")
#         except Exception as e:
#             print(f"[ERROR] Failed to send to {name} ({phone}) | {e}")

#     conn.close()
#     return "Reminder process finished"

@app.route('/send_reminder/<subject_code>/<assignment_num>/<department_id>', methods=['POST'])
def send_reminder(subject_code, assignment_num, department_id):
    print("[REMINDER] send_reminder triggered for subject:", subject_code, "assignment:", assignment_num, "department:", department_id)
    
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    c = conn.cursor()

    # Get assignment details
    c.execute("""
        SELECT a.assignment_num, a.assignment_name, s.subject_name, a.due_date
        FROM assignments a
        JOIN subjects s ON a.subject_code = s.subject_code
        WHERE a.assignment_num = %s AND a.subject_code = %s
    """, (assignment_num, subject_code))
    assignment = c.fetchone()

    if not assignment:
        conn.close()
        return "Invalid assignment"

    assignment_num, assignment_name, subject_name, due_date = assignment
    due_date = due_date if due_date else "no due date"

    # Get only students of this department who haven't submitted
    c.execute('''
        SELECT st.regno, st.name, st.phone
        FROM students st
        JOIN submissions sub 
          ON st.regno = sub.regno
        WHERE sub.assignment_num = %s 
          AND sub.subject_code = %s
          AND st.department_id = %s
          AND (sub.submitted = 0 OR sub.submitted IS NULL)
    ''', (assignment_num, subject_code, department_id))
    students = c.fetchall()

    if not students:
        print("[INFO] No pending students in this department")
        conn.close()
        return "No pending students in this department"

    for regno, name, phone in students:
        try:
            message = client.messages.create(
                from_='whatsapp:+14155238886',
                body=f"{name}, you have not submitted {subject_name} {assignment_name} (A{assignment_num}). Submit soon on {due_date}.",
                to=f"whatsapp:+91{phone}"
            )
            print(f"[SENT] Reminder to {name} ({phone}) | SID: {message.sid}")
        except Exception as e:
            print(f"[ERROR] Failed to send to {name} ({phone}) | {e}")

    conn.close()
    return "Reminder process finished for this department!"


def send_all_reminders():
    print("[CRON] send_all_reminders triggered")
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    c = conn.cursor()
    c.execute("SELECT assignment_num, subject_code FROM assignments")
    assignments = c.fetchall()
    conn.close()

    for assignment_num, subject_code in assignments:
        send_reminder(subject_code, assignment_num)

# Scheduler Setup
scheduler = BackgroundScheduler()
scheduler.add_job(send_all_reminders, 'cron', hour=22, minute=36)
scheduler.add_job(send_all_reminders, 'cron', minute=1)
scheduler.start()

# Logout
'''@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))'''
@app.route("/logout")
def logout():
    session.clear()
    session.pop("user", None)  # session la user irundha remove pannum
    return redirect(url_for("home"))

if __name__ == '__main__':
    app.run(debug=True)
