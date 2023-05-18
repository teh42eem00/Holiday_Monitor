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
import yagmail

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


def send_email(subject, content, to_email):
    # Read the sender's email and password from the secrets file
    with open("static/secrets.txt", "r") as secrets_file:
        sender_email = secrets_file.readline().strip()
        sender_password = secrets_file.readline().strip()

    # Create a yagmail instance
    yag = yagmail.SMTP(sender_email, sender_password)

    # Send the email
    yag.send(to=to_email, subject=subject, contents=content)


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

    # Retrieve the number of adults, children, and country from the URL query parameters
    persons = request.args.get('persons')
    country = request.args.get('country')

    if country and persons:
        # Filter trips by country and persons
        if persons == '2+0':
            c.execute(
                'SELECT * FROM trips WHERE location LIKE ? AND persons = "2 adults, 0 children" ORDER BY price ASC',
                ('%' + country + '%',))
        elif persons == '2+2':
            c.execute(
                'SELECT * FROM trips WHERE location LIKE ? AND persons = "2 adults, 2 children" ORDER BY price ASC',
                ('%' + country + '%',))
        else:
            c.execute('SELECT * FROM trips WHERE location LIKE ? ORDER BY price ASC', ('%' + country + '%',))
    elif country:
        # Filter trips by country
        c.execute('SELECT * FROM trips WHERE location LIKE ? ORDER BY price ASC', ('%' + country + '%',))
    elif persons == '2+0':
        c.execute('SELECT * FROM trips WHERE persons = "2 adults, 0 children" ORDER BY price ASC')
    elif persons == '2+2':
        c.execute('SELECT * FROM trips WHERE persons = "2 adults, 2 children" ORDER BY price ASC')
    else:
        c.execute('SELECT * FROM trips ORDER BY price ASC')

    trips = c.fetchall()
    conn.close()

    return render_template('trips.html', trips=trips)


# Route for subscribing to trip alerts
@app.route('/subscribe', methods=['GET', 'POST'])
@login_required
def subscribe():
    if request.method == 'POST':
        email = request.form['email']
        price = int(request.form['price'])

        # Save the subscription details in the database
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('INSERT INTO subscriptions (email, desired_price) VALUES (?, ?)', (email, price))
        conn.commit()
        conn.close()

        return redirect(url_for('trips'))

    return render_template('subscribe.html')


# Route for unsubscribing from trip alerts
@app.route('/unsubscribe', methods=['POST'])
def unsubscribe():
    email = request.form['email']

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('DELETE FROM subscriptions WHERE email = ?', (email,))
    conn.commit()
    conn.close()

    return redirect(url_for('trips'))


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
    c.execute('SELECT * FROM subscriptions')
    subscriptions = c.fetchall()
    c = conn.cursor()

    # Retrieve the existing trip hashes from the database
    c.execute('SELECT trip_hash FROM trips')
    hashes_to_remove = [row[0] for row in c.fetchall()]

    for url in urls:
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')

        trips = soup.findAll("a", class_="n-bloczek szukaj-bloczki__element")
        for trip in trips:
            title = trip.find("span", class_="r-bloczek-tytul").text.strip()
            location = trip.find("span", class_="r-bloczek-lokalizacja").text.strip()
            days = trip.find("div", class_="r-bloczek-wlasciwosc__dni").text.strip().split(')')[0].strip().replace("(",
                                                                                                                   "- ")
            price = trip.find("div", class_="r-bloczek-cena").text.strip()
            departure_location = trip.find("div", class_="r-bloczek-wlasciwosc__dni").find_next('div',
                                                                                                class_='r-bloczek-wlasciwosc').text.strip()
            food = trip.find("span", class_="r-bloczek-wyzywienie__nazwa").text.strip()
            trip_url = "https://r.pl" + trip['href']

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
            trip_hash = hashlib.md5(
                (title + location + days + departure_location + food + persons_formatted).encode('utf-8')).hexdigest()

            # Check if trip already exists in the database
            c.execute('SELECT price FROM trips WHERE trip_hash = ?', (trip_hash,))
            row = c.fetchone()

            if row:
                stored_price = row[0]
                hashes_to_remove.remove(trip_hash)
                if int(price) != stored_price:
                    # Update the price and set the previous price as the last price
                    c.execute('UPDATE trips SET price = ?, last_price = ?, food = ?, persons = ? WHERE trip_hash = ?',
                              (int(price), stored_price, food, persons_formatted, trip_hash))
            else:
                # Insert the new trip into the database
                c.execute(
                    'INSERT INTO trips (title, location, days, price, last_price, departure_location, food, persons, trip_hash, trip_url) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    (title, location, days, int(price), int(price), departure_location, food, persons_formatted,
                     trip_hash, trip_url))

            # Process subscriptions for matching trips
            for subscription in subscriptions:
                email = subscription[1]
                desired_price = subscription[2]

                # Check if the trip matches the subscription criteria and has not been alerted before
                c.execute(
                    'SELECT * FROM subscription_trips WHERE subscription_email = ? AND trip_hash = ? AND trip_price = ?',
                    (email, trip_hash, price))

                row = c.fetchone()

                if int(price) <= desired_price and not row:
                    # Prepare the email content
                    subject = 'Trip Alert: Price Match!'
                    content = f"There is a trip that matches your criteria:\n\nTitle: {title}\nLocation: {location}\nPrice: {price}\n\nYou can book the trip at: {trip_url}"

                    # Send the email
                    send_email(subject, content, email)

                    # Insert the trip hash and price into the subscription_trips table
                    c.execute(
                        'INSERT INTO subscription_trips (subscription_email, trip_hash, trip_price) VALUES (?, ?, ?)',
                        (email, trip_hash, int(price)))

                    # Delete trips with hashes that are not found on the scraped URLs anymore
                    # Uncomment the following code to delete the trips
                    """
                    for hash_to_delete in hashes_to_remove:
                        c.execute('DELETE FROM trips WHERE trip_hash = ?', (hash_to_delete,))
                    """

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
