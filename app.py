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
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, location TEXT, days TEXT, price INTEGER, last_price INTEGER, departure_location TEXT, trip_hash TEXT)''')
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
    c.execute('SELECT * FROM trips ORDER BY price ASC')
    trips = c.fetchall()
    conn.close()
    return render_template('trips.html', trips=trips)


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


# Scrapes the website for holiday offers and loads them into the database
def scrape_and_load_offers():
    print("Starting scraping...")

    urls = [
        'https://r.pl/szukaj?wybraneSkad=KTW&wybraneSkad=KRK&typTransportu=AIR&data=2023-06-24&data=2023-07-30&dorosli=1992-01-01&dorosli=1992-01-01&dzieci=2020-05-23&dzieci=2012-08-22&liczbaPokoi=1&dowolnaLiczbaPokoi=nie&wyzywienia=all-inclusive&wyzywienia=3-posilki&wyzywienia=2-posilki&dlugoscPobytu=*-*&dlugoscPobytu.od=8&dlugoscPobytu.do=&odlegloscLotnisko=*-*&cena=sum&cena.od=&cena.do=&ocenaKlientow=&sortowanie=cena-asc',
        'https://r.pl/szukaj?wybraneSkad=KTW&wybraneSkad=KRK&typTransportu=AIR&data=2023-05-18&data=2023-06-30&dorosli=1992-01-01&dorosli=1992-01-01&dzieci=2020-05-23&dzieci=2012-08-22&liczbaPokoi=1&dowolnaLiczbaPokoi=nie&wyzywienia=all-inclusive&wyzywienia=3-posilki&wyzywienia=2-posilki&dlugoscPobytu=*-*&dlugoscPobytu.od=8&dlugoscPobytu.do=&odlegloscLotnisko=*-*&cena=sum&cena.od=&cena.do=&ocenaKlientow=&sortowanie=cena-asc']
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
            departure_location_element = trip_div.find("span", class_="r-bloczek-przystanki__info")
            departure_location = departure_location_element.previous_sibling.strip() if departure_location_element else ""
            price = re.sub(r'\D', '', price)
            days = days.split(')')[0].strip().replace("(", "- ")

            # Generate trip hash
            trip_hash = hashlib.md5((title + location + days + departure_location).encode('utf-8')).hexdigest()

            # Check if trip already exists in the database
            c.execute('SELECT price FROM trips WHERE trip_hash = ?', (trip_hash,))
            row = c.fetchone()

            if row:
                stored_price = row[0]

                if int(price) != stored_price:
                    # Update the price and set the previous price as the last price
                    c.execute('UPDATE trips SET price = ?, last_price = ? WHERE trip_hash = ?',
                              (int(price), stored_price, trip_hash))
            else:
                # Insert the new trip into the database
                c.execute(
                    'INSERT INTO trips (title, location, days, price, last_price, departure_location, trip_hash) VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (title, location, days, int(price), int(price), departure_location, trip_hash))

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
    app.run(debug=True)
