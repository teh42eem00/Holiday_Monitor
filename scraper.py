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
                
                # Extract review score
                review_score_tag = trip.find("span", class_="r-typography--bold")
                review_score = review_score_tag.text.strip() if review_score_tag else "N/A"

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
                        c.execute('UPDATE trips SET price = ?, last_price = ?, food = ?, persons = ?, review_score = ? WHERE trip_hash = ?',
                                  (int(price), int(stored_price), food, persons_formatted, review_score, trip_hash))
                        c.execute('INSERT INTO price_changes (trip_hash, title, location, date, current_price, previous_price, departure_location, food, persons, change_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                                  (trip_hash, title, location, days, int(price), int(stored_price), departure_location, food, persons_formatted, datetime.now()))

                else:
                    c.execute(
                        'INSERT INTO trips (title, location, days, price, last_price, departure_location, food, persons, review_score, trip_hash, trip_url) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                        (title, location, days, int(price), int(price), departure_location, food, persons_formatted, review_score, trip_hash, trip_url))

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

def scrape_and_load_charters():
    print("Starting charter scraping...")

    charter_url = 'https://biletyczarterowe.r.pl/szukaj?data=2024-08-18&idPrzylot=198243_319679&idWylot=319696&oneWay=false&pakietIdPrzylot=198243_319679&pakietIdWylot=198243_319696&przylotDo&przylotOd&wiek%5B%5D=1989-10-30&wiek%5B%5D=1989-10-30&wiek%5B%5D=2020-05-23&wiek%5B%5D=2012-08-22&wylotDo=2024-08-19&wylotOd=2024-08-02'  # Zmień ten URL na odpowiedni adres URL
    response = requests.get(charter_url)
    soup = BeautifulSoup(response.content, 'html.parser')
    flights = soup.find_all('a', class_='karta karta')
    flight_links = [flight['href'] for flight in flights]
    flights_data = []
    for flight in flight_links:
        site = requests.get(charter_url)
        card = BeautifulSoup(site, 'html.parser')
        flight_info = {}

        # Znalezienie daty, państwa, miasta i godziny
        date_div = card.find('div', class_='termin active')
        if date_div:
            flight_info['date'] = date_div.get_text(strip=True)

        # Informacje o wylocie
        departure = card.find_all('div', class_='lot-info__col-side')[0]
        flight_info['departure_country'] = departure.find('div', class_='panstwo').get_text(strip=True)
        flight_info['departure_city'] = departure.find('div', class_='miasto').get_text(strip=True)
        flight_info['departure_time'] = departure.find_all('div', class_='godz tooltip-wrap')[0].get_text(strip=True)

        # Informacje o przylocie
        arrival = card.find_all('div', class_='lot-info__col-side')[1]
        flight_info['arrival_country'] = arrival.find('div', class_='panstwo').get_text(strip=True)
        flight_info['arrival_city'] = arrival.find('div', class_='miasto').get_text(strip=True)
        flight_info['arrival_time'] = arrival.find_all('div', class_='godz tooltip-wrap')[0].get_text(strip=True)

        # Cena
        price_div = card.find('div', class_='karta-lotu__cena')
        if price_div:
            flight_info['price'] = price_div.get_text(strip=True)

        flights_data.append(flight_info)
    print(flights_data)
    


def schedule_scraping():
    print("Scraping scheduled...")
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(scrape_and_load_offers, trigger=IntervalTrigger(minutes=1))
    scheduler.start()
