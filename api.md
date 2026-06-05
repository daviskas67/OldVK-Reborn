# OldVK-Reborn API Documentation

Документация текущих API-эндпоинтов сервера OldVK-Reborn. Все запросы принимают и отдают данные в формате JSON (или стандартных POST-форм `application/x-www-form-urlencoded`).

---

## 1. Проверка номера телефона

Проверяет, привязан ли указанный номер телефона к какому-либо аккаунту в базе данных. Используется мобильным клиентом перед входом или регистрацией.

* **URL:** `/api/auth/checkPhone`
* **Метод:** `POST`
* **Формат данных:** JSON или URL-encoded форма

### Запрос
```json
{
  "phone": "+79991234567"
}

```

### Ответы

#### Аккаунт найден (Вход по паролю):

* **Код:** `200 OK`

```json
{
  "registered": true,
  "auth_type": "password"
}

```

#### Аккаунт не найден (Нужна регистрация):

* **Код:** `200 OK`

```json
{
  "registered": false,
  "auth_type": "register"
}

```

#### Ошибка запроса (Пустой номер):

* **Код:** `400 Bad Request`

```json
{
  "error": "Missing phone parameter"
}

```

---

## 2. Регистрация пользователя

Создает новый аккаунт в системе. Поддерживает как стандартную регистрацию, так и привязку телефона.

* **URL:** `/api/register`
* **Метод:** `POST`
* **Формат данных:** JSON или URL-encoded форма

### Запрос

```json
{
  "username": "test1",
  "password": "123",
  "phone": "+71234567890",
  "email": "user@example.com",
  "first_name": "Иван",
  "last_name": "Иванов"
}

```

### Ответы

#### Успешная регистрация:

* **Код:** `200 OK`

```json
{
  "success": true,
  "access_token": "a1b2c3d4e5f6...", 
  "user_id": 1
}

```

#### Ошибка (Не указан username или password):

* **Код:** `400 Bad Request`

```json
{
  "error": "Username and password required"
}

```

#### Ошибка (Юзернейм уже занят):

* **Код:** `409 Conflict`

```json
{
  "error": "Username already exists"
}

```

#### Ошибка (Телефон уже зарегистрирован):

* **Код:** `409 Conflict`

```json
{
  "error": "Phone number already registered"
}

```

---

## 3. Авторизация (Логин)

Вход в систему. В качестве логина (`username`) можно передавать сам юзернейм, email или номер телефона.

* **URL:** `/api/login`
* **Метод:** `POST`
* **Формат данных:** JSON или URL-encoded форма

### Запрос

```json
{
  "username": "+71234567890", 
  "password": "123"
}

```

### Ответы

#### Успешный вход:

* **Код:** `200 OK`
* *Примечание: Статус пользователя в базе данных автоматически меняется на `online = 1`.*

```json
{
  "success": true,
  "access_token": "a1b2c3d4e5f6...",
  "user_id": 1,
  "username": "test1",
  "first_name": "Иван",
  "last_name": "Иванов"
}

```

#### Ошибка (Неверные учетные данные):

* **Код:** `401 Unauthorized`

```json
{
  "error": "Invalid credentials"
}

```

---

## CORS и Системные заголовки

Сервер автоматически добавляет CORS-заголовки ко всем JSON-ответам, чтобы веб-версия приложения не блокировала запросы:

* `Access-Control-Allow-Origin: *`
* `Content-Type: application/json; charset=utf-8`

