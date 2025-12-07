import sqlite3
import json
import requests
import sys
from datetime import datetime
from keys import WEATHER_KEY

# Connect to database
conn = sqlite3.connect('airports.db')
cursor = conn.cursor()

# Create airport_weather_data table if it doesn't exist
# Use airport_id as PRIMARY KEY to match airport_api_data table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS airport_weather_data (
        airport_id INTEGER PRIMARY KEY,
        icao TEXT,
        latitude REAL,
        longitude REAL,
        weather_json TEXT,
        status TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (airport_id) REFERENCES airport_api_data(id)
    )
''')
conn.commit()

# Get airports from airport_api_data that don't have weather data yet
cursor.execute('''
    SELECT 
        a.id,
        a.icao,
        a.api_data_json
    FROM airport_api_data a
    LEFT JOIN airport_weather_data w ON a.id = w.airport_id
    WHERE w.airport_id IS NULL
    LIMIT 25
''')

results = cursor.fetchall()

if not results:
    print("All airports already have weather data!")
    conn.close()
    sys.exit(0)

print(f"Found {len(results)} airports missing weather data")
print(f"Processing next 25 airports...\n")

successful = 0
failed = 0
missing_coords = 0

for idx, (airport_id, icao, api_data_json) in enumerate(results, 1):
    
    latitude = None
    longitude = None
    
    # Extract coordinates from API data
    if api_data_json:
        try:
            api_data = json.loads(api_data_json)
            latitude = api_data.get('latitude_deg')
            longitude = api_data.get('longitude_deg')
        except json.JSONDecodeError:
            pass
    
    if latitude is None or longitude is None:
        missing_coords += 1
        # Still insert record with missing coordinates
        cursor.execute('''
            INSERT OR REPLACE INTO airport_weather_data (airport_id, icao, latitude, longitude, weather_json, status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (airport_id, icao, None, None, None, 'missing_coordinates'))
        continue
    
    # Get current weather (not historical) for the airport
    # Using current.json endpoint for real-time weather
    url = f"https://api.weatherapi.com/v1/current.json?key={WEATHER_KEY}&q={latitude},{longitude}"
    
    weather_json = None
    status = 'success'
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        weather_data = response.json()
        weather_json = json.dumps(weather_data)
        successful += 1
        
        print(f"✓ Airport {idx}/{len(results)} ({icao}): Success")
    except requests.exceptions.HTTPError as e:
        status = f'HTTP {response.status_code}'
        failed += 1
        print(f"✗ Airport {idx}/{len(results)} ({icao}): {status}")
    except requests.exceptions.RequestException as e:
        status = f'Error: {str(e)}'
        failed += 1
        print(f"✗ Airport {idx}/{len(results)} ({icao}): {status}")
    
    # Insert weather data into database (using airport_id as primary key)
    cursor.execute('''
        INSERT OR REPLACE INTO airport_weather_data (airport_id, icao, latitude, longitude, weather_json, status)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (airport_id, icao, latitude, longitude, weather_json, status))

conn.commit()
conn.close()

print(f"\n=== Complete ===")
print(f"Processed: {len(results)} airports")
print(f"Successful: {successful}")
print(f"Failed: {failed}")
print(f"Missing coordinates: {missing_coords}")
print(f"Weather data written to airport_weather_data table in airports.db")
print(f"\nRemaining airports to process. Run again to process next 25 airports.")
print(f"\nTo join with airport_api_data table, use:")
print(f"  SELECT a.*, w.weather_json, w.latitude, w.longitude")
print(f"  FROM airport_api_data a")
print(f"  LEFT JOIN airport_weather_data w ON a.id = w.airport_id")
print(f"\nNote: airport_weather_data.airport_id is the PRIMARY KEY (same as airport_api_data.id)")