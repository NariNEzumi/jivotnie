import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, session
from functools import wraps
from werkzeug.utils import secure_filename
from datetime import datetime

# Попытка импорта psycopg2 для PostgreSQL (если установлен)
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'shelter-secret-key-2024')
app.config['UPLOAD_FOLDER'] = 'static/uploads/'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Определяем тип базы данных
DATABASE_URL = os.environ.get('DATABASE_URL')
USE_POSTGRES = DATABASE_URL is not None and PSYCOPG2_AVAILABLE

def get_db_connection():
    if USE_POSTGRES:
        # Для PostgreSQL
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    else:
        # Для SQLite (локально)
        conn = sqlite3.connect('shelter.db')
        conn.row_factory = sqlite3.Row
        return conn

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Пожалуйста, авторизуйтесь', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('Доступ запрещён', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    
    if USE_POSTGRES:
        # PostgreSQL
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS animals (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                breed TEXT,
                age TEXT,
                description TEXT,
                photo TEXT,
                status TEXT DEFAULT 'available',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS applications (
                id SERIAL PRIMARY KEY,
                user_id INTEGER,
                animal_id INTEGER,
                user_name TEXT,
                user_phone TEXT,
                user_email TEXT,
                message TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS volunteers (
                id SERIAL PRIMARY KEY,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT NOT NULL,
                experience TEXT,
                motivation TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Создаём админа, если нет
        cur.execute("SELECT * FROM users WHERE username = 'admin'")
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO users (username, email, password, role) VALUES (%s, %s, %s, %s)",
                ('admin', 'admin@shelter.com', 'admin123', 'admin')
            )
    else:
        # SQLite
        cur.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        cur.execute('''CREATE TABLE IF NOT EXISTS animals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            breed TEXT,
            age TEXT,
            description TEXT,
            photo TEXT,
            status TEXT DEFAULT 'available',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        cur.execute('''CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            animal_id INTEGER,
            user_name TEXT,
            user_phone TEXT,
            user_email TEXT,
            message TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        cur.execute('''CREATE TABLE IF NOT EXISTS volunteers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            experience TEXT,
            motivation TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        # Создаём админа, если нет
        cur.execute("SELECT * FROM users WHERE username = 'admin'")
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO users (username, email, password, role) VALUES (?, ?, ?, ?)",
                ('admin', 'admin@shelter.com', 'admin123', 'admin')
            )
    
    conn.commit()
    cur.close()
    conn.close()

# ---------- ОСНОВНЫЕ МАРШРУТЫ (остаются как у вас, но с поддержкой обоих БД) ----------
@app.route('/')
def index():
    conn = get_db_connection()
    cur = conn.cursor()
    if USE_POSTGRES:
        cur.execute("SELECT * FROM animals WHERE status = 'available' LIMIT 6")
    else:
        cur.execute("SELECT * FROM animals WHERE status = 'available' LIMIT 6")
    animals = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('index.html', animals=animals)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contacts')
def contacts():
    return render_template('contacts.html')

@app.route('/catalog')
def catalog():
    animal_type = request.args.get('type', 'all')
    conn = get_db_connection()
    cur = conn.cursor()
    if animal_type == 'all':
        if USE_POSTGRES:
            cur.execute("SELECT * FROM animals WHERE status = 'available'")
        else:
            cur.execute("SELECT * FROM animals WHERE status = 'available'")
    else:
        if USE_POSTGRES:
            cur.execute("SELECT * FROM animals WHERE type = %s AND status = 'available'", (animal_type,))
        else:
            cur.execute("SELECT * FROM animals WHERE type = ? AND status = 'available'", (animal_type,))
    animals = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('catalog.html', animals=animals, selected_type=animal_type)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        cur = conn.cursor()
        if USE_POSTGRES:
            cur.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
        else:
            cur.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        user = cur.fetchone()
        cur.close()
        conn.close()
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            flash(f'Добро пожаловать, {username}!', 'success')
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('index'))
        else:
            flash('Неверное имя пользователя или пароль', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        if password != confirm_password:
            flash('Пароли не совпадают', 'danger')
            return redirect(url_for('register'))
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            if USE_POSTGRES:
                cur.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
                           (username, email, password))
            else:
                cur.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                           (username, email, password))
            conn.commit()
            flash('Регистрация успешна! Теперь войдите в систему', 'success')
            return redirect(url_for('login'))
        except Exception:
            flash('Пользователь с таким именем или email уже существует', 'danger')
        finally:
            cur.close()
            conn.close()
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))

# ---------- АДМИН-ПАНЕЛЬ (добавлены волонтёры) ----------
@app.route('/admin')
@admin_required
def admin_dashboard():
    conn = get_db_connection()
    cur = conn.cursor()
    if USE_POSTGRES:
        cur.execute("SELECT * FROM animals ORDER BY created_at DESC")
        animals = cur.fetchall()
        cur.execute("SELECT * FROM applications ORDER BY created_at DESC")
        applications = cur.fetchall()
        cur.execute("SELECT * FROM volunteers ORDER BY created_at DESC")
        volunteers = cur.fetchall()
    else:
        cur.execute("SELECT * FROM animals ORDER BY created_at DESC")
        animals = cur.fetchall()
        cur.execute("SELECT * FROM applications ORDER BY created_at DESC")
        applications = cur.fetchall()
        cur.execute("SELECT * FROM volunteers ORDER BY created_at DESC")
        volunteers = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('admin_dashboard.html', animals=animals, applications=applications, volunteers=volunteers)

@app.route('/admin/add', methods=['GET', 'POST'])
@admin_required
def add_animal():
    if request.method == 'POST':
        name = request.form['name']
        animal_type = request.form['type']
        breed = request.form['breed']
        age = request.form['age']
        description = request.form['description']
        photo = 'default.jpg'
        if 'photo' in request.files:
            file = request.files['photo']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                photo = f"{datetime.now().timestamp()}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], photo))
        conn = get_db_connection()
        cur = conn.cursor()
        if USE_POSTGRES:
            cur.execute('''INSERT INTO animals (name, type, breed, age, description, photo) 
                         VALUES (%s, %s, %s, %s, %s, %s)''',
                      (name, animal_type, breed, age, description, photo))
        else:
            cur.execute('''INSERT INTO animals (name, type, breed, age, description, photo) 
                         VALUES (?, ?, ?, ?, ?, ?)''',
                      (name, animal_type, breed, age, description, photo))
        conn.commit()
        cur.close()
        conn.close()
        flash('Животное успешно добавлено!', 'success')
        return redirect(url_for('admin_dashboard'))
    return render_template('add_animal.html')

@app.route('/admin/edit/<int:animal_id>', methods=['GET', 'POST'])
@admin_required
def edit_animal(animal_id):
    conn = get_db_connection()
    cur = conn.cursor()
    if request.method == 'POST':
        name = request.form['name']
        animal_type = request.form['type']
        breed = request.form['breed']
        age = request.form['age']
        description = request.form['description']
        status = request.form['status']
        if USE_POSTGRES:
            cur.execute('''UPDATE animals SET name=%s, type=%s, breed=%s, age=%s, description=%s, status=%s
                         WHERE id=%s''',
                      (name, animal_type, breed, age, description, status, animal_id))
        else:
            cur.execute('''UPDATE animals SET name=?, type=?, breed=?, age=?, description=?, status=?
                         WHERE id=?''',
                      (name, animal_type, breed, age, description, status, animal_id))
        if 'photo' in request.files:
            file = request.files['photo']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                photo = f"{datetime.now().timestamp()}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], photo))
                if USE_POSTGRES:
                    cur.execute("UPDATE animals SET photo=%s WHERE id=%s", (photo, animal_id))
                else:
                    cur.execute("UPDATE animals SET photo=? WHERE id=?", (photo, animal_id))
        conn.commit()
        cur.close()
        conn.close()
        flash('Данные животного обновлены!', 'success')
        return redirect(url_for('admin_dashboard'))
    if USE_POSTGRES:
        cur.execute("SELECT * FROM animals WHERE id = %s", (animal_id,))
    else:
        cur.execute("SELECT * FROM animals WHERE id = ?", (animal_id,))
    animal = cur.fetchone()
    cur.close()
    conn.close()
    return render_template('edit_animal.html', animal=animal)

@app.route('/admin/delete/<int:animal_id>')
@admin_required
def delete_animal(animal_id):
    conn = get_db_connection()
    cur = conn.cursor()
    if USE_POSTGRES:
        cur.execute("DELETE FROM animals WHERE id = %s", (animal_id,))
    else:
        cur.execute("DELETE FROM animals WHERE id = ?", (animal_id,))
    conn.commit()
    cur.close()
    conn.close()
    flash('Животное удалено', 'warning')
    return redirect(url_for('admin_dashboard'))

@app.route('/apply/<int:animal_id>', methods=['GET', 'POST'])
@login_required
def apply(animal_id):
    conn = get_db_connection()
    cur = conn.cursor()
    if USE_POSTGRES:
        cur.execute("SELECT * FROM animals WHERE id = %s", (animal_id,))
    else:
        cur.execute("SELECT * FROM animals WHERE id = ?", (animal_id,))
    animal = cur.fetchone()
    if request.method == 'POST':
        user_name = request.form['user_name']
        user_phone = request.form['user_phone']
        user_email = request.form['user_email']
        message = request.form['message']
        if USE_POSTGRES:
            cur.execute('''INSERT INTO applications (user_id, animal_id, user_name, user_phone, user_email, message)
                         VALUES (%s, %s, %s, %s, %s, %s)''',
                      (session['user_id'], animal_id, user_name, user_phone, user_email, message))
        else:
            cur.execute('''INSERT INTO applications (user_id, animal_id, user_name, user_phone, user_email, message)
                         VALUES (?, ?, ?, ?, ?, ?)''',
                      (session['user_id'], animal_id, user_name, user_phone, user_email, message))
        conn.commit()
        cur.close()
        conn.close()
        flash('Заявка успешно отправлена! Мы свяжемся с вами', 'success')
        return redirect(url_for('catalog'))
    cur.close()
    conn.close()
    return render_template('apply.html', animal=animal)

@app.route('/admin/application/<int:app_id>/<action>')
@admin_required
def handle_application(app_id, action):
    conn = get_db_connection()
    cur = conn.cursor()
    if action == 'approve':
        if USE_POSTGRES:
            cur.execute("UPDATE applications SET status = 'approved' WHERE id = %s", (app_id,))
        else:
            cur.execute("UPDATE applications SET status = 'approved' WHERE id = ?", (app_id,))
        flash('Заявка одобрена', 'success')
    elif action == 'reject':
        if USE_POSTGRES:
            cur.execute("UPDATE applications SET status = 'rejected' WHERE id = %s", (app_id,))
        else:
            cur.execute("UPDATE applications SET status = 'rejected' WHERE id = ?", (app_id,))
        flash('Заявка отклонена', 'danger')
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('admin_dashboard'))

# ---------- НОВЫЙ РАЗДЕЛ: СТАТЬ ВОЛОНТЁРОМ ----------
@app.route('/volunteer', methods=['GET', 'POST'])
def volunteer():
    if request.method == 'POST':
        full_name = request.form['full_name']
        email = request.form['email']
        phone = request.form['phone']
        experience = request.form.get('experience', '')
        motivation = request.form.get('motivation', '')
        
        if not full_name or not email or not phone:
            flash('Пожалуйста, заполните все обязательные поля', 'danger')
            return redirect(url_for('volunteer'))
        
        conn = get_db_connection()
        cur = conn.cursor()
        if USE_POSTGRES:
            cur.execute('''INSERT INTO volunteers (full_name, email, phone, experience, motivation)
                         VALUES (%s, %s, %s, %s, %s)''',
                       (full_name, email, phone, experience, motivation))
        else:
            cur.execute('''INSERT INTO volunteers (full_name, email, phone, experience, motivation)
                         VALUES (?, ?, ?, ?, ?)''',
                       (full_name, email, phone, experience, motivation))
        conn.commit()
        cur.close()
        conn.close()
        flash('Спасибо! Ваша заявка на волонтёрство принята. Мы свяжемся с вами в ближайшее время.', 'success')
        return redirect(url_for('index'))
    return render_template('volunteer.html')

@app.route('/admin/volunteer/<int:vol_id>/<action>')
@admin_required
def handle_volunteer(vol_id, action):
    conn = get_db_connection()
    cur = conn.cursor()
    if action == 'approve':
        if USE_POSTGRES:
            cur.execute("UPDATE volunteers SET status = 'approved' WHERE id = %s", (vol_id,))
        else:
            cur.execute("UPDATE volunteers SET status = 'approved' WHERE id = ?", (vol_id,))
        flash('Заявка волонтёра одобрена', 'success')
    elif action == 'reject':
        if USE_POSTGRES:
            cur.execute("UPDATE volunteers SET status = 'rejected' WHERE id = %s", (vol_id,))
        else:
            cur.execute("UPDATE volunteers SET status = 'rejected' WHERE id = ?", (vol_id,))
        flash('Заявка волонтёра отклонена', 'danger')
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('DEBUG', 'False') == 'True')