import sqlite3
import requests
from bs4 import BeautifulSoup
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from email_utils import send_email
from file_db_utils import load_urls_from_file, DATABASE
import hashlib
import re
from datetime import datetime

def scrape_and_load_offers():
    print("Starting scraping...")

    urls = load_urls_from_file()
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM subscriptions')
        subscriptions = c.fetchall()

        for url in urls:
            response = requests.get(url)
            soup = BeautifulSoup(response.content, 'html.parser')

            trips = soup.findAll("a", class_="n-bloczek szukaj-bloczki__element")
            for trip in trips:
                title = trip.find("span", class_="r-bloczek-tytul").text.strip()
                location = trip.find("span", class_="r-bloczek-lokalizacja").text.strip()
                days = trip.find("div", class_="r-bloczek-wlasciwosci__dni").text.strip().split(')')[0].strip().replace("(", "- ")
                price = trip.find("span", class_="r-bloczek-cena__aktualna").text.strip()
                departure_location = trip.find("div", class_="r-bloczek-wlasciwosci__dni").find_next('div', class_='r-bloczek-wlasciwosci__wlasciwosc').text.strip()
                food = trip.find("span", class_="r-bloczek-wyzywienie__nazwa").text.strip()

                href = trip['href']
                if not href.startswith("http"):
                    trip_url = "https://r.pl" + href
                else:
                    trip_url = href

                adults_count, children_count = 0, 0
                if "dorosli" in url:
                    adults_count = url.count("dorosli")
                if "dzieci" in url:
                    children_count = url.count("dzieci")

                persons_formatted = f"{adults_count} adults, {children_count} children"
                price = re.sub(r'\D', '', price)

                trip_hash = hashlib.md5((title + location + days + departure_location + food + persons_formatted).encode('utf-8')).hexdigest()

                c.execute('SELECT price FROM trips WHERE trip_hash = ?', (trip_hash,))
                row = c.fetchone()

                if row:
                    stored_price = row[0]
                    if int(price) != stored_price:
                        c.execute('UPDATE trips SET price = ?, last_price = ?, food = ?, persons = ? WHERE trip_hash = ?',
                                  (int(price), int(stored_price), food, persons_formatted, trip_hash))
                        c.execute('INSERT INTO price_changes (trip_hash, title, location, date, current_price, previous_price, departure_location, food, persons, change_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                                  (trip_hash, title, location, days, int(price), int(stored_price), departure_location, food, persons_formatted, datetime.now()))

                else:
                    c.execute(
                        'INSERT INTO trips (title, location, days, price, last_price, departure_location, food, persons, trip_hash, trip_url) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                        (title, location, days, int(price), int(price), departure_location, food, persons_formatted, trip_hash, trip_url))

                for subscription in subscriptions:
                    email = subscription[1]
                    desired_price = subscription[2]
                    c.execute('SELECT * FROM subscription_trips WHERE subscription_email = ? AND trip_hash = ? AND trip_price = ?',
                              (email, trip_hash, price))

                    row = c.fetchone()

                    if int(price) <= desired_price and not row:
                        subject = 'Trip Alert: Price Match!'
                        content = f"There is a trip that matches your criteria:\n\nTitle: {title}\nLocation: {location}\nPrice: {price}\n\nYou can book the trip at: {trip_url}"

                        send_email(subject, content, email)
                        c.execute('INSERT INTO subscription_trips (subscription_email, trip_hash, trip_price) VALUES (?, ?, ?)',
                                  (email, trip_hash, int(price)))

    print("Scraping completed!")


def schedule_scraping():
    print("Scraping scheduled...")
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(scrape_and_load_offers, trigger=IntervalTrigger(minutes=1))
    scheduler.start()
