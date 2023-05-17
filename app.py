from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import bcrypt

app = Flask(__name__)
app.secret_key = 'SomeSecretKey!1'

# Configure SQLite database
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


def create_database():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    # Create table for users
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, password TEXT)''')

    # Create table for trips
    c.execute('''CREATE TABLE IF NOT EXISTS trips
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, destination TEXT, price INTEGER)''')

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
    c.execute('SELECT * FROM trips')
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
                session['username'] = username  # Store the username in the session
                return redirect(url_for('trips'))  # Redirect to 'trips' endpoint

        return 'Invalid username or password'

    return render_template('index.html')



# Route for loggin out
@app.route('/logout', methods=['GET', 'POST'])
def logout():
    # Clear session data or perform any necessary logout operations
    session.clear()
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)
