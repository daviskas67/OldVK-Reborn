import sqlite3
import json

# Переменная для хранения пути к БД (заполняется при старте из main.py)
DB_PATH = "social.db"

def init_database(db_path):
    """ Настраивает путь к БД и создает таблицы, если их нет """
    global DB_PATH
    DB_PATH = db_path
    
    # Тут можно прописать CREATE TABLE IF NOT EXISTS для ваших таблиц
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Пример:
    # cursor.execute("CREATE TABLE IF NOT EXISTS users (...)")
    conn.commit()
    conn.close()

def send_json_response(handler, status_code, data):
    """ Вспомогательная функция для отправки JSON ответов """
    handler.send_response(status_code)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.end_headers()
    handler.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

# --- ТУТ БУДУТ ВАШИ ФУНКЦИИ API ---

# --- КАРТА МАРШРУТОВ API ---
# Сюда просто добавляете новые эндпоинты по мере написания
ROUTES = {
#    'GET': {
#        '/api/test': test,
#    },
}

def handle_api_request(handler, path, method):
    """ Главный обработчик API, вызываемый из main.py """
    # Очищаем путь от GET-параметров для проверки роута
    clean_path = path.split('?')[0]
    
    if method in ROUTES and clean_path in ROUTES[method]:
        # Вызываем нужную функцию из карты маршрутов
        ROUTES[method][clean_path](handler)
        return True
        
    return False # Маршрут не найден в API
