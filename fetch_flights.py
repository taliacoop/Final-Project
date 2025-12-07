"""
Script to fetch flight data from AviationStack API and store it in CSV.
Pulls real-time flight information and exports to CSV file.
"""

import requests
import csv
import json
import sqlite3
from typing import List, Dict, Optional
from keys import AVIATIONSTACK_KEY

'''
##### Run this First #####
'''


class FlightDataFetcher:
    """Fetches flight data from AviationStack API"""
    
    def __init__(self, api_key: str, db_filename: str = 'airports.db'):
        self.api_key = api_key
        self.base_url = "https://api.aviationstack.com/v1/flights"
        self.db_filename = db_filename
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.flights = []
        self.errors = []
    
    def fetch_flights(self, limit: int = 100, offset: int = 0, **kwargs) -> Optional[Dict]:
        """Fetch flight data from AviationStack API"""
        params = {
            'access_key': self.api_key,
            'limit': limit,
            'offset': offset,
            **kwargs  # Allow additional parameters like flight_status, dep_iata, arr_iata, etc.
        }
        
        try:
            response = self.session.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # Check for API errors
            if 'error' in data:
                error_info = data.get('error', {})
                error_msg = error_info.get('info', 'Unknown error')
                print(f"API Error: {error_msg}")
                self.errors.append({'offset': offset, 'error': error_msg})
                return None
            
            return data
        except requests.exceptions.HTTPError as e:
            print(f"HTTP error: {e}")
            self.errors.append({'offset': offset, 'error': f'HTTP {response.status_code}'})
            return None
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            self.errors.append({'offset': offset, 'error': str(e)})
            return None
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            self.errors.append({'offset': offset, 'error': 'Invalid JSON response'})
            return None
    
    def _is_delayed(self, dep_delay, arr_delay) -> bool:
        """Helper method to check if a flight is delayed"""
        try:
            dep_delay_int = int(dep_delay) if dep_delay and str(dep_delay).strip() else 0
        except (ValueError, TypeError):
            dep_delay_int = 0
        
        try:
            arr_delay_int = int(arr_delay) if arr_delay and str(arr_delay).strip() else 0
        except (ValueError, TypeError):
            arr_delay_int = 0
        
        return dep_delay_int > 0 or arr_delay_int > 0
    
    def extract_flight_data(self, flight: Dict) -> Dict:
        """Extract relevant flight data from API response"""
        # Helper function to safely get nested values
        def safe_get(data, *keys, default=''):
            for key in keys:
                if data is None:
                    return default
                if isinstance(data, dict):
                    data = data.get(key)
                else:
                    return default
            return data if data is not None else default
        
        flight_data = {
            'flight_date': flight.get('flight_date', ''),
            'flight_status': flight.get('flight_status', ''),
            'flight_number': safe_get(flight.get('flight'), 'number'),
            'flight_iata': safe_get(flight.get('flight'), 'iata'),
            'flight_icao': safe_get(flight.get('flight'), 'icao'),
            
            # Departure information
            'departure_airport': safe_get(flight.get('departure'), 'airport'),
            'departure_iata': safe_get(flight.get('departure'), 'iata'),
            'departure_icao': safe_get(flight.get('departure'), 'icao'),
            'departure_timezone': safe_get(flight.get('departure'), 'timezone'),
            'departure_scheduled': safe_get(flight.get('departure'), 'scheduled'),
            'departure_estimated': safe_get(flight.get('departure'), 'estimated'),
            'departure_actual': safe_get(flight.get('departure'), 'actual'),
            'departure_delay': safe_get(flight.get('departure'), 'delay'),
            'departure_terminal': safe_get(flight.get('departure'), 'terminal'),
            'departure_gate': safe_get(flight.get('departure'), 'gate'),
            
            # Arrival information
            'arrival_airport': safe_get(flight.get('arrival'), 'airport'),
            'arrival_iata': safe_get(flight.get('arrival'), 'iata'),
            'arrival_icao': safe_get(flight.get('arrival'), 'icao'),
            'arrival_timezone': safe_get(flight.get('arrival'), 'timezone'),
            'arrival_scheduled': safe_get(flight.get('arrival'), 'scheduled'),
            'arrival_estimated': safe_get(flight.get('arrival'), 'estimated'),
            'arrival_actual': safe_get(flight.get('arrival'), 'actual'),
            'arrival_delay': safe_get(flight.get('arrival'), 'delay'),
            'arrival_terminal': safe_get(flight.get('arrival'), 'terminal'),
            'arrival_gate': safe_get(flight.get('arrival'), 'gate'),
            
            # Airline information
            'airline_name': safe_get(flight.get('airline'), 'name'),
            'airline_iata': safe_get(flight.get('airline'), 'iata'),
            'airline_icao': safe_get(flight.get('airline'), 'icao'),
            
            # Aircraft information
            'aircraft_registration': safe_get(flight.get('aircraft'), 'registration'),
            'aircraft_iata': safe_get(flight.get('aircraft'), 'iata'),
            'aircraft_icao': safe_get(flight.get('aircraft'), 'icao'),
            'aircraft_icao24': safe_get(flight.get('aircraft'), 'icao24'),
            
            # Live information (may be None)
            'live_updated': safe_get(flight.get('live'), 'updated'),
            'live_latitude': safe_get(flight.get('live'), 'latitude'),
            'live_longitude': safe_get(flight.get('live'), 'longitude'),
            'live_altitude': safe_get(flight.get('live'), 'altitude'),
            'live_direction': safe_get(flight.get('live'), 'direction'),
            'live_speed_horizontal': safe_get(flight.get('live'), 'speed_horizontal'),
            'live_speed_vertical': safe_get(flight.get('live'), 'speed_vertical'),
            'live_is_ground': safe_get(flight.get('live'), 'is_ground'),
        }
        
        return flight_data
    
    def _get_existing_flights_set(self, cursor, flight_data_list: List[Dict]) -> set:
        """Check which flights already exist in the database - batch query for efficiency"""
        if not flight_data_list:
            return set()
        
        # Build a set of unique identifiers for batch checking
        flight_keys = []
        for flight_data in flight_data_list:
            key = (
                flight_data.get('flight_date', ''),
                flight_data.get('flight_number', ''),
                flight_data.get('departure_iata', ''),
                flight_data.get('arrival_iata', ''),
                flight_data.get('departure_scheduled', '')
            )
            flight_keys.append(key)
        
        # Use a single query with IN clause or multiple OR conditions
        # SQLite doesn't support tuple IN, so we'll use OR conditions
        if len(flight_keys) == 1:
            key = flight_keys[0]
            cursor.execute('''
                SELECT flight_date, flight_number, departure_iata, arrival_iata, departure_scheduled
                FROM flights 
                WHERE flight_date = ? 
                AND flight_number = ?
                AND departure_iata = ?
                AND arrival_iata = ?
                AND departure_scheduled = ?
            ''', key)
        else:
            # Build OR conditions for batch check
            conditions = []
            params = []
            for key in flight_keys:
                conditions.append('(flight_date = ? AND flight_number = ? AND departure_iata = ? AND arrival_iata = ? AND departure_scheduled = ?)')
                params.extend(key)
            
            query = f'''
                SELECT flight_date, flight_number, departure_iata, arrival_iata, departure_scheduled
                FROM flights 
                WHERE {' OR '.join(conditions)}
            '''
            cursor.execute(query, params)
        
        # Return set of existing flight keys
        existing = set()
        for row in cursor.fetchall():
            existing.add(row)
        
        return existing
    
    def fetch_all_flights(self, max_total: int = 25, **kwargs) -> tuple[List[Dict], List[Dict]]:
        """Fetch flights, stopping when we have max_total NEW flights. Returns (all_flights, delayed_flights)"""
        all_flights = []
        delayed_flights = []
        offset = 0
        api_limit = 100  # Maximum API limit per request for efficiency
        
        # Connect to database to check for existing flights
        self.ensure_table_exists()
        conn = sqlite3.connect(self.db_filename)
        cursor = conn.cursor()
        
        print("Fetching flight data from AviationStack API...")
        print(f"API Key: {self.api_key[:20]}...")
        print(f"Target: {max_total} NEW flights (skipping existing ones)")
        print(f"Using maximum API batch size ({api_limit}) for efficiency")
        print("Filtering for delayed flights (departure.delay > 0 or arrival.delay > 0)")
        print()
        
        api_calls_made = 0
        
        while len(all_flights) < max_total:
            # Always fetch maximum batch size (100) to maximize API call efficiency
            # This gives us the best chance of getting 25 new flights in fewer API calls
            current_batch_size = api_limit
            
            api_calls_made += 1
            print(f"API Call #{api_calls_made}: Fetching {current_batch_size} flights (offset: {offset}, new flights so far: {len(all_flights)}/{max_total}, delayed: {len(delayed_flights)})...")
            
            data = self.fetch_flights(limit=current_batch_size, offset=offset, **kwargs)
            
            if not data or 'data' not in data:
                print("No more data available or error occurred.")
                break
            
            flights = data.get('data', [])
            
            if not flights:
                print("No flights returned.")
                break
            
            # Extract ALL flight data first (no DB checks yet)
            batch_flight_data = []
            for flight in flights:
                flight_data = self.extract_flight_data(flight)
                batch_flight_data.append(flight_data)
            
            # Batch check which flights already exist (single DB query instead of N queries)
            existing_flights = self._get_existing_flights_set(cursor, batch_flight_data)
            
            # Filter out existing flights and process new ones
            delayed_in_batch = 0
            skipped_in_batch = 0
            for i, flight_data in enumerate(batch_flight_data):
                # Create key for comparison
                flight_key = (
                    flight_data.get('flight_date', ''),
                    flight_data.get('flight_number', ''),
                    flight_data.get('departure_iata', ''),
                    flight_data.get('arrival_iata', ''),
                    flight_data.get('departure_scheduled', '')
                )
                
                # Check if flight already exists
                if flight_key in existing_flights:
                    skipped_in_batch += 1
                    continue
                
                # Add NEW flights to the list
                all_flights.append(flight_data)
                
                # Check if flight is delayed (departure.delay > 0 or arrival.delay > 0)
                original_flight = flights[i]
                dep_delay = original_flight.get('departure', {}).get('delay')
                arr_delay = original_flight.get('arrival', {}).get('delay')
                
                # Track delayed flights separately
                if self._is_delayed(dep_delay, arr_delay):
                    delayed_flights.append(flight_data)
                    delayed_in_batch += 1
                
                # Stop if we've reached max_total new flights
                if len(all_flights) >= max_total:
                    break
            
            new_in_batch = len(flights) - skipped_in_batch
            print(f"Retrieved {len(flights)} flights, {skipped_in_batch} already exist, {new_in_batch} new (new total: {len(all_flights)}/{max_total}, delayed: {len(delayed_flights)})")
            
            # Stop if we've reached max_total new flights
            if len(all_flights) >= max_total:
                # Trim to exactly max_total if we got more
                if len(all_flights) > max_total:
                    all_flights = all_flights[:max_total]
                    # Also trim delayed_flights to match
                    delayed_flights = [f for f in delayed_flights if f in all_flights]
                print(f"Reached target of {max_total} new flights in {api_calls_made} API call(s). Stopping.")
                break
            
            # Check if we got fewer results than requested (end of data)
            if len(flights) < current_batch_size:
                print("No more flights available.")
                break
            
            # Move to next page
            offset += len(flights)
        
        conn.close()
        
        if len(all_flights) < max_total:
            print(f"\nNote: Only found {len(all_flights)} new flights (target was {max_total}) after {api_calls_made} API call(s).")
        
        return all_flights, delayed_flights
    
    def ensure_table_exists(self):
        """Ensure the flights and delayed_flights tables exist in the database"""
        conn = sqlite3.connect(self.db_filename)
        cursor = conn.cursor()
        
        # Create flights table if it doesn't exist - stores ALL flights
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS flights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                flight_date TEXT,
                flight_status TEXT,
                flight_number TEXT,
                flight_iata TEXT,
                flight_icao TEXT,
                departure_airport TEXT,
                departure_iata TEXT,
                departure_icao TEXT,
                departure_timezone TEXT,
                departure_scheduled TEXT,
                departure_estimated TEXT,
                departure_actual TEXT,
                departure_delay TEXT,
                departure_terminal TEXT,
                departure_gate TEXT,
                arrival_airport TEXT,
                arrival_iata TEXT,
                arrival_icao TEXT,
                arrival_timezone TEXT,
                arrival_scheduled TEXT,
                arrival_estimated TEXT,
                arrival_actual TEXT,
                arrival_delay TEXT,
                arrival_terminal TEXT,
                arrival_gate TEXT,
                airline_name TEXT,
                airline_iata TEXT,
                airline_icao TEXT,
                aircraft_registration TEXT,
                aircraft_iata TEXT,
                aircraft_icao TEXT,
                aircraft_icao24 TEXT,
                live_updated TEXT,
                live_latitude TEXT,
                live_longitude TEXT,
                live_altitude TEXT,
                live_direction TEXT,
                live_speed_horizontal TEXT,
                live_speed_vertical TEXT,
                live_is_ground TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create delayed_flights table - only stores flight_id, delay, and airline_name
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS delayed_flights (
                id INTEGER PRIMARY KEY,
                delay INTEGER,
                airline_name TEXT,
                FOREIGN KEY (id) REFERENCES flights(id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_to_db(self, all_flights: List[Dict], delayed_flights: List[Dict]):
        """Save all flights to flights table, and delayed flights to delayed_flights table"""
        if not all_flights:
            print("No flight data to save to database.")
            return
        
        # Ensure tables exist
        self.ensure_table_exists()
        
        conn = sqlite3.connect(self.db_filename)
        cursor = conn.cursor()
        
        # Create a set of delayed flight keys for quick lookup (using flight data as key)
        delayed_keys = set()
        for dflight in delayed_flights:
            # Create a unique key from flight data
            key = (
                dflight.get('flight_date', ''),
                dflight.get('flight_number', ''),
                dflight.get('departure_iata', ''),
                dflight.get('arrival_iata', ''),
                dflight.get('departure_scheduled', '')
            )
            delayed_keys.add(key)
        
        # Save ALL flights to flights table
        flights_inserted = 0
        flights_skipped = 0
        delayed_inserted = 0
        
        for flight in all_flights:
            # Check if flight already exists (using unique combination of identifiers)
            cursor.execute('''
                SELECT id FROM flights 
                WHERE flight_date = ? 
                AND flight_number = ?
                AND departure_iata = ?
                AND arrival_iata = ?
                AND departure_scheduled = ?
            ''', (
                flight.get('flight_date', ''),
                flight.get('flight_number', ''),
                flight.get('departure_iata', ''),
                flight.get('arrival_iata', ''),
                flight.get('departure_scheduled', '')
            ))
            
            existing_flight = cursor.fetchone()
            
            if existing_flight:
                # Flight already exists, skip insertion but check if it needs to be added to delayed_flights
                flights_skipped += 1
                flight_id = existing_flight[0]
                
                # Check if this flight is delayed and if it's already in delayed_flights
                flight_key = (
                    flight.get('flight_date', ''),
                    flight.get('flight_number', ''),
                    flight.get('departure_iata', ''),
                    flight.get('arrival_iata', ''),
                    flight.get('departure_scheduled', '')
                )
                if flight_key in delayed_keys:
                    # Check if already in delayed_flights table
                    cursor.execute('SELECT id FROM delayed_flights WHERE id = ?', (flight_id,))
                    if not cursor.fetchone():
                        # Not in delayed_flights yet, add it
                        dep_delay = flight.get('departure_delay', '')
                        arr_delay = flight.get('arrival_delay', '')
                        
                        try:
                            dep_delay_int = int(dep_delay) if dep_delay and str(dep_delay).strip() else 0
                        except (ValueError, TypeError):
                            dep_delay_int = 0
                        
                        try:
                            arr_delay_int = int(arr_delay) if arr_delay and str(arr_delay).strip() else 0
                        except (ValueError, TypeError):
                            arr_delay_int = 0
                        
                        delay_value = max(dep_delay_int, arr_delay_int)
                        airline_name = flight.get('airline_name', '')
                        
                        cursor.execute('''
                            INSERT INTO delayed_flights (id, delay, airline_name)
                            VALUES (?, ?, ?)
                        ''', (flight_id, delay_value, airline_name))
                        delayed_inserted += 1
                continue
            
            # Insert into flights table
            cursor.execute('''
                INSERT INTO flights (
                    flight_date, flight_status, flight_number, flight_iata, flight_icao,
                    departure_airport, departure_iata, departure_icao, departure_timezone,
                    departure_scheduled, departure_estimated, departure_actual, departure_delay,
                    departure_terminal, departure_gate,
                    arrival_airport, arrival_iata, arrival_icao, arrival_timezone,
                    arrival_scheduled, arrival_estimated, arrival_actual, arrival_delay,
                    arrival_terminal, arrival_gate,
                    airline_name, airline_iata, airline_icao,
                    aircraft_registration, aircraft_iata, aircraft_icao, aircraft_icao24,
                    live_updated, live_latitude, live_longitude, live_altitude,
                    live_direction, live_speed_horizontal, live_speed_vertical, live_is_ground
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                flight.get('flight_date', ''),
                flight.get('flight_status', ''),
                flight.get('flight_number', ''),
                flight.get('flight_iata', ''),
                flight.get('flight_icao', ''),
                flight.get('departure_airport', ''),
                flight.get('departure_iata', ''),
                flight.get('departure_icao', ''),
                flight.get('departure_timezone', ''),
                flight.get('departure_scheduled', ''),
                flight.get('departure_estimated', ''),
                flight.get('departure_actual', ''),
                flight.get('departure_delay', ''),
                flight.get('departure_terminal', ''),
                flight.get('departure_gate', ''),
                flight.get('arrival_airport', ''),
                flight.get('arrival_iata', ''),
                flight.get('arrival_icao', ''),
                flight.get('arrival_timezone', ''),
                flight.get('arrival_scheduled', ''),
                flight.get('arrival_estimated', ''),
                flight.get('arrival_actual', ''),
                flight.get('arrival_delay', ''),
                flight.get('arrival_terminal', ''),
                flight.get('arrival_gate', ''),
                flight.get('airline_name', ''),
                flight.get('airline_iata', ''),
                flight.get('airline_icao', ''),
                flight.get('aircraft_registration', ''),
                flight.get('aircraft_iata', ''),
                flight.get('aircraft_icao', ''),
                flight.get('aircraft_icao24', ''),
                flight.get('live_updated', ''),
                flight.get('live_latitude', ''),
                flight.get('live_longitude', ''),
                flight.get('live_altitude', ''),
                flight.get('live_direction', ''),
                flight.get('live_speed_horizontal', ''),
                flight.get('live_speed_vertical', ''),
                flight.get('live_is_ground', '')
            ))
            flights_inserted += 1
            flight_id = cursor.lastrowid
            
            # Check if this flight is delayed and save to delayed_flights table
            flight_key = (
                flight.get('flight_date', ''),
                flight.get('flight_number', ''),
                flight.get('departure_iata', ''),
                flight.get('arrival_iata', ''),
                flight.get('departure_scheduled', '')
            )
            if flight_key in delayed_keys:
                # Get the delay value (use the larger of departure_delay or arrival_delay)
                dep_delay = flight.get('departure_delay', '')
                arr_delay = flight.get('arrival_delay', '')
                
                # Convert to integer, use the larger delay value
                try:
                    dep_delay_int = int(dep_delay) if dep_delay and str(dep_delay).strip() else 0
                except (ValueError, TypeError):
                    dep_delay_int = 0
                
                try:
                    arr_delay_int = int(arr_delay) if arr_delay and str(arr_delay).strip() else 0
                except (ValueError, TypeError):
                    arr_delay_int = 0
                
                delay_value = max(dep_delay_int, arr_delay_int)
                airline_name = flight.get('airline_name', '')
                
                # Insert into delayed_flights table
                cursor.execute('''
                    INSERT INTO delayed_flights (id, delay, airline_name)
                    VALUES (?, ?, ?)
                ''', (flight_id, delay_value, airline_name))
                delayed_inserted += 1
        
        conn.commit()
        conn.close()
        
        print(f"Saved {flights_inserted} new flights to database '{self.db_filename}' (table: flights)")
        print(f"Skipped {flights_skipped} flights that already exist")
        print(f"Saved {delayed_inserted} delayed flights to database '{self.db_filename}' (table: delayed_flights)")
    
    def save_to_csv(self, flights: List[Dict], filename: str = 'flight_data.csv'):
        """Save flight data to CSV file"""
        if not flights:
            print("No flight data to save.")
            return
        
        # Get all field names from the first flight
        fieldnames = list(flights[0].keys())
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for flight in flights:
                writer.writerow(flight)
        
        print(f"\nSaved {len(flights)} flights to {filename}")


def main():
    """Main function"""
    output_csv = 'flight_data.csv'
    db_filename = 'airports.db'
    
    print("=" * 60)
    print("AviationStack Flight Data Fetcher")
    print("=" * 60)
    print(f"API Key: {AVIATIONSTACK_KEY[:20]}...")
    print(f"Output CSV: {output_csv}")
    print(f"Database: {db_filename} (tables: flights, delayed_flights)")
    print("=" * 60)
    print()
    
    fetcher = FlightDataFetcher(AVIATIONSTACK_KEY, db_filename)
    
    # Fetch 25 flights per run
    # The script will save ALL flights to flights table, and delayed flights to delayed_flights table
    # You can add parameters like flight_status='active', dep_iata='JFK', etc.
    # For example: all_flights, delayed = fetcher.fetch_all_flights(max_total=25, flight_status='active')
    all_flights, delayed_flights = fetcher.fetch_all_flights(max_total=25)  # Process 25 flights per run
    
    # Save to CSV (only delayed flights) and database (all flights + delayed flights table)
    if delayed_flights:
        fetcher.save_to_csv(delayed_flights, output_csv)
        fetcher.save_to_db(all_flights, delayed_flights)
        
        # Print summary
        print(f"\n=== Summary ===")
        print(f"Total flights fetched: {len(all_flights)}")
        print(f"Total delayed flights: {len(delayed_flights)}")
        print(f"Errors: {len(fetcher.errors)}")
        
        # Print sample
        if delayed_flights:
            print(f"\n=== Sample Delayed Flight ===")
            sample = delayed_flights[0]
            print(f"Flight: {sample.get('flight_number', 'N/A')}")
            print(f"Status: {sample.get('flight_status', 'N/A')}")
            print(f"Departure: {sample.get('departure_airport', 'N/A')} ({sample.get('departure_iata', 'N/A')})")
            print(f"Departure Delay: {sample.get('departure_delay', 'N/A')} minutes")
            print(f"Arrival: {sample.get('arrival_airport', 'N/A')} ({sample.get('arrival_iata', 'N/A')})")
            print(f"Arrival Delay: {sample.get('arrival_delay', 'N/A')} minutes")
            print(f"Airline: {sample.get('airline_name', 'N/A')}")
    else:
        print("No flights retrieved.")
    
    # Save errors if any
    if fetcher.errors:
        error_file = 'flight_api_errors.csv'
        with open(error_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=['offset', 'error'])
            writer.writeheader()
            writer.writerows(fetcher.errors)
        print(f"\nErrors saved to: {error_file}")


if __name__ == "__main__":
    main()

