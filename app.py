from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import mysql.connector
from mysql.connector import Error
import bcrypt
import os
import random
import re
from functools import wraps
from urllib.parse import urlparse
from datetime import datetime

app = Flask(__name__)

# Security: Use environment variables
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))

# Database configuration from environment variables
mysql_url = os.environ.get('MYSQL_URL')
url_parts = urlparse(mysql_url)
db_config = {
    'host': url_parts.hostname,
    'user': url_parts.username,
    'password': url_parts.password,
    'database': url_parts.path[1:],
    'port': url_parts.port or 3306
}

def get_db_connection():
    try:
        connection = mysql.connector.connect(**db_config)
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

def check_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def validate_phone_number(phone):
    """Validate phone number format"""
    pattern = r'^\+?1?\d{9,15}$'
    return re.match(pattern, phone) is not None

def get_majors_by_faculty(faculty):
    """Get majors based on selected faculty"""
    faculty_majors = {
        'FCIT': ['Computer Science', 'Information Technology', 'Software Engineering', 
                'Cybersecurity', 'Data Science', 'Artificial Intelligence', 
                'Computer Engineering', 'Network Engineering'],
        'FBBA': ['Business Administration', 'Accounting', 'Finance', 'Marketing', 
                'Human Resources', 'International Business', 'Management', 'Entrepreneurship'],
        'FENG': ['Electrical Engineering', 'Mechanical Engineering', 'Civil Engineering', 
                'Chemical Engineering', 'Industrial Engineering', 'Biomedical Engineering'],
        'FMED': ['Medicine', 'Nursing', 'Pharmacy', 'Dentistry', 'Public Health'],
        'FSCI': ['Biology', 'Chemistry', 'Physics', 'Mathematics', 
                'Environmental Science', 'Biotechnology'],
        'FART': ['Psychology', 'Sociology', 'English Literature', 'History', 
                'Political Science', 'International Relations'],
        'FLAW': ['Law', 'Criminal Justice'],
        'FEDU': ['Education', 'Early Childhood Education']
    }
    return faculty_majors.get(faculty, [])

def assign_sample_grades(student_id):
    """Assign random sample grades to a new student"""
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor()
            
            # Get some random courses to assign grades for
            cursor.execute("SELECT id FROM courses ORDER BY RAND() LIMIT 6")
            courses = cursor.fetchall()
            
            # Grade distribution with probabilities
            grade_distribution = [
                ('A', 0.2),   # 20% chance
                ('A-', 0.15), # 15% chance  
                ('B+', 0.15), # 15% chance
                ('B', 0.15),  # 15% chance
                ('B-', 0.1),  # 10% chance
                ('C+', 0.1),  # 10% chance
                ('C', 0.08),  # 8% chance
                ('C-', 0.05), # 5% chance
                ('D', 0.02)   # 2% chance
            ]
            
            semesters = ['Fall', 'Spring']
            years = ['2023', '2024']
            
            for course in courses:
                course_id = course[0]
                
                # Random grade based on distribution
                rand_val = random.random()
                cumulative_prob = 0
                assigned_grade = 'B'  # default
                
                for grade, prob in grade_distribution:
                    cumulative_prob += prob
                    if rand_val <= cumulative_prob:
                        assigned_grade = grade
                        break
                
                # Random semester and year
                semester = random.choice(semesters)
                year = random.choice(years)
                
                # Insert the grade
                cursor.execute(
                    "INSERT INTO grades (student_id, course_id, grade, semester, academic_year) VALUES (%s, %s, %s, %s, %s)",
                    (student_id, course_id, assigned_grade, semester, year)
                )
            
            connection.commit()
            print(f"Assigned sample grades for student {student_id}")
            
        except Error as e:
            print(f"Error assigning grades: {e}")
        finally:
            connection.close()

def assign_program_courses(student_id, major):
    """Automatically assign required courses based on student's major"""
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor()
            
            # Get required courses for the student's major
            cursor.execute("SELECT id FROM courses WHERE program = %s", (major,))
            required_courses = cursor.fetchall()
            
            # Register student for required courses
            for course in required_courses:
                course_id = course[0]
                
                # Check if already registered
                cursor.execute(
                    "SELECT * FROM registrations WHERE student_id = %s AND course_id = %s",
                    (student_id, course_id)
                )
                if not cursor.fetchone():
                    # Register for course
                    cursor.execute(
                        "INSERT INTO registrations (student_id, course_id, semester) VALUES (%s, %s, %s)",
                        (student_id, course_id, 'Fall 2024')
                    )
                    
                    # Update course enrollment
                    cursor.execute(
                        "UPDATE courses SET current_enrollment = current_enrollment + 1 WHERE id = %s",
                        (course_id,)
                    )
            
            connection.commit()
            print(f"Automatically assigned program courses for student {student_id} in major {major}")
            
        except Error as e:
            print(f"Error assigning program courses: {e}")
        finally:
            connection.close()

# Routes
@app.route('/')
def home():
    if 'student_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Get form data
        university_id = request.form['university_id'].strip().upper()
        faculty = request.form['faculty']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        phone_number = request.form['phone_number']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        major = request.form['major']
        enrollment_year = request.form['enrollment_year']
        
        # Enhanced validation
        if password != confirm_password:
            flash('Passwords do not match!', 'error')
            return render_template('register.html')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters long!', 'error')
            return render_template('register.html')
        
        if not validate_phone_number(phone_number):
            flash('Please enter a valid phone number!', 'error')
            return render_template('register.html')
        
        if not enrollment_year or not enrollment_year.isdigit():
            flash('Please enter a valid enrollment year!', 'error')
            return render_template('register.html')
        
        # Hash password
        hashed_password = hash_password(password)
        
        # Save to database
        connection = get_db_connection()
        if connection:
            try:
                cursor = connection.cursor()
                
                # Check if university ID already exists
                cursor.execute("SELECT id FROM students WHERE university_id = %s", (university_id,))
                if cursor.fetchone():
                    flash('This University ID is already registered!', 'error')
                    return render_template('register.html')
                
                # Check if email already exists
                cursor.execute("SELECT id FROM students WHERE email = %s", (email,))
                if cursor.fetchone():
                    flash('This email address is already registered!', 'error')
                    return render_template('register.html')
                
                # Insert new student with university ID
                cursor.execute(
                    "INSERT INTO students (university_id, faculty, first_name, last_name, email, phone_number, password, major, enrollment_year) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (university_id, faculty, first_name, last_name, email, phone_number, hashed_password, major, enrollment_year)
                )
                connection.commit()
                
                # Get the database ID of the new student
                cursor.execute("SELECT id FROM students WHERE university_id = %s", (university_id,))
                result = cursor.fetchone()
                student_db_id = result[0]
                
                # Assign sample grades automatically
                assign_sample_grades(student_db_id)
                
                # Automatically assign program courses
                assign_program_courses(student_db_id, major)
                
                flash(f'Registration successful! You can now login with your University ID: <strong>{university_id}</strong>', 'success')
                return redirect(url_for('login'))
                
            except Error as e:
                error_message = str(e).lower()
                if "duplicate" in error_message and "email" in error_message:
                    flash('Error: This email address is already registered!', 'error')
                elif "duplicate" in error_message and "university_id" in error_message:
                    flash('Error: This University ID is already registered!', 'error')
                else:
                    flash(f'Registration error: {e}', 'error')
                    print(f"Database error: {e}")
            finally:
                connection.close()
        else:
            flash('Database connection error!', 'error')
    
    return render_template('register.html')

@app.route('/get_majors/<faculty>')
def get_majors(faculty):
    """API endpoint to get majors for selected faculty"""
    majors = get_majors_by_faculty(faculty)
    return jsonify(majors)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        university_id = request.form['university_id'].strip().upper()
        password = request.form['password']
        
        connection = get_db_connection()
        if connection:
            try:
                cursor = connection.cursor(dictionary=True)
                cursor.execute(
                    "SELECT * FROM students WHERE university_id = %s", 
                    (university_id,)
                )
                student = cursor.fetchone()
                
                if student and check_password(password, student['password']):
                    session['student_id'] = student['id']
                    session['student_name'] = f"{student['first_name']} {student['last_name']}"
                    session['student_university_id'] = student['university_id']
                    flash(f'Welcome back, {student["first_name"]}!', 'success')
                    return redirect(url_for('dashboard'))
                else:
                    flash('Invalid University ID or password!', 'error')
            except Error as e:
                flash('Login error!', 'error')
            finally:
                connection.close()
        else:
            flash('Database connection error!', 'error')
    
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'student_id' not in session:
        return redirect(url_for('login'))
    
    # Get recent announcements and timetable data for dashboard
    connection = get_db_connection()
    announcements = []
    timetable_data = []
    
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            
            # Get recent announcements
            cursor.execute("SELECT * FROM announcements ORDER BY created_at DESC LIMIT 3")
            announcements = cursor.fetchall()
            
            # Get timetable data for today's classes
            cursor.execute("""
                SELECT 
                    t.day_of_week,
                    TIME_FORMAT(t.start_time, '%H:%i:%s') as start_time_str,
                    TIME_FORMAT(t.end_time, '%H:%i:%s') as end_time_str,
                    TIME_FORMAT(t.start_time, '%h:%i %p') as start_time_display,
                    TIME_FORMAT(t.end_time, '%h:%i %p') as end_time_display,
                    t.room_number,
                    c.course_code,
                    c.course_name,
                    c.instructor
                FROM timetable t
                JOIN courses c ON t.course_id = c.id
                WHERE t.student_id = %s
            """, (session['student_id'],))
            timetable_data = cursor.fetchall()
            
            print(f"DEBUG: Loaded {len(timetable_data)} timetable entries for dashboard")
            
        except Error as e:
            print(f"Error loading dashboard data: {e}")
        finally:
            connection.close()
    
    # Get current day for today's classes
    from datetime import datetime
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    today_name = days[datetime.now().weekday()]
    
    return render_template('dashboard.html', 
                         student_name=session['student_name'],
                         announcements=announcements,
                         timetable_data=timetable_data,
                         today_name=today_name)

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('home'))

@app.route('/profile')
def profile():
    if 'student_id' not in session:
        return redirect(url_for('login'))
    
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM students WHERE id = %s", (session['student_id'],))
            student = cursor.fetchone()
            return render_template('profile.html', student=student)
        except Error as e:
            flash('Error loading profile!', 'error')
        finally:
            connection.close()
    
    return redirect(url_for('dashboard'))



@app.route('/courses')
def courses():
    if 'student_id' not in session:
        return redirect(url_for('login'))
    
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            
            # Get all available courses
            cursor.execute("SELECT * FROM courses")
            all_courses = cursor.fetchall()
            
            # Get student's registered courses
            cursor.execute("""
                SELECT c.* FROM courses c 
                JOIN registrations r ON c.id = r.course_id 
                WHERE r.student_id = %s
            """, (session['student_id'],))
            my_courses = cursor.fetchall()
            
            return render_template('courses.html', 
                                 all_courses=all_courses, 
                                 my_courses=my_courses)
        except Error as e:
            flash('Error loading courses!', 'error')
        finally:
            connection.close()
    
    return redirect(url_for('dashboard'))

@app.route('/register_course/<int:course_id>')
def register_course(course_id):
    if 'student_id' not in session:
        return redirect(url_for('login'))
    
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor()
            
            # Check if already registered
            cursor.execute(
                "SELECT * FROM registrations WHERE student_id = %s AND course_id = %s",
                (session['student_id'], course_id)
            )
            if cursor.fetchone():
                flash('You are already registered for this course!', 'error')
                return redirect(url_for('courses'))
            
            # Register for course
            cursor.execute(
                "INSERT INTO registrations (student_id, course_id, semester) VALUES (%s, %s, %s)",
                (session['student_id'], course_id, 'Fall 2024')
            )
            
            # Update course enrollment
            cursor.execute(
                "UPDATE courses SET current_enrollment = current_enrollment + 1 WHERE id = %s",
                (course_id,)
            )
            
            connection.commit()
            flash('Course registration successful!', 'success')
            
        except Error as e:
            flash('Registration failed! Course might be full.', 'error')
        finally:
            connection.close()
    
    return redirect(url_for('courses'))

@app.route('/drop_course/<int:course_id>')
def drop_course(course_id):
    if 'student_id' not in session:
        return redirect(url_for('login'))
    
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor()
            
            # Drop course
            cursor.execute(
                "DELETE FROM registrations WHERE student_id = %s AND course_id = %s",
                (session['student_id'], course_id)
            )
            
            # Update course enrollment
            cursor.execute(
                "UPDATE courses SET current_enrollment = current_enrollment - 1 WHERE id = %s",
                (course_id,)
            )
            
            connection.commit()
            flash('Course dropped successfully!', 'success')
            
        except Error as e:
            flash('Error dropping course!', 'error')
        finally:
            connection.close()
    
    return redirect(url_for('courses'))

@app.route('/grades')
def grades():
    if 'student_id' not in session:
        return redirect(url_for('login'))
    
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            
            # Get student's grades
            cursor.execute("""
                SELECT c.course_code, c.course_name, c.credits, g.grade, g.semester, g.academic_year
                FROM grades g 
                JOIN courses c ON g.course_id = c.id 
                WHERE g.student_id = %s
                ORDER BY g.academic_year DESC, g.semester DESC
            """, (session['student_id'],))
            grades = cursor.fetchall()
            
            return render_template('grades.html', grades=grades)
        except Error as e:
            flash('Error loading grades!', 'error')
        finally:
            connection.close()
    
    return redirect(url_for('dashboard'))

@app.route('/announcements')
def announcements():
    if 'student_id' not in session:
        return redirect(url_for('login'))
    
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM announcements ORDER BY created_at DESC")
            announcements = cursor.fetchall()
            return render_template('announcements.html', announcements=announcements)
        except Error as e:
            flash('Error loading announcements!', 'error')
        finally:
            connection.close()
    
    return redirect(url_for('dashboard'))

# Admin Authentication Decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            flash('Admin access required!', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# Admin Routes
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # SIMPLE HARDCODED CREDENTIALS - JUST WORKS!
        if username == 'admin' and password == 'admin123':
            session['admin_id'] = 1
            session['admin_name'] = 'University Administrator'
            session['admin_role'] = 'super_admin'
            flash('Welcome to Admin Panel!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid credentials! Use: admin / admin123', 'error')
    
    return render_template('admin/login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_id', None)
    session.pop('admin_name', None)
    session.pop('admin_role', None)
    flash('Admin logged out successfully.', 'info')
    return redirect(url_for('admin_login'))

# Admin Dashboard
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    connection = get_db_connection()
    stats = {}
    
    if connection:
        try:
            cursor = connection.cursor()
            
            # Get statistics
            cursor.execute("SELECT COUNT(*) FROM students")
            stats['total_students'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM courses")
            stats['total_courses'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM announcements")
            stats['total_announcements'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM registrations")
            stats['total_registrations'] = cursor.fetchone()[0]
            
        except Error as e:
            flash('Error loading dashboard data!', 'error')
        finally:
            connection.close()
    
    return render_template('admin/dashboard.html', stats=stats)

# Admin Student Management
@app.route('/admin/students')
@admin_required
def admin_students():
    connection = get_db_connection()
    students = []
    
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("""
                SELECT s.*, COUNT(r.id) as registered_courses
                FROM students s 
                LEFT JOIN registrations r ON s.id = r.student_id
                GROUP BY s.id
                ORDER BY s.created_at DESC
            """)
            students = cursor.fetchall()
        except Error as e:
            flash('Error loading students!', 'error')
        finally:
            connection.close()
    
    return render_template('admin/students.html', students=students)

# Delete Student
@app.route('/admin/students/delete/<int:student_id>')
@admin_required
def delete_student(student_id):
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor()
            
            # First delete related records to maintain referential integrity
            cursor.execute("DELETE FROM registrations WHERE student_id = %s", (student_id,))
            cursor.execute("DELETE FROM grades WHERE student_id = %s", (student_id,))
            
            # Then delete the student
            cursor.execute("DELETE FROM students WHERE id = %s", (student_id,))
            connection.commit()
            
            flash('Student deleted successfully!', 'success')
        except Error as e:
            flash(f'Error deleting student: {e}', 'error')
        finally:
            connection.close()
    
    return redirect(url_for('admin_students'))

# Admin Course Management
@app.route('/admin/courses')
@admin_required
def admin_courses():
    connection = get_db_connection()
    courses = []
    
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM courses ORDER BY course_code")
            courses = cursor.fetchall()
        except Error as e:
            flash('Error loading courses!', 'error')
        finally:
            connection.close()
    
    return render_template('admin/courses.html', courses=courses)

# Delete Course
@app.route('/admin/courses/delete/<int:course_id>')
@admin_required
def delete_course(course_id):
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor()
            
            # First delete related records
            cursor.execute("DELETE FROM registrations WHERE course_id = %s", (course_id,))
            cursor.execute("DELETE FROM grades WHERE course_id = %s", (course_id,))
            
            # Then delete the course
            cursor.execute("DELETE FROM courses WHERE id = %s", (course_id,))
            connection.commit()
            
            flash('Course deleted successfully!', 'success')
        except Error as e:
            flash(f'Error deleting course: {e}', 'error')
        finally:
            connection.close()
    
    return redirect(url_for('admin_courses'))

# Admin Announcement Management
@app.route('/admin/announcements')
@admin_required
def admin_announcements():
    connection = get_db_connection()
    announcements = []
    
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM announcements ORDER BY created_at DESC")
            announcements = cursor.fetchall()
        except Error as e:
            flash('Error loading announcements!', 'error')
        finally:
            connection.close()
    
    return render_template('admin/announcements.html', announcements=announcements)

@app.route('/admin/announcements/create', methods=['GET', 'POST'])
@admin_required
def create_announcement():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        author = request.form['author']
        is_important = 'is_important' in request.form
        
        connection = get_db_connection()
        if connection:
            try:
                cursor = connection.cursor()
                cursor.execute(
                    "INSERT INTO announcements (title, content, author, is_important) VALUES (%s, %s, %s, %s)",
                    (title, content, author, is_important)
                )
                connection.commit()
                flash('Announcement created successfully!', 'success')
                return redirect(url_for('admin_announcements'))
            except Error as e:
                flash('Error creating announcement!', 'error')
            finally:
                connection.close()
    
    return render_template('admin/create_announcement.html')

# Delete Announcement
@app.route('/admin/announcements/delete/<int:announcement_id>')
@admin_required
def delete_announcement(announcement_id):
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor()
            cursor.execute("DELETE FROM announcements WHERE id = %s", (announcement_id,))
            connection.commit()
            flash('Announcement deleted successfully!', 'success')
        except Error as e:
            flash(f'Error deleting announcement: {e}', 'error')
        finally:
            connection.close()
    
    return redirect(url_for('admin_announcements'))

# Admin Grade Management
@app.route('/admin/grades')
@admin_required
def admin_grades():
    connection = get_db_connection()
    grades = []
    
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("""
                SELECT g.*, s.university_id, s.first_name, s.last_name, c.course_code, c.course_name
                FROM grades g
                JOIN students s ON g.student_id = s.id
                JOIN courses c ON g.course_id = c.id
                ORDER BY g.academic_year DESC, g.semester DESC
            """)
            grades = cursor.fetchall()
        except Error as e:
            flash('Error loading grades!', 'error')
        finally:
            connection.close()
    
    return render_template('admin/grades.html', grades=grades)

# Delete Grade
@app.route('/admin/grades/delete/<int:grade_id>')
@admin_required
def delete_grade(grade_id):
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor()
            cursor.execute("DELETE FROM grades WHERE id = %s", (grade_id,))
            connection.commit()
            flash('Grade deleted successfully!', 'success')
        except Error as e:
            flash(f'Error deleting grade: {e}', 'error')
        finally:
            connection.close()
    
    return redirect(url_for('admin_grades'))

# NEW: Assign Grade Route
@app.route('/admin/grades/assign', methods=['GET', 'POST'])
@admin_required
def assign_grade():
    if request.method == 'POST':
        student_id = request.form['student_id']
        course_id = request.form['course_id']
        grade = request.form['grade']
        semester = request.form['semester']
        academic_year = request.form['academic_year']
        
        connection = get_db_connection()
        if connection:
            try:
                cursor = connection.cursor()
                
                # Check if grade already exists
                cursor.execute(
                    "SELECT * FROM grades WHERE student_id = %s AND course_id = %s AND semester = %s AND academic_year = %s",
                    (student_id, course_id, semester, academic_year)
                )
                existing_grade = cursor.fetchone()
                
                if existing_grade:
                    # Update existing grade
                    cursor.execute(
                        "UPDATE grades SET grade = %s WHERE student_id = %s AND course_id = %s AND semester = %s AND academic_year = %s",
                        (grade, student_id, course_id, semester, academic_year)
                    )
                    flash('Grade updated successfully!', 'success')
                else:
                    # Insert new grade
                    cursor.execute(
                        "INSERT INTO grades (student_id, course_id, grade, semester, academic_year) VALUES (%s, %s, %s, %s, %s)",
                        (student_id, course_id, grade, semester, academic_year)
                    )
                    flash('Grade assigned successfully!', 'success')
                
                connection.commit()
                return redirect(url_for('admin_grades'))
                
            except Error as e:
                flash(f'Error assigning grade: {e}', 'error')
            finally:
                connection.close()
    
    # Get students and courses for dropdowns
    connection = get_db_connection()
    students = []
    courses = []
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT id, university_id, first_name, last_name FROM students ORDER BY first_name")
            students = cursor.fetchall()
            
            cursor.execute("SELECT id, course_code, course_name FROM courses ORDER BY course_code")
            courses = cursor.fetchall()
        except Error as e:
            flash('Error loading data!', 'error')
        finally:
            connection.close()
    
    return render_template('admin/assign_grade.html', students=students, courses=courses)

# Help Desk Chatbot
@app.route('/help')
def help_desk():
    if 'student_id' not in session:
        return redirect(url_for('login'))
    return render_template('help.html')

@app.route('/chatbot_response', methods=['POST'])
def chatbot_response():
    if 'student_id' not in session:
        return redirect(url_for('login'))
    
    user_message = request.json.get('message', '').lower()
    
    # Simple chatbot responses
    responses = {
        'hello': "Hello! How can I help you with the student portal today?",
        'hi': "Hi there! What can I assist you with?",
        'grades': "You can view your grades in the 'Grades' section. If you have issues, contact the administration office.",
        'courses': "You can register for courses in the 'Course Registration' section. Required courses for your program are automatically assigned.",
        'registration': "Course registration is available in the 'Course Registration' section. You can also drop courses from there.",
        'profile': "Update your personal information in the 'My Profile' section.",
        'announcements': "Check the 'Announcements' section for latest university updates.",
        'password': "If you forgot your password, please contact the IT help desk for password reset.",
        'login': "Make sure you're using your University ID to login.",
        'contact': "For urgent matters, contact:\n- IT Help Desk: it-support@university.edu\n- Administration: admin@university.edu\n- Phone: +1 (555) 123-4567",
        'hours': "University office hours:\nMonday-Friday: 8:00 AM - 6:00 PM\nSaturday: 9:00 AM - 1:00 PM",
        'deadline': "Important deadlines:\n- Course registration: End of first week\n- Grade appeals: Within 7 days of posting\n- Fee payment: 15th of each month",
        'help': "I can help with:\n- Grades and courses\n- Registration issues\n- Profile updates\n- University contacts\n- Office hours and deadlines",
    }
    
    # Find the best matching response
    response = "I'm not sure I understand. Try asking about:\n- Grades\n- Course registration\n- Profile updates\n- Contact information\n- Office hours\nOr type 'help' for more options."
    
    for keyword, bot_response in responses.items():
        if keyword in user_message:
            response = bot_response
            break
    
    return {'response': response}

@app.route('/timetable')
def timetable():
    if 'student_id' not in session:
        return redirect(url_for('login'))
    
    # Static timetable data - always visible for prototype
    static_timetable = [
        {'day': 'Monday', 'time': '8:00 AM - 9:30 AM', 'course_code': 'CS101', 'course_name': 'Introduction to Programming', 'instructor': 'Dr. Smith', 'room': 'Room 101'},
        {'day': 'Monday', 'time': '11:30 AM - 1:00 PM', 'course_code': 'MATH201', 'course_name': 'Calculus I', 'instructor': 'Dr. Johnson', 'room': 'Room 202'},
        {'day': 'Tuesday', 'time': '9:45 AM - 11:15 AM', 'course_code': 'PHY101', 'course_name': 'Physics I', 'instructor': 'Dr. Wilson', 'room': 'Room 305'},
        {'day': 'Tuesday', 'time': '1:30 PM - 3:00 PM', 'course_code': 'ENG101', 'course_name': 'English Composition', 'instructor': 'Prof. Davis', 'room': 'Room 410'},
        {'day': 'Wednesday', 'time': '8:00 AM - 9:30 AM', 'course_code': 'CS101', 'course_name': 'Introduction to Programming', 'instructor': 'Dr. Smith', 'room': 'Room 101'},
        {'day': 'Wednesday', 'time': '11:30 AM - 1:00 PM', 'course_code': 'MATH201', 'course_name': 'Calculus I', 'instructor': 'Dr. Johnson', 'room': 'Room 202'},
        {'day': 'Thursday', 'time': '9:45 AM - 11:15 AM', 'course_code': 'PHY101', 'course_name': 'Physics I', 'instructor': 'Dr. Wilson', 'room': 'Room 305'},
        {'day': 'Friday', 'time': '1:30 PM - 3:00 PM', 'course_code': 'ENG101', 'course_name': 'English Composition', 'instructor': 'Prof. Davis', 'room': 'Room 410'}
    ]
    
    return render_template('timetable.html', timetable_data=static_timetable)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)






