import os

# Карта MIME-типов, чтобы браузер понимал, что ему прилетело
MIME_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon'
}

def handle_web_request(handler, path):
    # Если стучатся в корень, перенаправляем на index.html
    if path == '/':
        path = '/index.html'
    
    # Убираем GET-параметры из пути файла, если они есть (например, /style.css?v=1)
    clean_path = path.split('?')[0]
    file_path = f"content{clean_path}"
    
    # Проверяем существование файла
    if os.path.exists(file_path) and os.path.isfile(file_path):
        handler.send_response(200)
        
        # Определяем MIME-тип по расширению файла
        _, ext = os.path.splitext(clean_path)
        content_type = MIME_TYPES.get(ext.lower(), 'application/octet-stream')
        
        handler.send_header('Content-Type', content_type)
        handler.end_headers()
        
        # Читаем файл побайтово и отправляем в браузер
        with open(file_path, 'rb') as f:
            handler.wfile.write(f.read())
        return True
        
    return False # Файл не найден, main.py выдаст 404
