import sqlite3
import pickle

def init_db():
    conn = sqlite3.connect('appointments.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS clients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    surname TEXT,
                    address TEXT,
                    phone TEXT,
                    email TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS appointments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id INTEGER,
                    date TEXT NOT NULL,
                    time TEXT NOT NULL,
                    description TEXT,
                    google_event_id TEXT,
                    FOREIGN KEY(client_id) REFERENCES clients(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS diets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id INTEGER,
                    date TEXT NOT NULL,
                    diet TEXT,
                    FOREIGN KEY(client_id) REFERENCES clients(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL,
                    token BLOB NOT NULL)''')
    conn.commit()
    conn.close()

def get_stored_session():
    conn = sqlite3.connect('appointments.db')
    c = conn.cursor()
    c.execute('SELECT email, token FROM sessions ORDER BY id DESC LIMIT 1')
    session = c.fetchone()
    conn.close()
    if session:
        email, token = session
        return email, pickle.loads(token)
    return None

def store_session(email, creds):
    conn = sqlite3.connect('appointments.db')
    c = conn.cursor()
    c.execute('DELETE FROM sessions')  # Solo guardamos una sesión a la vez
    c.execute('INSERT INTO sessions (email, token) VALUES (?, ?)', (email, pickle.dumps(creds)))
    conn.commit()
    conn.close()

def clear_session():
    conn = sqlite3.connect('appointments.db')
    c = conn.cursor()
    c.execute('DELETE FROM sessions')
    conn.commit()
    conn.close()
