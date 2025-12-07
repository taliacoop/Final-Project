import sqlite3
import requests
import json
import sys
from keys import AIRPORT_KEY

'''
##### Run this Second #####
'''

# Connect to database
conn = sqlite3.connect('airports.db')
cursor = conn.cursor()

# Create table for airport API data
cursor.execute('''
    CREATE TABLE IF NOT EXISTS airport_api_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        icao TEXT UNIQUE,
        api_data_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')
conn.commit()

# Get all departure_icao values from flights table
cursor.execute('SELECT departure_icao FROM flights WHERE departure_icao IS NOT NULL AND departure_icao != ""')
departure_icaos = [row[0] for row in cursor.fetchall()]

# Get all arrival_icao values from flights table
cursor.execute('SELECT arrival_icao FROM flights WHERE arrival_icao IS NOT NULL AND arrival_icao != ""')
arrival_icaos = [row[0] for row in cursor.fetchall()]

# Combine lists and get unique ICAO codes
all_icaos = list(set(departure_icaos + arrival_icaos))

# Get ICAO codes that already exist in the database
cursor.execute('SELECT icao FROM airport_api_data')
existing_icaos = {row[0] for row in cursor.fetchall()}

# Filter to only missing ICAO codes
missing_icaos = [icao for icao in all_icaos if icao not in existing_icaos]

print(f"Found {len(all_icaos)} total unique ICAO codes")
print(f"Already in database: {len(existing_icaos)}")
print(f"Missing: {len(missing_icaos)}")
print(f"Processing next 25 missing ICAO codes...\n")

# Limit to 25 calls per run
icaos_to_process = missing_icaos[:25]

if not icaos_to_process:
    print("All ICAO codes have been processed!")
    conn.close()
    sys.exit(0)

successful = 0
failed = 0

# Call API for each ICAO code
for icao in icaos_to_process:
    url = f"https://airportdb.io/api/v1/airport/{icao}?apiToken={AIRPORT_KEY}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Save to database
        api_data_json = json.dumps(data)
        cursor.execute('''
            INSERT OR REPLACE INTO airport_api_data (icao, api_data_json)
            VALUES (?, ?)
        ''', (icao, api_data_json))
        conn.commit()
        
        print(f"✓ {icao}: Success - saved to database")
        successful += 1
    except requests.exceptions.HTTPError as e:
        print(f"✗ {icao}: HTTP {response.status_code}")
        failed += 1
    except requests.exceptions.RequestException as e:
        print(f"✗ {icao}: {e}")
        failed += 1

conn.close()

print(f"\nCompleted API calls for {len(icaos_to_process)} ICAO codes")
print(f"Successful: {successful}, Failed: {failed}")
print(f"Remaining to process: {len(missing_icaos) - len(icaos_to_process)}")
