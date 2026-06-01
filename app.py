from flask import Flask, render_template, request, redirect, url_for, flash, session
from functools import wraps
import sqlite3
import os
from werkzeug.utils import secure_filename
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'shelter-secret-key-2024'
app.config['UPLOAD_FOLDER'] = 'static/uploads/'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

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
    conn = sqlite3.connect('shelter.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT DEFAULT 'user',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS animals (
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
    
    c.execute('''CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        animal_id INTEGER,
        user_name TEXT,
        user_phone TEXT,
        user_email TEXT,
        message TEXT,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (animal_id) REFERENCES animals (id)
    )''')
    
    c.execute("SELECT * FROM users WHERE username = 'admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username, email, password, role) VALUES (?, ?, ?, ?)",
                  ('admin', 'admin@shelter.com', 'admin123', 'admin'))
    
    conn.commit()
    conn.close()

@app.route('/')
def index():
    conn = sqlite3.connect('shelter.db')
    c = conn.cursor()
    c.execute("SELECT * FROM animals WHERE status = 'available' LIMIT 6")
    animals = c.fetchall()
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
    conn = sqlite3.connect('shelter.db')
    c = conn.cursor()
    
    if animal_type == 'all':
        c.execute("SELECT * FROM animals WHERE status = 'available'")
    else:
        c.execute("SELECT * FROM animals WHERE type = ? AND status = 'available'", (animal_type,))
    
    animals = c.fetchall()
    conn.close()
    return render_template('catalog.html', animals=animals, selected_type=animal_type)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect('shelter.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        user = c.fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['role'] = user[4]
            flash(f'Добро пожаловать, {username}!', 'success')
            if user[4] == 'admin':
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
        
        conn = sqlite3.connect('shelter.db')
        c = conn.cursor()
        
        try:
            c.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                      (username, email, password))
            conn.commit()
            flash('Регистрация успешна! Теперь войдите в систему', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Пользователь с таким именем или email уже существует', 'danger')
        finally:
            conn.close()
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))

@app.route('/admin')
@admin_required
def admin_dashboard():
    conn = sqlite3.connect('shelter.db')
    c = conn.cursor()
    c.execute("SELECT * FROM animals ORDER BY created_at DESC")
    animals = c.fetchall()
    c.execute("SELECT * FROM applications ORDER BY created_at DESC")
    applications = c.fetchall()
    conn.close()
    return render_template('admin_dashboard.html', animals=animals, applications=applications)

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
        
        conn = sqlite3.connect('shelter.db')
        c = conn.cursor()
        c.execute('''INSERT INTO animals (name, type, breed, age, description, photo) 
                     VALUES (?, ?, ?, ?, ?, ?)''',
                  (name, animal_type, breed, age, description, photo))
        conn.commit()
        conn.close()
        
        flash('Животное успешно добавлено!', 'success')
        return redirect(url_for('admin_dashboard'))
    
    return render_template('add_animal.html')

@app.route('/admin/edit/<int:animal_id>', methods=['GET', 'POST'])
@admin_required
def edit_animal(animal_id):
    conn = sqlite3.connect('shelter.db')
    c = conn.cursor()
    
    if request.method == 'POST':
        name = request.form['name']
        animal_type = request.form['type']
        breed = request.form['breed']
        age = request.form['age']
        description = request.form['description']
        status = request.form['status']
        
        c.execute('''UPDATE animals SET name=?, type=?, breed=?, age=?, description=?, status=?
                     WHERE id=?''',
                  (name, animal_type, breed, age, description, status, animal_id))
        
        if 'photo' in request.files:
            file = request.files['photo']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                photo = f"{datetime.now().timestamp()}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], photo))
                c.execute("UPDATE animals SET photo=? WHERE id=?", (photo, animal_id))
        
        conn.commit()
        conn.close()
        flash('Данные животного обновлены!', 'success')
        return redirect(url_for('admin_dashboard'))
    
    c.execute("SELECT * FROM animals WHERE id = ?", (animal_id,))
    animal = c.fetchone()
    conn.close()
    return render_template('edit_animal.html', animal=animal)

@app.route('/admin/delete/<int:animal_id>')
@admin_required
def delete_animal(animal_id):
    conn = sqlite3.connect('shelter.db')
    c = conn.cursor()
    c.execute("DELETE FROM animals WHERE id = ?", (animal_id,))
    conn.commit()
    conn.close()
    flash('Животное удалено', 'warning')
    return redirect(url_for('admin_dashboard'))

@app.route('/apply/<int:animal_id>', methods=['GET', 'POST'])
@login_required
def apply(animal_id):
    conn = sqlite3.connect('shelter.db')
    c = conn.cursor()
    c.execute("SELECT * FROM animals WHERE id = ?", (animal_id,))
    animal = c.fetchone()
    
    if request.method == 'POST':
        user_name = request.form['user_name']
        user_phone = request.form['user_phone']
        user_email = request.form['user_email']
        message = request.form['message']
        
        c.execute('''INSERT INTO applications (user_id, animal_id, user_name, user_phone, user_email, message)
                     VALUES (?, ?, ?, ?, ?, ?)''',
                  (session['user_id'], animal_id, user_name, user_phone, user_email, message))
        conn.commit()
        conn.close()
        
        flash('Заявка успешно отправлена! Мы свяжемся с вами', 'success')
        return redirect(url_for('catalog'))
    
    conn.close()
    return render_template('apply.html', animal=animal)

@app.route('/admin/application/<int:app_id>/<action>')
@admin_required
def handle_application(app_id, action):
    conn = sqlite3.connect('shelter.db')
    c = conn.cursor()
    
    if action == 'approve':
        c.execute("UPDATE applications SET status = 'approved' WHERE id = ?", (app_id,))
        flash('Заявка одобрена', 'success')
    elif action == 'reject':
        c.execute("UPDATE applications SET status = 'rejected' WHERE id = ?", (app_id,))
        flash('Заявка отклонена', 'danger')
    
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)