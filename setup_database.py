import mysql.connector
from mysql.connector import Error
import os

def setup_database():
    db_config = {
        'host': os.environ.get('DB_HOST', 'localhost'),
        'user': os.environ.get('DB_USER', 'root'),
        'password': os.environ.get('DB_PASSWORD', '1234567890'),
        'database': os.environ.get('DB_NAME', 'student_portal_db')
    }
    
    try:
        # Connect to MySQL
        connection = mysql.connector.connect(
            host=db_config['host'],
            user=db_config['user'],
            password=db_config['password']
        )
        
        if connection.is_connected():
            cursor = connection.cursor()
            
            # Create database if not exists
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_config['database']}")
            print(f"Database '{db_config['database']}' created or already exists")
            
            # Use the database
            cursor.execute(f"USE {db_config['database']}")
            
            # Create tables
            tables = [
                """
                CREATE TABLE IF NOT EXISTS students (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    faculty_code VARCHAR(10) NOT NULL,
                    session_type VARCHAR(1) NOT NULL,
                    numeric_id INT NOT NULL,
                    student_id VARCHAR(20) GENERATED ALWAYS AS (CONCAT(faculty_code, '/', session_type, '/', LPAD(numeric_id, 3, '0'))) STORED UNIQUE,
                    first_name VARCHAR(100) NOT NULL,
                    last_name VARCHAR(100) NOT NULL,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    major VARCHAR(100),
                    enrollment_year INT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS courses (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    course_code VARCHAR(20) UNIQUE NOT NULL,
                    course_name VARCHAR(255) NOT NULL,
                    instructor VARCHAR(100) NOT NULL,
                    schedule_days VARCHAR(50) NOT NULL,
                    schedule_time VARCHAR(50) NOT NULL,
                    credits INT NOT NULL,
                    max_capacity INT NOT NULL,
                    current_enrollment INT DEFAULT 0,
                    program VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS registrations (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    student_id INT NOT NULL,
                    course_id INT NOT NULL,
                    semester VARCHAR(50) NOT NULL,
                    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
                    UNIQUE KEY unique_registration (student_id, course_id, semester)
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS grades (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    student_id INT NOT NULL,
                    course_id INT NOT NULL,
                    grade VARCHAR(5) NOT NULL,
                    semester VARCHAR(50) NOT NULL,
                    academic_year VARCHAR(20) NOT NULL,
                    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS announcements (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    content TEXT NOT NULL,
                    author VARCHAR(100) NOT NULL,
                    is_important BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            ]
            
            for table in tables:
                cursor.execute(table)
            
            # Insert sample courses
            sample_courses = [
                ('CS101', 'Introduction to Programming', 'Dr. Smith', 'Mon, Wed', '10:00-11:30', 3, 50, 0, 'Computer Science'),
                ('CS102', 'Data Structures', 'Dr. Johnson', 'Tue, Thu', '14:00-15:30', 3, 40, 0, 'Computer Science'),
                ('BUS101', 'Business Fundamentals', 'Prof. Davis', 'Mon, Wed', '09:00-10:30', 3, 60, 0, 'Business Administration'),
                ('BUS201', 'Marketing Principles', 'Prof. Wilson', 'Tue, Thu', '11:00-12:30', 3, 45, 0, 'Business Administration'),
                ('EE101', 'Circuit Analysis', 'Dr. Brown', 'Mon, Wed, Fri', '13:00-14:00', 4, 35, 0, 'Electrical Engineering')
            ]
            
            for course in sample_courses:
                cursor.execute(
                    "INSERT IGNORE INTO courses (course_code, course_name, instructor, schedule_days, schedule_time, credits, max_capacity, current_enrollment, program) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    course
                )
            
            connection.commit()
            print("Database setup completed successfully!")
            
    except Error as e:
        print(f"Error: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

if _name_ == "_main_":
    setup_database()
