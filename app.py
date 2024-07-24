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


# Route for displaying trips
@app.route('/trips')
@login_required
def trips():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    country = request.args.get('country', '')
    persons = request.args.get('persons', '')

    query = 'SELECT * FROM trips WHERE 1=1'
    if country:
        query += f' AND location = "{country}"'
    if persons:
        query += f' AND persons = "{persons}"'

    c.execute(query)
    trips = c.fetchall()

    trip_data = []
    for trip in trips:
        trip_id = trip[0]
        trip_hash = trip[9]
        c.execute('SELECT date, price FROM price_history WHERE trip_hash = ? ORDER BY date ASC', (trip_hash,))
        price_history = c.fetchall()
        trip_data.append({
            'id': trip_id,
            'title': trip[1],
            'location': trip[2],
            'days': trip[3],
            'price': trip[4],
            'last_price': trip[5],
            'departure_location': trip[6],
            'food': trip[7],
            'persons': trip[8],
            'trip_hash': trip_hash,
            'trip_url': trip[10],
            'price_history': price_history
        })

    conn.close()
    return render_template('trips.html', trips=trip_data)

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
