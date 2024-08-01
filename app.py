from flask import Flask, render_template, request, redirect, url_for, session
from decorators import login_required
from file_db_utils import create_database, DATABASE
import sqlite3
import bcrypt

from scraper import schedule_scraping

app = Flask(__name__)
app.secret_key = 'SomeSecretKey!1'

create_database()
schedule_scraping()


# Route for the main page
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/charters')
@login_required
def charters():
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM charters ORDER BY date DESC')
        charters = c.fetchall()
    return render_template('charters.html', charters=charters)

@app.route('/charter-changes')
@login_required
def charter_changes():
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute('SELECT trip_hash, date, price FROM charter_price_history ORDER BY date DESC')
        charter_changes = c.fetchall()
    return render_template('charter_changes.html', charter_changes=charter_changes)


@app.route('/price-changes')
def price_changes():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT title, location, date, current_price, previous_price, departure_location, food, persons, change_date FROM price_changes ORDER BY change_date DESC')
    price_changes = c.fetchall()
    conn.close()
    return render_template('price_changes.html', price_changes=price_changes)

# Route for displaying trips
@app.route('/trips')
@login_required
def trips():
    # Retrieve the number of adults, children, and country from the URL query parameters
    persons = request.args.get('persons')
    country = request.args.get('country')

    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()

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
    return render_template('trips.html', trips=trips)

# Route to empty trips db
@app.route('/empty-trips', methods=['GET', 'POST'])
@login_required
def empty_trips():
    if request.method == 'GET':
        with sqlite3.connect(DATABASE) as conn:
            conn.execute('DELETE FROM trips')

        return redirect(url_for('trips'))

    return redirect(url_for('index'))

# Route for user registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        # Hash the password
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        with sqlite3.connect(DATABASE) as conn:
            conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_password))

        return redirect(url_for('index'))

    return render_template('register.html')


# Route for user login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.execute('SELECT password FROM users WHERE username = ?', (username,))
            row = cursor.fetchone()
            if row and bcrypt.checkpw(password.encode('utf-8'), row[0]):
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


# Route for subscribing to trip alerts
@app.route('/subscribe', methods=['GET', 'POST'])
@login_required
def subscribe():
    if request.method == 'POST':
        email = request.form['email']
        price = int(request.form['price'])

        # Save the subscription details in the database
        with sqlite3.connect(DATABASE) as conn:
            conn.execute('INSERT INTO subscriptions (email, desired_price) VALUES (?, ?)', (email, price))

        return redirect(url_for('trips'))

    return render_template('subscribe.html')


# Route for unsubscribing from trip alerts
@app.route('/unsubscribe', methods=['POST'])
@login_required
def unsubscribe():
    email = request.form['email']

    with sqlite3.connect(DATABASE) as conn:
        conn.execute('DELETE FROM subscriptions WHERE email = ?', (email,))

    return redirect(url_for('trips'))


if __name__ == '__main__':
    app.run(debug=True, port=5001)
