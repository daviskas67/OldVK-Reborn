#!/usr/bin/env python3
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler
import api
import web

class OldVKRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 1. Сначала проверяем, не API ли это запрос
        if api.handle_api_request(self, self.path, method='GET'):
            return
        # 2. Если не API, пытаемся отдать статический файл (HTML/CSS/JS)
        if web.handle_web_request(self, self.path):
            return
        # 3. Если ничего не нашли — 404
        self.send_error(404, "Страница не найдена")

    def do_POST(self):
        # POST-запросы обычно идут только в API (регистрация, посты, сообщения)
        if api.handle_api_request(self, self.path, method='POST'):
            return
        self.send_error(404, "API эндпоинт не найден")

def main():
    parser = argparse.ArgumentParser(description="OldVK-Reborn Server")
    parser.add_argument('-p', '--port', type=int, default=8081, help='Порт сервера')
    parser.add_argument('-d', '--db', type=str, default='social.db', help='Путь к базе данных SQLite')
    args = parser.parse_args()

    # Инициализируем базу данных в модуле API перед запуском сервера
    api.init_database(args.db)

    server = HTTPServer(('0.0.0.0', args.port), OldVKRequestHandler)
    print(f"🚀 Сервер OldVK-Reborn успешно запущен!")
    print(f"🏠 Локальный адрес: http://localhost:{args.port}")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Сервер успешно остановлен. До встречи!")

if __name__ == '__main__':
    main()
