#!/usr/bin/env python3
import sqlite3
import hashlib
import secrets
import json
import os
import urllib.parse
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

DB_PATH = '/home/daviskas/rescueoldvk/web-vesion/social.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        email TEXT,
        first_name TEXT,
        last_name TEXT,
        avatar TEXT,
        access_token TEXT,
        online INTEGER DEFAULT 0,
        created_at TIMESTAMP
    )''')
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

init_db()

class SocialServer(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == '/' or path == '/index.html':
            self.serve_webapp()
        elif path == '/api/feed':
            self.api_feed()
        elif path == '/api/messages/dialogs':
            self.api_dialogs()
        elif path == '/api/messages/with':
            self.api_messages_with(query.get('user_id', [None])[0])
        elif path == '/api/messages/unread':
            self.api_unread_count()
        elif path == '/api/users/search':
            self.api_search_users(query.get('q', [''])[0])
        elif path == '/api/users/info':
            self.api_user_info(query.get('user_id', [None])[0])
        elif path == '/api/notifications':
            self.api_notifications()
        elif path.startswith('/res/'):
            self.serve_static()
        else:
            self.send_error(404)

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode()
        try:
            data = json.loads(body)
        except:
            data = dict(urllib.parse.parse_qs(body))
            data = {k: v[0] for k, v in data.items()}

        if '/api/register' in self.path:
            self.api_register(data)
        elif '/api/login' in self.path:
            self.api_login(data)
        elif '/api/post/create' in self.path:
            self.api_create_post(data)
        elif '/api/like' in self.path:
            self.api_like(data)
        elif '/api/unlike' in self.path:
            self.api_unlike(data)
        elif '/api/comment' in self.path:
            self.api_comment(data)
        elif '/api/messages/send' in self.path:
            self.api_send_message(data)
        elif '/api/messages/read' in self.path:
            self.api_mark_read(data)
        elif '/api/notifications/read' in self.path:
            self.api_notifications_read(data)
        else:
            self.send_error(404)

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def get_user_by_token(self, token):
        if not token:
            return None
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, username, first_name, last_name, avatar FROM users WHERE access_token=?", (token,))
        user = c.fetchone()
        conn.close()
        if user:
            return {'id': user[0], 'username': user[1], 'first_name': user[2] or '', 'last_name': user[3] or '', 'avatar': user[4]}
        return None

    def api_register(self, data):
        username = data.get('username', '').strip()
        password = data.get('password', '')
        email = data.get('email', '')
        first_name = data.get('first_name', '')
        last_name = data.get('last_name', '')
        if not username or not password:
            self.send_json({'error': 'Username and password required'}, 400)
            return
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE username=?", (username,))
        if c.fetchone():
            self.send_json({'error': 'Username already exists'}, 409)
            conn.close()
            return
        token = secrets.token_hex(32)
        hashed = hashlib.sha256(password.encode()).hexdigest()
        c.execute("INSERT INTO users (username, password, email, first_name, last_name, access_token, created_at) VALUES (?,?,?,?,?,?,?)",
                  (username, hashed, email, first_name, last_name, token, datetime.now().isoformat()))
        user_id = c.lastrowid
        conn.commit()
        conn.close()
        self.send_json({'success': True, 'access_token': token, 'user_id': user_id})

    def api_login(self, data):
        username = data.get('username', '')
        password = data.get('password', '')
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        hashed = hashlib.sha256(password.encode()).hexdigest()
        c.execute("SELECT id, username, first_name, last_name, access_token FROM users WHERE (username=? OR email=?) AND password=?", 
                  (username, username, hashed))
        user = c.fetchone()
        if user:
            c.execute("UPDATE users SET online=1 WHERE id=?", (user[0],))
            conn.commit()
            self.send_json({'success': True, 'access_token': user[4], 'user_id': user[0],
                            'username': user[1], 'first_name': user[2] or '', 'last_name': user[3] or ''})
        else:
            self.send_json({'error': 'Invalid credentials'}, 401)
        conn.close()

    def api_search_users(self, query):
        token = self.headers.get('Authorization', '').replace('Bearer ', '')
        user = self.get_user_by_token(token)
        if not user:
            self.send_json({'error': 'Unauthorized'}, 401)
            return
        if not query:
            self.send_json({'users': []})
            return
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""SELECT id, username, first_name, last_name, avatar FROM users 
                     WHERE (username LIKE ? OR first_name LIKE ? OR last_name LIKE ? OR (first_name || ' ' || last_name) LIKE ?)
                     AND id != ? LIMIT 30""",
                  (f'%{query}%', f'%{query}%', f'%{query}%', f'%{query}%', user['id']))
        rows = c.fetchall()
        users = [{'id': r[0], 'username': r[1], 'first_name': r[2] or '', 'last_name': r[3] or '', 'avatar': r[4]} for r in rows]
        conn.close()
        self.send_json({'users': users})

    def api_user_info(self, user_id):
        token = self.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            self.send_json({'error': 'Unauthorized'}, 401)
            return
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, username, first_name, last_name, avatar FROM users WHERE id=?", (user_id,))
        row = c.fetchone()
        conn.close()
        if row:
            self.send_json({'user': {'id': row[0], 'username': row[1], 'first_name': row[2] or '', 'last_name': row[3] or '', 'avatar': row[4]}})
        else:
            self.send_json({'error': 'User not found'}, 404)

    def api_feed(self):
        token = self.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            self.send_json({'error': 'Unauthorized'}, 401)
            return
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""SELECT p.id, p.content, p.image, p.likes, p.comments_count, p.created_at,
                            u.id, u.username, u.first_name, u.last_name, u.avatar
                     FROM posts p JOIN users u ON p.user_id = u.id
                     ORDER BY p.created_at DESC LIMIT 50""")
        posts = []
        for row in c.fetchall():
            # Проверяем, лайкнул ли текущий пользователь
            current_user = self.get_user_by_token(token)
            user_liked = False
            if current_user:
                c2 = conn.cursor()
                c2.execute("SELECT 1 FROM likes WHERE post_id=? AND user_id=?", (row[0], current_user['id']))
                user_liked = c2.fetchone() is not None
                c2.close()
            posts.append({
                'id': row[0], 'content': row[1], 'image': row[2], 'likes': row[3] or 0,
                'comments_count': row[4] or 0, 'date': row[5] if row[5] else '',
                'user_id': row[6], 'username': row[7], 'first_name': row[8] or '', 
                'last_name': row[9] or '', 'avatar': row[10], 'user_liked': user_liked
            })
        conn.close()
        self.send_json({'posts': posts})

    def api_create_post(self, data):
        token = data.get('token', '')
        user = self.get_user_by_token(token)
        if not user:
            self.send_json({'error': 'Unauthorized'}, 401)
            return
        content = data.get('content', '').strip()
        if not content:
            self.send_json({'error': 'Content required'}, 400)
            return
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO posts (user_id, content, created_at) VALUES (?,?,?)",
                  (user['id'], content, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        self.send_json({'success': True})

    def api_like(self, data):
        token = data.get('token', '')
        user = self.get_user_by_token(token)
        if not user:
            self.send_json({'error': 'Unauthorized'}, 401)
            return
        post_id = data.get('post_id')
        if not post_id:
            self.send_json({'error': 'Missing post_id'}, 400)
            return
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute("INSERT INTO likes (user_id, post_id, created_at) VALUES (?,?,?)", 
                      (user['id'], post_id, datetime.now().isoformat()))
            c.execute("UPDATE posts SET likes = likes + 1 WHERE id=?", (post_id,))
            # Уведомление
            c.execute("SELECT user_id FROM posts WHERE id=?", (post_id,))
            post_owner = c.fetchone()
            if post_owner and post_owner[0] != user['id']:
                c.execute("INSERT INTO notifications (user_id, from_id, type, post_id, created_at) VALUES (?,?,?,?,?)",
                          (post_owner[0], user['id'], 'like', post_id, datetime.now().isoformat()))
            conn.commit()
            c.execute("SELECT likes FROM posts WHERE id=?", (post_id,))
            count = c.fetchone()[0]
            self.send_json({'success': True, 'likes': count})
        except sqlite3.IntegrityError:
            self.send_json({'error': 'Already liked'}, 400)
        conn.close()

    def api_unlike(self, data):
        token = data.get('token', '')
        user = self.get_user_by_token(token)
        if not user:
            self.send_json({'error': 'Unauthorized'}, 401)
            return
        post_id = data.get('post_id')
        if not post_id:
            self.send_json({'error': 'Missing post_id'}, 400)
            return
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM likes WHERE user_id=? AND post_id=?", (user['id'], post_id))
        c.execute("UPDATE posts SET likes = likes - 1 WHERE id=?", (post_id,))
        conn.commit()
        c.execute("SELECT likes FROM posts WHERE id=?", (post_id,))
        count = c.fetchone()[0]
        conn.close()
        self.send_json({'success': True, 'likes': count})

    def api_comment(self, data):
        token = data.get('token', '')
        user = self.get_user_by_token(token)
        if not user:
            self.send_json({'error': 'Unauthorized'}, 401)
            return
        post_id = data.get('post_id')
        content = data.get('content', '').strip()
        if not post_id or not content:
            self.send_json({'error': 'Missing fields'}, 400)
            return
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO comments (post_id, user_id, content, created_at) VALUES (?,?,?,?)",
                  (post_id, user['id'], content, datetime.now().isoformat()))
        c.execute("UPDATE posts SET comments_count = comments_count + 1 WHERE id=?", (post_id,))
        # Уведомление
        c.execute("SELECT user_id FROM posts WHERE id=?", (post_id,))
        post_owner = c.fetchone()
        if post_owner and post_owner[0] != user['id']:
            c.execute("INSERT INTO notifications (user_id, from_id, type, post_id, created_at) VALUES (?,?,?,?,?)",
                      (post_owner[0], user['id'], 'comment', post_id, datetime.now().isoformat()))
        conn.commit()
        c.execute("""SELECT c.id, c.content, c.created_at, u.id, u.username, u.first_name, u.last_name, u.avatar
                     FROM comments c JOIN users u ON c.user_id = u.id WHERE c.id = last_insert_rowid()""")
        row = c.fetchone()
        c.execute("SELECT comments_count FROM posts WHERE id=?", (post_id,))
        comments_count = c.fetchone()[0]
        conn.close()
        self.send_json({
            'success': True,
            'comment': {
                'id': row[0], 'content': row[1], 'date': row[2],
                'user_id': row[3], 'username': row[4], 'first_name': row[5] or '', 
                'last_name': row[6] or '', 'avatar': row[7]
            },
            'comments_count': comments_count
        })

    def api_notifications(self):
        token = self.headers.get('Authorization', '').replace('Bearer ', '')
        user = self.get_user_by_token(token)
        if not user:
            self.send_json({'error': 'Unauthorized'}, 401)
            return
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""SELECT n.id, n.type, n.post_id, n.created_at, n.read,
                            u.id, u.username, u.first_name, u.last_name, u.avatar
                     FROM notifications n
                     JOIN users u ON n.from_id = u.id
                     WHERE n.user_id = ?
                     ORDER BY n.created_at DESC LIMIT 50""", (user['id'],))
        notifs = []
        for row in c.fetchall():
            notifs.append({
                'id': row[0], 'type': row[1], 'post_id': row[2], 'date': row[3], 'read': row[4],
                'from_user': {'id': row[5], 'username': row[6], 'first_name': row[7] or '', 'last_name': row[8] or '', 'avatar': row[9]}
            })
        conn.close()
        self.send_json({'notifications': notifs})

    def api_notifications_read(self, data):
        token = data.get('token', '')
        user = self.get_user_by_token(token)
        if not user:
            self.send_json({'error': 'Unauthorized'}, 401)
            return
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE notifications SET read=1 WHERE user_id=?", (user['id'],))
        conn.commit()
        conn.close()
        self.send_json({'success': True})

    def api_dialogs(self):
        token = self.headers.get('Authorization', '').replace('Bearer ', '')
        user = self.get_user_by_token(token)
        if not user:
            self.send_json({'error': 'Unauthorized'}, 401)
            return
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            SELECT u.id, u.username, u.first_name, u.last_name, u.avatar,
                   (SELECT text FROM messages WHERE (from_id=u.id AND to_id=?) OR (from_id=? AND to_id=u.id) 
                    ORDER BY created_at DESC LIMIT 1) as last_text,
                   (SELECT COUNT(*) FROM messages WHERE to_id=? AND from_id=u.id AND read=0) as unread
            FROM users u
            WHERE u.id IN (SELECT from_id FROM messages WHERE to_id=?) OR u.id IN (SELECT to_id FROM messages WHERE from_id=?)
            AND u.id != ?
            GROUP BY u.id
            ORDER BY last_text DESC""",
            (user['id'], user['id'], user['id'], user['id'], user['id'], user['id']))
        dialogs = []
        for row in c.fetchall():
            dialogs.append({
                'id': row[0], 'username': row[1], 'first_name': row[2] or '', 'last_name': row[3] or '', 'avatar': row[4],
                'last_message': row[5], 'unread': row[6] or 0
            })
        conn.close()
        self.send_json({'dialogs': dialogs})

    def api_messages_with(self, other_id):
        if not other_id:
            self.send_json({'error': 'Missing user_id'}, 400)
            return
        token = self.headers.get('Authorization', '').replace('Bearer ', '')
        user = self.get_user_by_token(token)
        if not user:
            self.send_json({'error': 'Unauthorized'}, 401)
            return
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""SELECT m.id, m.text, m.created_at, m.from_id, m.read,
                            u.username, u.first_name, u.last_name
                     FROM messages m JOIN users u ON u.id = m.from_id
                     WHERE (m.from_id=? AND m.to_id=?) OR (m.from_id=? AND m.to_id=?)
                     ORDER BY m.created_at ASC""", (user['id'], other_id, other_id, user['id']))
        messages = []
        for row in c.fetchall():
            messages.append({
                'id': row[0], 'text': row[1], 'date': row[2] if row[2] else '', 'from_id': row[3], 'read': row[4],
                'username': row[5], 'first_name': row[6] or '', 'last_name': row[7] or ''
            })
        conn.close()
        self.send_json({'messages': messages, 'other_id': int(other_id)})

    def api_send_message(self, data):
        token = data.get('token', '')
        user = self.get_user_by_token(token)
        if not user:
            self.send_json({'error': 'Unauthorized'}, 401)
            return
        to_id = data.get('to_id')
        text = data.get('text', '').strip()
        if not to_id or not text:
            self.send_json({'error': 'Missing fields'}, 400)
            return
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO messages (from_id, to_id, text, created_at) VALUES (?,?,?,?)",
                  (user['id'], to_id, text, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        self.send_json({'success': True})

    def api_unread_count(self):
        token = self.headers.get('Authorization', '').replace('Bearer ', '')
        user = self.get_user_by_token(token)
        if not user:
            self.send_json({'error': 'Unauthorized'}, 401)
            return
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM messages WHERE to_id=? AND read=0", (user['id'],))
        messages = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND read=0", (user['id'],))
        notifs = c.fetchone()[0]
        conn.close()
        self.send_json({'unread': messages, 'notifications': notifs})

    def api_mark_read(self, data):
        token = data.get('token', '')
        user = self.get_user_by_token(token)
        if not user:
            self.send_json({'error': 'Unauthorized'}, 401)
            return
        other_id = data.get('other_id')
        if not other_id:
            self.send_json({'error': 'Missing other_id'}, 400)
            return
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE messages SET read=1 WHERE to_id=? AND from_id=?", (user['id'], other_id))
        conn.commit()
        conn.close()
        self.send_json({'success': True})

    def serve_webapp(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        with open('/home/daviskas/rescueoldvk/web-vesion/index.html', 'r', encoding='utf-8') as f:
            html = f.read()
        self.wfile.write(html.encode())

    def serve_static(self):
        path = self.path[1:]
        if os.path.exists(path):
            self.send_response(200)
            if path.endswith('.css'):
                self.send_header('Content-Type', 'text/css')
            elif path.endswith('.js'):
                self.send_header('Content-Type', 'application/javascript')
            elif path.endswith('.png'):
                self.send_header('Content-Type', 'image/png')
            elif path.endswith('.gif'):
                self.send_header('Content-Type', 'image/gif')
            elif path.endswith('.jpg') or path.endswith('.jpeg'):
                self.send_header('Content-Type', 'image/jpeg')
            self.end_headers()
            with open(path, 'rb') as f:
                self.wfile.write(f.read())
        else:
            self.send_error(404)

if __name__ == '__main__':
    print("="*50)
    print("OldVK Social Network - с комментариями и уведомлениями")
    print("="*50)
    print("Web: http://localhost:8081")
    print("API: http://localhost:8081/api")
    print("="*50)
    HTTPServer(("0.0.0.0", 8081), SocialServer).serve_forever()
