import sqlite3

import pytest
from fastapi.testclient import TestClient

from YADRO_test.main import app, User, fetch_users_from_api, get_users_from_db

client = TestClient(app)


@pytest.fixture(scope="module")
def test_db():
    conn = sqlite3.connect("../test.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      gender TEXT,
                      first_name TEXT,
                      last_name TEXT,
                      phone TEXT,
                      email TEXT,
                      location TEXT,
                      picture TEXT)''')
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def test_client():
    with TestClient(app) as client:
        yield client


@pytest.fixture
def mock_user_data():
    return {
        "results": [
            {
                "gender": "male",
                "name": {"first": "John", "last": "Doe"},
                "phone": "123-456-7890",
                "email": "john.doe@example.com",
                "location": {"city": "New York", "country": "USA"},
                "picture": {"thumbnail": "https://example.com/john.jpg"}
            },
            {
                "gender": "female",
                "name": {"first": "Jane", "last": "Smith"},
                "phone": "987-654-3210",
                "email": "jane.smith@example.com",
                "location": {"city": "London", "country": "UK"},
                "picture": {"thumbnail": "https://example.com/jane.jpg"}
            }
        ]
    }


def test_fetch_users_from_api(mocker, mock_user_data):
    mock_get = mocker.patch('requests.get')
    mock_response = mock_get.return_value
    mock_response.json.return_value = mock_user_data

    users = fetch_users_from_api(2)

    assert len(users) == 2
    assert isinstance(users[0], User)
    assert users[0].first_name == "John"
    assert users[1].email == "jane.smith@example.com"
    mock_get.assert_called_once_with("https://randomuser.me/api/?results=2")


def test_save_and_get_users_from_db(mocker, test_db):
    mocker.patch.dict('main.DB_CONFIG', {'table_name': 'test_db'})
    test_users = [
        User(
            gender="male",
            first_name="Test",
            last_name="User1",
            phone="111-111-1111",
            email="test1@example.com",
            location="Test City, Test Country",
            picture="https://example.com/test1.jpg"
        ),
        User(
            gender="female",
            first_name="Test",
            last_name="User2",
            phone="222-222-2222",
            email="test2@example.com",
            location="Test City, Test Country",
            picture="https://example.com/test2.jpg"
        )
    ]

    cursor = test_db.cursor()
    for user in test_users:
        cursor.execute('''INSERT INTO users (gender, first_name, last_name,
         phone, email, location, picture)
                         VALUES (?, ?, ?, ?, ?, ?, ?)''',
                       (user.gender, user.first_name, user.last_name,
                        user.phone,
                        user.email, user.location, user.picture))
    test_db.commit()

    users = get_users_from_db(limit=2)

    assert len(users) == 2
    assert users[0]['first_name'] == "Test"
    assert users[1]['email'] == "test2@example.com"


def test_get_random_endpoint(test_client, mocker):
    mock_user = {
        "id": 1,
        "gender": "male",
        "first_name": "Random",
        "last_name": "User",
        "phone": "111-222-3333",
        "email": "random@example.com",
        "location": "Random City",
        "picture": "random.jpg"
    }
    mocker.patch('main.get_random_user').return_value = mock_user

    response = test_client.get("/random")

    assert response.status_code == 200
    assert response.json() == mock_user


def test_get_user_details_endpoint(test_client, mocker):
    mock_user = {
        "id": 1,
        "gender": "male",
        "first_name": "Detail",
        "last_name": "User",
        "phone": "444-555-6666",
        "email": "detail@example.com",
        "location": "Detail City",
        "picture": "detail.jpg"
    }
    mocker.patch('main.get_user_by_id').return_value = mock_user

    response = test_client.get("/1")

    assert response.status_code == 200
    assert "Detail User" in response.text
    assert "detail@example.com" in response.text
    assert "<img src=\"detail.jpg\"" in response.text


def test_get_user_details_not_found(test_client, mocker):
    mocker.patch('main.get_user_by_id').return_value = None

    response = test_client.get("/999")

    assert response.status_code == 404
    assert "User not found" in response.text
