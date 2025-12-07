import sqlite3
import csv

# Connect to database
conn = sqlite3.connect('airports.db')
cursor = conn.cursor()

# Get flights with departure delay and airport ICAO
cursor.execute('''
    SELECT 
        f.departure_icao,
        f.departure_delay
    FROM flights f
    WHERE f.departure_icao IS NOT NULL
    AND f.departure_icao != ''
    AND f.departure_delay IS NOT NULL
    AND f.departure_delay != ''
''')

results = cursor.fetchall()
conn.close()

# Process data: group by airport and calculate averages
airport_delays = {}

for departure_icao, departure_delay in results:
    # Parse delay
    try:
        delay = int(departure_delay) if departure_delay and str(departure_delay).strip() else 0
    except (ValueError, TypeError):
        continue
    
    # Group by airport
    if departure_icao not in airport_delays:
        airport_delays[departure_icao] = []
    airport_delays[departure_icao].append(delay)

# Calculate averages
averages = []
for icao, delays in airport_delays.items():
    avg_delay = sum(delays) / len(delays)
    averages.append({
        'airport_icao': icao,
        'average_delay': round(avg_delay, 2),
        'flight_count': len(delays)
    })

# Sort by average delay (descending)
averages.sort(key=lambda x: x['average_delay'], reverse=True)

# Write to CSV
output_file = 'avg_delay_by_airport.csv'
with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=['airport_icao', 'average_delay', 'flight_count'])
    writer.writeheader()
    writer.writerows(averages)

print(f"=== Average Departure Delay by Airport ===")
print(f"Total flights analyzed: {len(results)}")
print(f"Unique airports: {len(averages)}")
print(f"\nResults written to {output_file}")
print(f"\nTop 10 airports by average delay:")
for i, item in enumerate(averages[:10], 1):
    print(f"  {i}. {item['airport_icao']}: {item['average_delay']} minutes ({item['flight_count']} flights)")

