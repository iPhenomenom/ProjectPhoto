from datetime import datetime, timedelta
from typing import Optional, List
from router import router
import uvicorn as uvicorn
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
import jwt
import secrets


# Конфігурація Cloudinary


app = FastAPI()

# Налаштування JWT токенів
SECRET_KEY = secrets.token_hex(32)  # "your_secret_key"  Замініть це на ваш секретний ключ
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


# Оголошення моделі користувача
class User(BaseModel):
    username: str
    password: str
    role: str
    is_active: bool = True  # Поле для позначення активності користувача
    registered_at: datetime = datetime.utcnow()  # Поле для дати реєстрації користувача
    uploaded_photos: int = 0  # Поле для підрахунку завантажених фото


# Генерація JWT токена
def create_access_token(data: dict, expires_delta: timedelta):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# Функція для отримання користувача з бази даних
def get_user(username: str):
    # Замініть цей код на звернення до бази даних або іншим методом отримання користувачів
    users = [
        User(username="admin", password="adminpass", role="admin"),
        User(username="moderator", password="modpass", role="moderator"),
        User(username="user", password="userpass", role="user"),
    ]
    for user in users:
        if user.username == username:
            return user
    return None


# Захищений маркер доступу (Bearer token)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# Функція для перевірки дійсності та отримання інформації з токена
def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        token_data = {"username": username}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    user = get_user(username=token_data["username"])
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return user


# Функція для перевірки ролі користувача
def role_dependency(required_role: str = None):
    def check_role(user: User = Depends(get_current_user)):
        if required_role is None or user.role == required_role:
            return user
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have enough permissions")

    return check_role


# Модель для коментаря
class Comment(BaseModel):
    id: int
    image_id: int
    text: str
    created_at: datetime
    edited_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None  # Додали поле для часу редагування коментаря


# Cимулюємо базу даних списком
comments_db = []


# Маршрут для додавання коментарів під світлинами
@app.post("/comments/", response_model=Comment)
def create_comment(image_id: int, text: str, user: User = Depends(role_dependency())):
    image = next((img for img in comments_db if img.id == image_id), None)
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found")
    comment = Comment(id=len(comments_db) + 1, image_id=image_id, text=text, created_at=datetime.utcnow())
    comments_db.append(comment)
    return comment


# Маршрут для редагування свого коментаря
@app.put("/comments/{comment_id}", response_model=Comment)
def update_comment(comment_id: int, text: str, user: User = Depends(role_dependency())):
    comment = next((cmt for cmt in comments_db if cmt.id == comment_id), None)
    if comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    if comment.user.username != user.username:
        raise HTTPException(status_code=403, detail="You can only edit your own comments")
    comment.text = text
    comment.edited_at = datetime.utcnow()
    return comment


# Маршрут для видалення коментарів модераторами та адміністраторами
@app.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(comment_id: int, user: User = Depends(role_dependency(required_role="moderator"))):
    global comments_db
    comments_db = [cmt for cmt in comments_db if cmt.id != comment_id]
    return


# Маршрут для додавання коментарів під світлинами
@app.post("/images/{image_id}/comments/", response_model=Comment)
def add_comment_to_image(image_id: int, text: str, current_user: User = Depends(get_current_user)):
    image = next((img for img in database if img.id == image_id), None)
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found")

    comment = Comment(id=len(comments_db) + 1, image_id=image_id, text=text, created_at=datetime.utcnow())
    image.comments.append(comment)
    return comment


# Маршрут для редагування свого коментаря
@app.put("/images/{image_id}/comments/{comment_id}", response_model=Comment)
def update_comment(image_id: int, comment_id: int, text: str, current_user: User = Depends(get_current_user)):
    image = next((img for img in database if img.id == image_id), None)
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found")

    comment = next((cmt for cmt in image.comments if cmt.id == comment_id), None)
    if comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")

    if comment.user.username != current_user.username:
        raise HTTPException(status_code=403, detail="You can only edit your own comments")

    comment.text = text
    comment.updated_at = datetime.utcnow()  # Оновлюємо час редагування коментаря
    return comment


# Модель для зображення
class Image(BaseModel):
    id: int
    url: str
    description: str
    tags: List[str]
    comments: List[Comment] = []  # Поле для зберігання коментарів під зображенням


# База даних імітуємо простим списком
database = []


# Симуляція завантаження зображення на Cloudinary
def upload_image_to_cloudinary(image_data: bytes):
    # Код для завантаження на Cloudinary тут
    cloudinary_url = "https://your-cloudinary-image-url.com/image.jpg"
    return cloudinary_url


# Маршрут для завантаження світлин з описом
@app.post("/images/", response_model=Image)
def create_image(image_data: bytes, description: str, tags: Optional[List[str]] = None,
                 user: User = Depends(role_dependency())):
    cloudinary_url = upload_image_to_cloudinary(image_data)
    image = Image(id=len(database) + 1, url=cloudinary_url, description=description, tags=tags or [])
    database.append(image)
    return image


# Маршрут для отримання світлини за унікальним посиланням
@app.get("/images/{image_id}", response_model=Image)
def get_image(image_id: int):
    image = next((img for img in database if img.id == image_id), None)
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found")
    return image


# Маршрут для редагування опису світлини
@app.put("/images/{image_id}", response_model=Image)
def update_image(image_id: int, description: str, user: User = Depends(role_dependency("admin"))):
    image = next((img for img in database if img.id == image_id), None)
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found")
    image.description = description
    return image


# Маршрут для видалення світлини
@app.delete("/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_image(image_id: int, user: User = Depends(role_dependency("admin"))):
    global database
    database = [img for img in database if img.id != image_id]
    return


# Маршрут для додавання тегів під світлину
@app.post("/images/{image_id}/tags", response_model=Image)
def add_tags_to_image(image_id: int, tags: List[str], user: User = Depends(role_dependency("moderator"))):
    image = next((img for img in database if img.id == image_id), None)
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found")
    image.tags += tags
    return image


# Маршрут для створення посилання на трансформовані зображення (Cloudinary URL)
@app.get("/images/{image_id}/view_url/", response_model=str)
def get_image_view_url(image_id: int):
    image = next((img for img in database if img.id == image_id), None)
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found")
    # Код для створення URL трансформованого зображення на Cloudinary тут
    cloudinary_view_url = "https://your-cloudinary-transformed-image-url.com/image.jpg"
    return cloudinary_view_url


# Маршрут для створення QR-коду на основі Cloudinary URL
@app.get("/images/{image_id}/qr_code/", response_model=str)
def get_image_qr_code(image_id: int):
    image = next((img for img in database if img.id == image_id), None)
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found")
    # Ваш код для створення QR-коду на основі Cloudinary URL тут
    qr_code_url = "https://your-qr-code-url.com/qr_code.png"
    return qr_code_url


# Маршрут для перегляду профілю користувача (без редагування)
@app.get("/users/{username}", response_model=User)
def get_user_profile(username: str, current_user: User = Depends(get_current_user)):
    if current_user.username != username:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have enough permissions")

    user = get_user(username=username)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    return user


# Маршрут для редагування інформації про користувача (дозволено тільки для себе)
@app.put("/users/{username}/edit", response_model=User)
def edit_user_profile(username: str, password: str, current_user: User = Depends(get_current_user)):
    if current_user.username != username:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have enough permissions")

    user = get_user(username=username)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    user.password = password  # Оновлення паролю користувача
    return user


# Маршрут для перегляду списку всіх користувачів (дозволено тільки адміністраторам)
@app.get("/users/", response_model=List[User])
def get_all_users(current_user: User = Depends(role_dependency(required_role="admin"))):
    users = [
        user for user in users
        if user.role != "admin"  # Показуємо всіх користувачів, окрім адміністраторів
    ]
    return users


# Маршрут для зміни статусу користувача на неактивний (бан)
@app.put("/users/{username}/ban", response_model=User)
def ban_user(username: str, current_user: User = Depends(role_dependency(required_role="admin"))):
    user = get_user(username=username)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = False
    return user


app.include_router(router)
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
