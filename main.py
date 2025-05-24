import random
import sqlite3
from contextlib import asynccontextmanager
from typing import List, Dict, Any

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

DB_CONFIG = {
    'table_name': 'users.db'
}


class User(BaseModel):
    gender: str
    first_name: str
    last_name: str
    phone: str
    email: str
    location: str
    picture: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    conn = sqlite3.connect('../users.db')
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM users')
    count = c.fetchone()[0]
    conn.close()

    if count == 0:
        for _ in range(10):
            users = fetch_users_from_api(100)
            save_users_to_db(users)
    yield


app = FastAPI(lifespan=lifespan)


def init_db():
    conn = sqlite3.connect('../users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  gender TEXT,
                  first_name TEXT,
                  last_name TEXT,
                  phone TEXT,
                  email TEXT,
                  location TEXT,
                  picture TEXT)''')
    conn.commit()
    conn.close()


def fetch_users_from_api(count: int = 1) -> List[User]:
    response = requests.get(f'https://randomuser.me/api/?results={count}')
    data = response.json()
    users = []
    for result in data['results']:
        user = User(
            gender=result['gender'],
            first_name=result['name']['first'],
            last_name=result['name']['last'],
            phone=result['phone'],
            email=result['email'],
            location=f"{result['location']['city']}, "
                     f"{result['location']['country']}",
            picture=result['picture']['thumbnail']
        )
        users.append(user)
    return users


def save_users_to_db(users: List[User]):
    conn = sqlite3.connect('../users.db')
    c = conn.cursor()
    for user in users:
        c.execute('''INSERT INTO users (gender, first_name, last_name, 
        phone, email, location, picture)
                     VALUES (?, ?, ?, ?, ?, ?, ?)''',
                  (user.gender, user.first_name, user.last_name, user.phone,
                   user.email, user.location, user.picture))
    conn.commit()
    conn.close()


def get_users_from_db(limit: int = 10, offset: int = 0) -> List[
    Dict[str, Any]]:
    conn = sqlite3.connect(DB_CONFIG['table_name'])
    c = conn.cursor()
    c.execute('''SELECT id, gender, first_name, last_name, phone, email,
     location, picture 
                 FROM users LIMIT ? OFFSET ?''', (limit, offset))
    rows = c.fetchall()
    conn.close()
    return [dict(
        zip(['id', 'gender', 'first_name', 'last_name', 'phone', 'email',
             'location', 'picture'], row))
        for row in rows]


def get_user_by_id(user_id: int) -> Dict[str, Any]:
    conn = sqlite3.connect('../users.db')
    c = conn.cursor()
    c.execute('''SELECT id, gender, first_name, last_name, phone, email,
     location, picture 
                 FROM users WHERE id = ?''', (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return dict(
            zip(['id', 'gender', 'first_name', 'last_name', 'phone', 'email',
                 'location', 'picture'], row))
    return None


def get_random_user() -> Dict[str, Any]:
    conn = sqlite3.connect('../users.db')
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM users')
    count = c.fetchone()[0]
    if count == 0:
        return None
    random_id = random.randint(1, count)
    c.execute('''SELECT id, gender, first_name, last_name, phone, email,
     location, picture 
                 FROM users WHERE id = ?''', (random_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return dict(
            zip(['id', 'gender', 'first_name', 'last_name', 'phone', 'email',
                 'location', 'picture'], row))
    return None


@app.get("/", response_class=HTMLResponse)
async def read_root(limit: int = 10, offset: int = 0):
    users = get_users_from_db(limit, offset)

    table_rows = []
    for user in users:
        table_rows.append(f"""
        <tr>
            <td>{user['gender']}</td>
            <td>{user['first_name']}</td>
            <td>{user['last_name']}</td>
            <td>{user['phone']}</td>
            <td>{user['email']}</td>
            <td>{user['location']}</td>
            <td><img src="{user['picture']}" alt="User photo"></td>
            <td><a href="/{user['id']}">View details</a></td>
        </tr>
        """)

    html_content = f"""
    <html>
        <head>
            <title>Random Users</title>
            <style>
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align:
                 left; }}
                th {{ background-color: #f2f2f2; }}
                img {{ width: 50px; height: 50px; object-fit: cover; }}
            </style>
        </head>
        <body>
            <h1>Random Users</h1>
            <form action="/load" method="get">
                <label for="count">Load more users:</label>
                <input type="number" id="count" name="count" min="1" max="
                1000">
                <button type="submit">Load</button>
            </form>
            <table>
                <thead>
                    <tr>
                        <th>Gender</th>
                        <th>First Name</th>
                        <th>Last Name</th>
                        <th>Phone</th>
                        <th>Email</th>
                        <th>Location</th>
                        <th>Photo</th>
                        <th>Details</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(table_rows)}
                </tbody>
            </table>
            <div>
                <a href="/?limit={limit}&offset={max(0, offset - limit)}">
                Previous</a>
                <a href="/?limit={limit}&offset={offset + limit}">Next</a>
            </div>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.get("/load", response_class=HTMLResponse)
async def load_users(count: int):
    users = fetch_users_from_api(count)
    save_users_to_db(users)

    conn = sqlite3.connect('../users.db')
    c = conn.cursor()
    c.execute("SELECT id FROM users ORDER BY id DESC LIMIT ?", (count,))
    user_ids = [row[0] for row in c.fetchall()]
    conn.close()

    user_ids.sort()
    users.sort(key=lambda u: (u.first_name, u.last_name))

    table_rows = []
    for user_id, user in zip(user_ids, users):
        table_rows.append(f"""
        <tr>
            <td>{user.gender}</td>
            <td>{user.first_name}</td>
            <td>{user.last_name}</td>
            <td>{user.phone}</td>
            <td>{user.email}</td>
            <td>{user.location}</td>
            <td><img src="{user.picture}" alt="User photo" style="width:50px;
            height:50px;object-fit:cover;"></td>
            <td><a href="/{user_id}">View details</a></td>
        </tr>
        """)

    html_content = f"""
    <html>
        <head>
            <title>Loaded Users</title>
            <style>
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align:
                 left; }}
                th {{ background-color: #f2f2f2; }}
                img {{ width: 50px; height: 50px; object-fit: cover;}}
            </style>
        </head>
        <body>
            <h1>Successfully loaded {count} users</h1>
            <a href="/">Back to main page</a>
            <table>
                <thead>
                    <tr>
                        <th>Gender</th>
                        <th>First Name</th>
                        <th>Last Name</th>
                        <th>Phone</th>
                        <th>Email</th>
                        <th>Location</th>
                        <th>Photo</th>
                        <th>Details</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(table_rows)}
                </tbody>
            </table>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.get("/random")
async def get_random():
    user = get_random_user()
    if user is None:
        raise HTTPException(status_code=404, detail="No users in database")
    return user


@app.get("/{user_id}", response_class=HTMLResponse)
async def get_user(user_id: int):
    user = get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    html_content = f"""
    <html>
        <head>
            <title>User Details</title>
            <style>
                table {{ 
                    border-collapse: collapse; 
                    width: 50%;
                    margin: 20px auto;
                }}
                th, td {{ 
                    border: 1px solid #ddd; 
                    padding: 12px; 
                    text-align: left; 
                }}
                th {{ 
                    background-color: #f2f2f2; 
                    width: 30%;
                }}
                .user-header {{
                    text-align: center;
                    font-size: 24px;
                    margin: 20px 0;
                }}
                .photo-cell {{
                    text-align: center;
                }}
                .user-photo {{
                    width: 100px;
                    height: 100px;
                    border-radius: 50%;
                }}
            </style>
        </head>
        <body>
            <div class="user-header">
                {user['first_name']} {user['last_name']}
            </div>
            <table>
                <tr>
                    <th>Gender</th>
                    <td>{user['gender']}</td>
                </tr>
                <tr>
                    <th>Phone</th>
                    <td>{user['phone']}</td>
                </tr>
                <tr>
                    <th>Email</th>
                    <td>{user['email']}</td>
                </tr>
                <tr>
                    <th>Location</th>
                    <td>{user['location']}</td>
                </tr>
                <tr>
                    <th>Photo</th>
                    <td class="photo-cell">
                        <img src="{user['picture']}" alt="User photo" 
                        class="user-photo">
                    </td>
                </tr>
            </table>
            <div style="text-align: center; margin-top: 20px;">
                <a href="/">Back to main page</a>
            </div>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)
