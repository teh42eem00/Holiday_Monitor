from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session
from bs4 import BeautifulSoup
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import hashlib
import re
import sqlite3
import bcrypt
import requests

app = Flask(__name__)
app.secret_key = 'SomeSecretKey!1'
DATABASE = 'database.db'


# Custom decorator to check if the user is authenticated
def login_required(route_function):
    @wraps(route_function)
    def wrapper(*args, **kwargs):
        if 'username' in session:
            return route_function(*args, **kwargs)
        else:
            return redirect(url_for('login'))

    return wrapper


# Create DB
def create_database():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS trips
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, location TEXT, days TEXT, price INTEGER, last_price INTEGER, departure_location TEXT, food TEXT, persons TEXT, trip_hash TEXT)''')
    conn.commit()
    conn.close()


create_database()


# Route for the main page
@app.route('/')
def index():
    return render_template('index.html')


# Route for displaying trips
@app.route('/trips')
@login_required
def trips():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    # Retrieve the number of adults and children from the URL query parameters
    adults = int(request.args.get('adults', 0))
    children = int(request.args.get('children', 0))

    if adults == 2 and children == 0:
        c.execute('SELECT * FROM trips WHERE persons = "2 adults, 0 children"')
    elif adults == 2 and children == 2:
        c.execute('SELECT * FROM trips WHERE persons = "2 adults, 2 children"')
    else:
        c.execute('SELECT * FROM trips ORDER BY price ASC')

    trips = c.fetchall()
    conn.close()

    return render_template('trips.html', trips=trips, adults=adults, children=children)



# Route for user registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Hash the password
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_password))
        conn.commit()
        conn.close()

        return redirect(url_for('index'))

    return render_template('register.html')


# Route for user login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT password FROM users WHERE username = ?', (username,))
        row = c.fetchone()
        conn.close()

        if row:
            stored_password = row[0]

            if bcrypt.checkpw(password.encode('utf-8'), stored_password):
                session['username'] = username
                return redirect(url_for('trips'))

        return 'Invalid username or password'

    return render_template('index.html')


# Route for logging out
@app.route('/logout', methods=['GET', 'POST'])
def logout():
    # Clear session data or perform any necessary logout operations
    session.clear()
    return redirect(url_for('login'))


def load_urls_from_file():
    with open("static/urls.txt", "r") as file:
        return [line.strip() for line in file]


# Scrapes the website for holiday offers and loads them into the database
def scrape_and_load_offers():
    print("Starting scraping...")

    urls = load_urls_from_file()
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    for url in urls:
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')

        trip_divs = soup.findAll("div", class_="r-card__body")
        for trip_div in trip_divs:
            title = trip_div.find("span", class_="r-bloczek-tytul").text.strip()
            location = trip_div.find("span", class_="r-bloczek-lokalizacja").text.strip()
            days = trip_div.find("div", class_="r-bloczek-wlasciwosc__dni").text.strip()
            price = trip_div.find("div", class_="r-bloczek-cena").text.strip()
            departure_location = trip_div.find("span",
                                               class_="r-typography r-typography--secondary r-typography--normal r-typography--black r-typography__caption").text.strip()
            food = trip_div.find("span", class_="r-bloczek-wyzywienie__nazwa").text.strip()

            adults_count, children_count = 0, 0
            # Extracting the number of adults and children from the URL
            if "dorosli" in url:
                adults_count = url.count("dorosli")
            if "dzieci" in url:
                children_count = url.count("dzieci")

            # Calculate the formatted persons string
            persons_formatted = f"{adults_count} adults, {children_count} children"

            # Clean and format the price
            price = re.sub(r'\D', '', price)

            # Generate trip hash
            trip_hash = hashlib.md5((title + location + days + departure_location).encode('utf-8')).hexdigest()

            # Check if trip already exists in the database
            c.execute('SELECT price FROM trips WHERE trip_hash = ?', (trip_hash,))
            row = c.fetchone()

            if row:
                stored_price = row[0]

                if int(price) != stored_price:
                    # Update the price and set the previous price as the last price
                    c.execute('UPDATE trips SET price = ?, last_price = ?, food = ?, persons = ? WHERE trip_hash = ?',
                              (int(price), stored_price, food, persons_formatted, trip_hash))
            else:
                # Insert the new trip into the database
                c.execute(
                    'INSERT INTO trips (title, location, days, price, last_price, departure_location, food, persons, trip_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    (title, location, days, int(price), int(price), departure_location, food, persons_formatted,
                     trip_hash))

    conn.commit()
    conn.close()

    print("Scraping completed!")


def schedule_scraping():
    with app.app_context():
        print("Scraping scheduled...")
        scheduler = BackgroundScheduler(daemon=True)
        scheduler.add_job(scrape_and_load_offers, trigger=IntervalTrigger(minutes=1))
        scheduler.start()


schedule_scraping()

if __name__ == '__main__':
    app.run(debug=True, port=5001)
