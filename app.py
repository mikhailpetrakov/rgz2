from flask import Flask, render_template, request, redirect, url_for, session, current_app,flash,get_flashed_messages
import psycopg2
from psycopg2.extras import RealDictCursor
import sqlite3
from os import path

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['DB_TYPE'] = 'postgres'  # или 'sqlite' для SQLite

def db_connect():
    if current_app.config['DB_TYPE'] == 'postgres':
        conn = psycopg2.connect(
            host='127.0.0.1',
            database='dating_site',
            user='dating_user',
            password='your_password',
            port=5432
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)
    else:
        dir_path = path.dirname(path.realpath(__file__))
        db_path = path.join(dir_path, "database.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
    return conn, cur

def db_close(conn, cur):
    conn.commit()
    cur.close()
    conn.close()


@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('profile'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn, cur = db_connect()
        try:
            if current_app.config['DB_TYPE'] == 'postgres':
                cur.execute('INSERT INTO users (username, password, name, age, gender, search_gender) VALUES (%s, %s, %s, %s, %s, %s)',
                            (username, password, '', 0, '', ''))
            else:
                cur.execute('INSERT INTO users (username, password, name, age, gender, search_gender) VALUES (?, ?, ?, ?, ?, ?)',
                            (username, password, '', 0, '', ''))
            db_close(conn, cur)
            session['username'] = username
            flash('Регистрация прошла успешно!', 'success')
            return redirect(url_for('edit_profile'))
        except Exception as e:
            db_close(conn, cur)
            flash('Ошибка при регистрации. Возможно, имя пользователя уже занято.', 'error')
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn, cur = db_connect()
        if current_app.config['DB_TYPE'] == 'postgres':
            cur.execute('SELECT * FROM users WHERE username = %s AND password = %s', (username, password))
        else:
            cur.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password))
        user = cur.fetchone()
        db_close(conn, cur)
        if user:
            session['username'] = username
            session['is_admin'] = user['is_admin']
            flash('Вход выполнен успешно!', 'success')
            return redirect(url_for('profile'))
        else:
            flash('Неверное имя пользователя или пароль.', 'error')
    return render_template('login.html')

@app.route('/profile')
def profile():
    if 'username' not in session:
        return redirect(url_for('index'))
    conn, cur = db_connect()
    if current_app.config['DB_TYPE'] == 'postgres':
        cur.execute('SELECT * FROM users WHERE username = %s', (session['username'],))
    else:
        cur.execute('SELECT * FROM users WHERE username = ?', (session['username'],))
    user = cur.fetchone()
    db_close(conn, cur)
    return render_template('profile.html', user=user)

@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'username' not in session:
        return redirect(url_for('index'))
    conn, cur = db_connect()
    if current_app.config['DB_TYPE'] == 'postgres':
        cur.execute('SELECT * FROM users WHERE username = %s', (session['username'],))
    else:
        cur.execute('SELECT * FROM users WHERE username = ?', (session['username'],))
    user = cur.fetchone()
    if request.method == 'POST':
        name = request.form['name']
        age = request.form['age']
        gender = request.form['gender']
        search_gender = request.form['search_gender']
        about = request.form['about']
        photo = request.form['photo']
        if current_app.config['DB_TYPE'] == 'postgres':
            cur.execute('''
                UPDATE users SET name = %s, age = %s, gender = %s, search_gender = %s, about = %s, photo = %s
                WHERE username = %s
            ''', (name, age, gender, search_gender, about, photo, session['username']))
        else:
            cur.execute('''
                UPDATE users SET name = ?, age = ?, gender = ?, search_gender = ?, about = ?, photo = ?
                WHERE username = ?
            ''', (name, age, gender, search_gender, about, photo, session['username']))
        db_close(conn, cur)
        flash('Профиль успешно обновлен!', 'success')
        return redirect(url_for('profile'))
    db_close(conn, cur)
    return render_template('edit_profile.html', user=user)

@app.route('/search', methods=['GET', 'POST'])
def search():
    if 'username' not in session:
        return redirect(url_for('index'))

    conn, cur = db_connect()
    if current_app.config['DB_TYPE'] == 'postgres':
        cur.execute('SELECT * FROM users WHERE username = %s', (session['username'],))
    else:
        cur.execute('SELECT * FROM users WHERE username = ?', (session['username'],))
    current_user = cur.fetchone()

    if request.method == 'POST':
        action = request.form.get('action')
        liked_user_id = request.form.get('liked_user_id')

        if action and liked_user_id:
            if current_app.config['DB_TYPE'] == 'postgres':
                cur.execute('INSERT INTO likes (user_id, liked_user_id, liked) VALUES (%s, %s, %s)',
                            (current_user['id'], liked_user_id, True if action == 'like' else False))
            else:
                cur.execute('INSERT INTO likes (user_id, liked_user_id, liked) VALUES (?, ?, ?)',
                            (current_user['id'], liked_user_id, True if action == 'like' else False))
            db_close(conn, cur)
            return redirect(url_for('search'))

    # Поиск следующего пользователя
    
    query = '''
        SELECT * FROM users 
        WHERE id != ? 
        AND gender = ? 
        AND search_gender = ? 
        AND hidden = FALSE 
        AND id NOT IN (
            SELECT liked_user_id FROM likes WHERE user_id = ?
        )
    '''
    params = [current_user['id'], current_user['search_gender'], current_user['gender'], current_user['id']]

    # Добавляем фильтр по возрасту, если он указан и корректен
    age = request.form.get('age')
    if age and age.isdigit():  # Проверяем, что возраст является числом
        query += ' AND age = ?'
        params.append(int(age))

    query += ' LIMIT 1'

    if current_app.config['DB_TYPE'] == 'postgres':
        query = query.replace('?', '%s')

    cur.execute(query, params)
    next_user = cur.fetchone()

    db_close(conn, cur)
    return render_template('search.html', user=next_user)

@app.route('/hide_profile', methods=['POST'])
def hide_profile():
    if 'username' not in session:
        return redirect(url_for('index'))
    conn, cur = db_connect()
    cur.execute('UPDATE users SET hidden = TRUE WHERE username = %s', (session['username'],))
    db_close(conn, cur)
    return redirect(url_for('profile'))

@app.route('/delete_account', methods=['POST'])
def delete_account():
    if 'username' not in session:
        return redirect(url_for('index'))

    conn, cur = db_connect()

    # Удаляем все лайки пользователя из таблицы likes
    if current_app.config['DB_TYPE'] == 'postgres':
        cur.execute('DELETE FROM likes WHERE user_id = (SELECT id FROM users WHERE username = %s)', (session['username'],))
    else:
        cur.execute('DELETE FROM likes WHERE user_id = (SELECT id FROM users WHERE username = ?)', (session['username'],))

    # Удаляем пользователя из таблицы users
    if current_app.config['DB_TYPE'] == 'postgres':
        cur.execute('DELETE FROM users WHERE username = %s', (session['username'],))
    else:
        cur.execute('DELETE FROM users WHERE username = ?', (session['username'],))

    db_close(conn, cur)

    # Удаляем пользователя из сессии
    session.pop('username', None)

    flash('Ваш аккаунт успешно удален.', 'success')
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('index'))

@app.route('/admin_panel')
def admin_panel():
    if 'username' not in session or not session.get('is_admin'):
        return redirect(url_for('index'))

    conn, cur = db_connect()
    cur.execute('SELECT * FROM users')
    users = cur.fetchall()
    db_close(conn, cur)

    return render_template('admin_panel.html', users=users)


@app.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    if 'username' not in session or not session.get('is_admin'):
        return redirect(url_for('index'))

    conn, cur = db_connect()
    if current_app.config['DB_TYPE'] == 'postgres':
        cur.execute('SELECT * FROM users WHERE id = %s', (user_id,))
    else:
        cur.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user = cur.fetchone()

    if request.method == 'POST':
        name = request.form['name']
        age = request.form['age']
        gender = request.form['gender']
        search_gender = request.form['search_gender']
        about = request.form['about']
        photo = request.form['photo']
        if current_app.config['DB_TYPE'] == 'postgres':
            cur.execute('''
                UPDATE users SET name = %s, age = %s, gender = %s, search_gender = %s, about = %s, photo = %s
                WHERE id = %s
            ''', (name, age, gender, search_gender, about, photo, user_id))
        else:
            cur.execute('''
                UPDATE users SET name = ?, age = ?, gender = ?, search_gender = ?, about = ?, photo = ?
                WHERE id = ?
            ''', (name, age, gender, search_gender, about, photo, user_id))
        db_close(conn, cur)
        flash('Профиль пользователя успешно обновлен!', 'success')
        return redirect(url_for('admin_panel'))

    db_close(conn, cur)
    return render_template('edit_user.html', user=user)

@app.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if 'username' not in session or not session.get('is_admin'):
        return redirect(url_for('index'))

    conn, cur = db_connect()
    if current_app.config['DB_TYPE'] == 'postgres':
        cur.execute('DELETE FROM users WHERE id = %s', (user_id,))
    else:
        cur.execute('DELETE FROM users WHERE id = ?', (user_id,))
    db_close(conn, cur)
    flash('Пользователь успешно удален.', 'success')
    return redirect(url_for('admin_panel'))