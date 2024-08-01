import sqlite3

DATABASE = 'database.db'

def create_database():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS trips
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, location TEXT, days TEXT, price INTEGER, last_price INTEGER, departure_location TEXT, food TEXT, persons TEXT, review_score TEXT, trip_hash TEXT, trip_url TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS subscriptions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, desired_price INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS subscription_trips
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, subscription_email TEXT, trip_hash TEXT, trip_price INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS price_changes
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, trip_hash TEXT, title TEXT, location TEXT, date TEXT, current_price INTEGER, previous_price INTEGER, departure_location TEXT, food TEXT, persons TEXT, change_date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS charters
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, trip_hash TEXT, date TEXT, price INTEGER, last_price INTEGER, departure_country TEXT, departure_city TEXT, departure_time TEXT, arrival_country TEXT, arrival_city TEXT, arrival_time TEXT, flight_url TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS charter_price_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, trip_hash TEXT, date TEXT, price INTEGER)''')
    conn.commit()
    conn.close()

def load_urls_from_file():
    with open("static/urls.txt", "r") as file:
        return [line.strip() for line in file]
