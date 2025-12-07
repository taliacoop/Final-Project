import sqlite3
import csv
import json

# Connect to database
conn = sqlite3.connect('airports.db')
cursor = conn.cursor()

# Get flights with departure delay and weather condition
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

# Process data: group by condition and calculate averages
condition_delays = {}

for departure_delay, weather_json in results:
    # Parse delay
    try:
        delay = int(departure_delay) if departure_delay and str(departure_delay).strip() else 0
    except (ValueError, TypeError):
        continue
    
    # Extract condition from weather JSON
    try:
        weather_data = json.loads(weather_json)
        condition = weather_data.get('current', {}).get('condition', {}).get('text')
        if not condition:
            continue
    except (json.JSONDecodeError, KeyError, TypeError):
        continue
    
    # Group by condition
    if condition not in condition_delays:
        condition_delays[condition] = []
    condition_delays[condition].append(delay)

# Calculate averages
averages = []
for condition, delays in condition_delays.items():
    avg_delay = sum(delays) / len(delays)
    averages.append({
        'condition': condition,
        'average_delay': round(avg_delay, 2),
        'flight_count': len(delays)
    })

# Sort by average delay (descending)
averages.sort(key=lambda x: x['average_delay'], reverse=True)

# Write to CSV
output_file = 'avg_delay_by_condition.csv'
with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=['condition', 'average_delay', 'flight_count'])
    writer.writeheader()
    writer.writerows(averages)

print(f"=== Average Departure Delay by Weather Condition ===")
print(f"Total flights analyzed: {len(results)}")
print(f"Unique conditions: {len(averages)}")
print(f"\nResults written to {output_file}")
print(f"\nTop 5 conditions by average delay:")
for i, item in enumerate(averages[:5], 1):
    print(f"  {i}. {item['condition']}: {item['average_delay']} minutes ({item['flight_count']} flights)")

