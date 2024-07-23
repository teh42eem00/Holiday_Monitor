import sqlite3

DATABASE = 'database.db'


# Create DB
def create_database():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS trips
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, location TEXT, days TEXT, price INTEGER, last_price INTEGER, departure_location TEXT, food TEXT, persons TEXT, trip_hash TEXT, trip_url TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS subscriptions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, desired_price INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS subscription_trips
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, subscription_email TEXT, trip_hash TEXT, trip_price INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS price_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, trip_hash TEXT, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, price INTEGER)''')
    conn.commit()
    conn.close()

# Function to load URLs to scrape from file
def load_urls_from_file():
    with open("static/urls.txt", "r") as file:
        return [line.strip() for line in file]
