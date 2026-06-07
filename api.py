import sqlite3
import json
import hashlib
import secrets
import urllib.parse
from datetime import datetime

DB_PATH = "social.db"

def init_database(db_path):
    """ Инициализация базы данных и создание всех таблиц из старого сервера """
    global DB_PATH
    DB_PATH = db_path
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 1. Создаем таблицу пользователей (теперь phone встроен изначально для чистой установки)
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        phone TEXT UNIQUE,
        email TEXT,
        first_name TEXT,
        last_name TEXT,
        avatar TEXT,
        access_token TEXT,
        online INTEGER DEFAULT 0,
        created_at TIMESTAMP
    )''')
    
    # МИГРАЦИЯ: Если база старая и поля phone нет — добавляем его безопасно через INDEX
    try:
        c.execute("SELECT phone FROM users LIMIT 1")
    except sqlite3.OperationalError:
        print("🔧 Старая база обнаружена. Добавляю колонку 'phone'...")
        # Добавляем просто как текст (SQLite это разрешает)
        c.execute("ALTER TABLE users ADD COLUMN phone TEXT")
        # Создаем уникальный индекс, чтобы обойти ограничение ALTER TABLE UNIQUE
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_phone ON users(phone)")
    
    # 2. Создаем остальные таблицы из старого server.py
    c.execute('''CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        content TEXT,
        image TEXT,
        likes INTEGER DEFAULT 0,
        comments_count INTEGER DEFAULT 0,
        created_at TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS likes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        post_id INTEGER,
        created_at TIMESTAMP,
        UNIQUE(user_id, post_id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER,
        user_id INTEGER,
        content TEXT,
        created_at TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_id INTEGER,
        to_id INTEGER,
        text TEXT,
        read INTEGER DEFAULT 0,
        created_at TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        from_id INTEGER,
        type TEXT,
        post_id INTEGER,
        read INTEGER DEFAULT 0,
        created_at TIMESTAMP
    )''')
    
    conn.commit()
    conn.close()

def send_json_response(handler, status_code, data):
    """ Хелпер для отправки JSON (с поддержкой CORS как в старом сервере) """
    handler.send_response(status_code)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Access-Control-Allow-Origin', '*')
    handler.end_headers()
    handler.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

def parse_post_data(handler):
    """ Хелпер, который умеет читать и JSON, и обычные POST-формы из телефона """
    length = int(handler.headers.get('Content-Length', 0))
    if length == 0:
        return {}
        
    body = handler.rfile.read(length).decode('utf-8')
    try:
        return json.loads(body)
    except ValueError:
        parsed = urllib.parse.parse_qs(body)
        return {k: v[0] for k, v in parsed.items()}


# --- ОБРАБОТЧИКИ API (ЭНДПОИНТЫ) ---

def api_check_phone(handler):
    """ Проверка: есть ли номер телефона в базе данных """
    data = parse_post_data(handler)
    phone = data.get('phone', '').strip()
    
    if not phone:
        return send_json_response(handler, 400, {"error": "Missing phone parameter"})
        
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE phone = ?", (phone,))
    user_exists = c.fetchone() is not None
    conn.close()
    
    if user_exists:
        send_json_response(handler, 200, {"registered": True, "auth_type": "password"})
    else:
        send_json_response(handler, 200, {"registered": False, "auth_type": "register"})

def api_register(handler):
    """ Регистрация нового пользователя с поддержкой телефона """
    data = parse_post_data(handler)
    
    username = data.get('username', '').strip()
    password = data.get('password', '')
    phone = data.get('phone', '').strip()
    email = data.get('email', '').strip()
    first_name = data.get('first_name', '')
    last_name = data.get('last_name', '')
    
    if not username or not password:
        return send_json_response(handler, 400, {'error': 'Username and password required'})
        
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("SELECT id FROM users WHERE username=?", (username,))
    if c.fetchone():
        conn.close()
        return send_json_response(handler, 409, {'error': 'Username already exists'})
        
    if phone:
        c.execute("SELECT id FROM users WHERE phone=?", (phone,))
        if c.fetchone():
            conn.close()
            return send_json_response(handler, 409, {'error': 'Phone number already registered'})

    token = secrets.token_hex(32)
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    
    c.execute("""INSERT INTO users (username, password, phone, email, first_name, last_name, access_token, created_at) 
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
              (username, hashed_password, phone, email, first_name, last_name, token, datetime.now().isoformat()))
              
    user_id = c.lastrowid
    conn.commit()
    conn.close()
    
    send_json_response(handler, 200, {'success': True, 'access_token': token, 'user_id': user_id})

def api_login(handler):
    """ Авторизация (логин) """
    data = parse_post_data(handler)
    username = data.get('username', '')
    password = data.get('password', '')
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    hashed = hashlib.sha256(password.encode()).hexdigest()
    
    c.execute("""SELECT id, username, first_name, last_name, access_token FROM users 
                 WHERE (username=? OR email=? OR phone=?) AND password=?""", 
              (username, username, username, hashed))
              
    user = c.fetchone()
    if user:
        c.execute("UPDATE users SET online=1 WHERE id=?", (user[0],))
        conn.commit()
        send_json_response(handler, 200, {
            'success': True, 
            'access_token': user[4], 
            'user_id': user[0],
            'username': user[1], 
            'first_name': user[2] or '', 
            'last_name': user[3] or ''
        })
    else:
        send_json_response(handler, 401, {'error': 'Invalid credentials'})
    conn.close()


# --- КАРТА МАРШРУТОВ API ---
ROUTES = {
    'GET': {},
    'POST': {
        '/api/login': api_login,
        '/api/register': api_register,
        '/api/auth/checkPhone': api_check_phone,
    }
}

def handle_api_request(handler, path, method):
    """ Главный диспетчер API """
    clean_path = path.split('?')[0]
    
    if method in ROUTES and clean_path in ROUTES[method]:
        ROUTES[method][clean_path](handler)
        return True
    return False
