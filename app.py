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

def sort_order_toggle(current_sort_by):
    sort_by = request.args.get('sort_by', 'price')
    sort_order = request.args.get('sort_order', 'ASC')
    if sort_by == current_sort_by:
        return 'DESC' if sort_order == 'ASC' else 'ASC'
    return 'ASC'

# Route for the main page
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/charters')
@login_required
def charters():
    sort_by = request.args.get('sort_by', 'date')  # Domyślnie sortuj po dacie
    sort_order = request.args.get('sort_order', 'DESC')  # Domyślnie sortuj malejąco

    valid_columns = ['date', 'price', 'last_price', 'departure_country', 'departure_city', 'departure_time', 'arrival_country', 'arrival_city', 'arrival_time']
    if sort_by not in valid_columns:
        sort_by = 'date'
    if sort_order not in ['ASC', 'DESC']:
        sort_order = 'DESC'

    query = f'SELECT * FROM charters ORDER BY {sort_by} {sort_order}'
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute(query)
        charters = c.fetchall()
    return render_template('charters.html', charters=charters, sort_by=sort_by, sort_order=sort_order)

@app.route('/charter-changes')
@login_required
def charter_changes():
    query = """
    SELECT
        ch.trip_hash,
        ch.date AS flight_date,
        ch.departure_country,
        ch.departure_city,
        ch.departure_time,
        ch.arrival_country,
        ch.arrival_city,
        ch.arrival_time,
        cph.date AS change_date,
        cph.price AS new_price,
        ch.last_price AS previous_price
    FROM
        charter_price_history cph
    JOIN
        charters ch
    ON
        cph.trip_hash = ch.trip_hash
    ORDER BY
        cph.date DESC;
    """
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute(query)
        changes = c.fetchall()

    return render_template('charter_changes.html', changes=changes)

@app.route('/price-changes')
@login_required
def price_changes():
    query = """
    SELECT
        title, location, date, current_price, previous_price,
        departure_location, food, persons, change_date
    FROM
        price_changes
    ORDER BY
        change_date DESC
    """
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute(query)
        price_changes = c.fetchall()

    return render_template('price_changes.html', price_changes=price_changes)

# Route for displaying trips
@app.route('/trips')
@login_required
def trips():
    sort_by = request.args.get('sort_by', 'price')
    sort_order = request.args.get('sort_order', 'ASC')

    valid_columns = {
        'title': 'title',
        'location': 'location',
        'days': 'days',
        'price': 'price',
        'last_price': 'last_price',
        'departure_location': 'departure_location',
        'food': 'food',
        'persons': 'persons',
        'review_score': 'review_score'
    }

    if sort_by not in valid_columns:
        sort_by = 'price'
    if sort_order not in ['ASC', 'DESC']:
        sort_order = 'ASC'

    query = f'SELECT * FROM trips ORDER BY {valid_columns[sort_by]} {sort_order}'

    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute(query)
        trips = c.fetchall()

    return render_template('trips.html', trips=trips, sort_by=sort_by, sort_order=sort_order)
    
# Route to empty trips db
@app.route('/empty-trips', methods=['GET', 'POST'])
@login_required
def empty_trips():
    if request.method == 'GET':
        with sqlite3.connect(DATABASE) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM trips')
            conn.commit()
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
            c = conn.cursor()
            c.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_password))
            conn.commit()

        return redirect(url_for('index'))

    return render_template('register.html')


# Route for user login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        with sqlite3.connect(DATABASE) as conn:
            c = conn.cursor()
            c.execute('SELECT password FROM users WHERE username = ?', (username,))
            row = c.fetchone()
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
            c = conn.cursor()
            c.execute('INSERT INTO subscriptions (email, desired_price) VALUES (?, ?)', (email, price))
            conn.commit()

        return redirect(url_for('trips'))

    return render_template('subscribe.html')


# Route for unsubscribing from trip alerts
@app.route('/unsubscribe', methods=['POST'])
@login_required
def unsubscribe():
    email = request.form['email']

    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute('DELETE FROM subscriptions WHERE email = ?', (email,))
        conn.commit()

    return redirect(url_for('trips'))


if __name__ == '__main__':
    app.run(debug=True, port=5001)
