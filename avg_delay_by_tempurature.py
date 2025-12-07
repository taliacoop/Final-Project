import sqlite3
import csv
import json

# Connect to database
conn = sqlite3.connect('airports.db')
cursor = conn.cursor()

# Get flights with departure delay and temperature
cursor.execute('''
    SELECT 
        f.departure_delay,
        w.weather_json
    FROM flights f
    LEFT JOIN airport_api_data a ON f.departure_icao = a.icao
    LEFT JOIN airport_weather_data w ON a.id = w.airport_id
    WHERE f.departure_delay IS NOT NULL
    AND f.departure_delay != ''
    AND w.weather_json IS NOT NULL
''')

results = cursor.fetchall()
conn.close()

# Process data: group by temperature range and calculate averages
temperature_delays = {}

for departure_delay, weather_json in results:
    # Parse delay
    try:
        delay = int(departure_delay) if departure_delay and str(departure_delay).strip() else 0
    except (ValueError, TypeError):
        continue
    
    # Extract temperature from weather JSON
    try:
        weather_data = json.loads(weather_json)
        temp_c = weather_data.get('current', {}).get('temp_c')
        if temp_c is None:
            continue
        # Round to nearest 5 degrees for grouping
        temp_range = int(round(temp_c / 5) * 5)
        temp_label = f"{temp_range}°C"
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        continue
    
    # Group by temperature range
    if temp_label not in temperature_delays:
        temperature_delays[temp_label] = []
    temperature_delays[temp_label].append(delay)

# Calculate averages
averages = []
for temp_label, delays in temperature_delays.items():
    avg_delay = sum(delays) / len(delays)
    averages.append({
        'temperature': temp_label,
        'average_delay': round(avg_delay, 2),
        'flight_count': len(delays)
    })

# Sort by temperature
averages.sort(key=lambda x: int(x['temperature'].replace('°C', '')))

# Write to CSV
output_file = 'avg_delay_by_temperature.csv'
with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=['temperature', 'average_delay', 'flight_count'])
    writer.writeheader()
    writer.writerows(averages)

print(f"=== Average Departure Delay by Temperature ===")
print(f"Total flights analyzed: {len(results)}")
print(f"Temperature ranges: {len(averages)}")
print(f"\nResults written to {output_file}")
print(f"\nTemperature ranges with highest delays:")
for item in sorted(averages, key=lambda x: x['average_delay'], reverse=True)[:5]:
    print(f"  {item['temperature']}: {item['average_delay']} minutes ({item['flight_count']} flights)")

