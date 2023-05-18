from functools import wraps
from flask import redirect, url_for, session


# Custom decorator to check if the user is authenticated
def login_required(route_function):
    @wraps(route_function)
    def wrapper(*args, **kwargs):
        if 'username' in session:
            return route_function(*args, **kwargs)
        else:
            return redirect(url_for('login'))

    return wrapper
