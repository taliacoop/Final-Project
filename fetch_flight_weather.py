import sqlite3
import json
import requests
import sys
from datetime import datetime
from keys import WEATHER_KEY

# Connect to database
conn = sqlite3.connect('airports.db')
cursor = conn.cursor()

# Create weather_data table if it doesn't exist
# Use flight_id as PRIMARY KEY to match flights table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS weather_data (
        flight_id INTEGER PRIMARY KEY,
        departure_scheduled TEXT,
        latitude REAL,
        longitude REAL,
        date TEXT,
        weather_json TEXT,
        status TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (flight_id) REFERENCES flights(id)
    )
''')
conn.commit()

# Get flights that don't have weather data yet, with their departure info and airport coordinates
cursor.execute('''
    SELECT 
        f.id,
        f.departure_scheduled,
        a.api_data_json
    FROM flights f
    LEFT JOIN airport_api_data a ON f.departure_icao = a.icao
    LEFT JOIN weather_data w ON f.id = w.flight_id
    WHERE f.departure_scheduled IS NOT NULL
    AND w.flight_id IS NULL
    LIMIT 25
''')

results = cursor.fetchall()

if not results:
    print("All flights already have weather data!")
    conn.close()
    sys.exit(0)

print(f"Found {len(results)} flights missing weather data")
print(f"Processing next 25 flights...\n")

successful = 0
failed = 0
missing_coords = 0

for idx, (flight_id, departure_scheduled, api_data_json) in enumerate(results, 1):
    
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
            INSERT OR REPLACE INTO weather_data (flight_id, departure_scheduled, latitude, longitude, date, weather_json, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (flight_id, departure_scheduled, None, None, None, None, 'missing_coordinates'))
        continue
    
    # Extract date from departure_scheduled (format: 2025-12-07T07:05:00+00:00)
    try:
        dt = datetime.fromisoformat(departure_scheduled.replace('Z', '+00:00'))
        date_str = dt.strftime('%Y-%m-%d')
    except:
        date_str = departure_scheduled.split('T')[0] if 'T' in departure_scheduled else departure_scheduled[:10]
    
    # Build API URL
    url = f"https://api.weatherapi.com/v1/history.json?key={WEATHER_KEY}&q={latitude},{longitude}&dt={date_str}"
    
    weather_json = None
    status = 'success'
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        weather_data = response.json()
        weather_json = json.dumps(weather_data)
        successful += 1
        
        print(f"✓ Flight {idx}/{len(results)}: Success")
    except requests.exceptions.HTTPError as e:
        status = f'HTTP {response.status_code}'
        failed += 1
    except requests.exceptions.RequestException as e:
        status = f'Error: {str(e)}'
        failed += 1
    
    # Insert weather data into database (using flight_id as primary key)
    cursor.execute('''
        INSERT OR REPLACE INTO weather_data (flight_id, departure_scheduled, latitude, longitude, date, weather_json, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (flight_id, departure_scheduled, latitude, longitude, date_str, weather_json, status))

conn.commit()
conn.close()

print(f"\n=== Complete ===")
print(f"Processed: {len(results)} flights")
print(f"Successful: {successful}")
print(f"Failed: {failed}")
print(f"Missing coordinates: {missing_coords}")
print(f"Weather data written to weather_data table in airports.db")
print(f"\nRemaining flights to process. Run again to process next 25 flights.")
print(f"\nTo join with flights table, use:")
print(f"  SELECT f.*, w.weather_json, w.latitude, w.longitude")
print(f"  FROM flights f")
print(f"  LEFT JOIN weather_data w ON f.id = w.flight_id")
print(f"\nNote: weather_data.flight_id is the PRIMARY KEY (same as flights.id)")

