import csv
from random import choice, uniform, randint
from datetime import datetime, timedelta

states = ["Andhra Pradesh","Karnataka","Telangana","Maharashtra","Tamil Nadu"]
districts = ["Visakhapatnam","Hyderabad","Bengaluru","Pune","Chennai"]
markets = ["Main Market","Wholesale Yard","Central Mandai","Local Market"]
crops = ["Tomato","Onion","Potato","Rice","Wheat"]

with open("mock_prices.csv", "w", newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(["state","district","market","crop","date","price","unit"])
    for _ in range(1000):
        state = choice(states)
        district = choice(districts)
        market = choice(markets)
        crop = choice(crops)
        days_ago = randint(0, 365)
        dt = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        price = round(uniform(8.0, 60.0), 2)
        unit = "kg"
        writer.writerow([state, district, market, crop, dt, price, unit])
print("mock_prices.csv generated")