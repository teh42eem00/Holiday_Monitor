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
from playwright.sync_api import sync_playwright
from urllib.parse import urljoin

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
                food_element = trip.find("span", class_="r-bloczek-wyzywienie__nazwa")
                if food_element:
                    food = food_element.text.strip()
                else:
                    food = None
                
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
                        c.execute('UPDATE trips SET price = ?, last_price = ?, review_score = ? WHERE trip_hash = ?',
                                  (int(price), int(stored_price), review_score, trip_hash))
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

    charter_url = 'https://biletyczarterowe.r.pl/szukaj?data=2024-08-03&idPrzylot=179487_317769&idWylot=317795&oneWay=false&pakietIdPrzylot=179487_317769&pakietIdWylot=179487_317795&przylotDo&przylotOd&skad%5B%5D=KTW&skad%5B%5D=KRK&wiek%5B%5D=1989-10-30&wiek%5B%5D=1989-10-30&wiek%5B%5D=2020-05-23&wiek%5B%5D=2012-08-22&wylotDo=2024-08-19&wylotOd=2024-08-02'

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(charter_url, timeout=60000)

        # Czekaj na załadowanie treści
        page.wait_for_selector('a.karta.karta', timeout=60000)  # Czekać, aż pojawią się linki do lotów

        # Pobierz treść strony
        content = page.content()
        browser.close()

    soup = BeautifulSoup(content, 'html.parser')
    flights = soup.find_all("a", class_="karta karta")

    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()

        for flight in flights:
            relative_link = flight.get('href')
            if relative_link:
                # Użyj urljoin, aby uzyskać pełny URL
                flight_link = urljoin(charter_url, relative_link)
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    page = browser.new_page()
                    page.goto(flight_link, timeout=60000)

                    # Czekaj na załadowanie treści
                    page.wait_for_selector('div.bilety', timeout=60000)

                    # Pobierz treść strony
                    content = page.content()
                    browser.close()

                card = BeautifulSoup(content, 'html.parser')

                # Znajdź wszystkie informacje o lotach
                flight_infos = card.find_all('div', class_='bilety')

                for flight_info in flight_infos:
                    # Znalezienie daty
                    date_div = flight_info.find('div', class_='termin active')
                    date_header = date_div.find('div', class_='termin__header')
                    date = date_header.get_text(strip=True) if date_header else ""
                    
                    # Informacje o wylocie
                    departure_info = flight_info.find('div', class_='lot-info__col-side')
                    departure_country = departure_info.find('div', class_='panstwo').get_text(strip=True)
                    departure_city = departure_info.find('div', class_='miasto').get_text(strip=True)
                    departure_time = departure_info.find('div', class_='godz tooltip-wrap').get_text(strip=True)

                    # Informacje o przylocie
                    arrival_info = flight_info.find('div', class_='lot-info__col-side right')
                    arrival_country = arrival_info.find('div', class_='panstwo').get_text(strip=True)
                    arrival_city = arrival_info.find('div', class_='miasto').get_text(strip=True)
                    arrival_time = arrival_info.find('div', class_='godz tooltip-wrap').get_text(strip=True)

                    # Cena
                    price_div = flight_info.find('div', class_='karta-lotu__cena')
                    price_text = price_div.get_text(strip=True) if price_div else ""
                    price = int(re.sub(r'\D', '', price_text)) if price_text else None

                    # Generowanie hasha dla lotu
                    flight_string = f"{date} {departure_country} {departure_city} {departure_time} {arrival_country} {arrival_city} {arrival_time}"
                    flight_hash = hashlib.md5(flight_string.encode('utf-8')).hexdigest()

                     # Sprawdzamy, czy lot już istnieje
                    c.execute('SELECT price FROM charters WHERE trip_hash = ?', (flight_hash,))
                    row = c.fetchone()

                    if row:
                        # Jeśli lot istnieje, aktualizuj rekord, jeśli cena się zmieniła
                        stored_price = row[0]
                        if price is not None and price != stored_price:
                            c.execute('UPDATE charters SET price = ?, last_price = ? WHERE trip_hash = ?',
                                      (price, stored_price, flight_hash))
                            c.execute('INSERT INTO charter_price_history (trip_hash, date, price) VALUES (?, ?, ?)',
                                      (flight_hash, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), price))
                    else:
                        # Dodanie nowego rekordu do tabeli `charters`
                        c.execute('INSERT INTO charters (trip_hash, date, departure_country, departure_city, departure_time, arrival_country, arrival_city, arrival_time, flight_url, price, last_price) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                                  (flight_hash, date, departure_country, departure_city, departure_time, arrival_country, arrival_city, arrival_time, flight_link, price, price))
                        
                        # Dodajemy nową cenę do tabeli `charter_price_history`
                        if price is not None:
                            c.execute('INSERT INTO charter_price_history (trip_hash, date, price) VALUES (?, ?, ?)',
                                      (flight_hash, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), price))

    print("Charter scraping completed!")

def schedule_scraping():
    print("Scraping scheduled...")
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(scrape_and_load_offers, trigger=IntervalTrigger(minutes=1))
    scheduler.add_job(scrape_and_load_charters, trigger=IntervalTrigger(minutes=2))
    scheduler.start()

if __name__ == "__main__":
    schedule_scraping()
