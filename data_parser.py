import re
import json
import os
import ast
from datetime import datetime

error_count = 0

class CTATrainDataParser:
    """
    A class to parse and analyze CTA train tracker data
    """
    
    def __init__(self):
        self.raw_data = []
        self.parsed_data = []
        self.stations = {}

    def parse_data_string(self, data_string):
        """
        Parse a string containing CTA data records
        """
        self.raw_data = []
        self.parsed_data = []
        
        # Split into lines and process each line
        lines = data_string.strip().split('\n')
        for line in lines:
            self._parse_line(line)
        
        return self.parsed_data
    
    def parse_file(self, file_path):
        """
        Parse CTA data from a file
        """
        with open(file_path, 'r') as f:
            data_string = f.read()
        
        return self.parse_data_string(data_string)
        
    def _parse_line(self, line):
        """
        Parse a single line of CTA data
        """
        # Initial split by comma, but we need to handle the JSON part specially
        parts = []
        current_part = ''
        in_json = False
        in_quotes = False
        
        for char in line:
            if char == '"' and (len(current_part) == 0 or current_part[-1] != '\\'):
                in_quotes = not in_quotes
                current_part += char
            elif char == '{' and in_quotes:
                in_json = True
                current_part += char
            elif char == '}' and in_json:
                in_json = False
                current_part += char
            elif char == ',' and not in_quotes and not in_json:
                parts.append(current_part)
                current_part = ''
            else:
                current_part += char
        
        if current_part:
            parts.append(current_part)
        
        if len(parts) < 4:
            print(f"Skipping line with insufficient data: {line[:50]}...")
            return
        
        # Extract basic information
        row_id = parts[0]
        timestamp_str = parts[1]
        station_id = parts[2]
        json_data_str = parts[3]
        extension = parts[4] if len(parts) > 4 else None
        
        if station_id == -199999:
            return
        
        # Parse timestamp
        try:
            timestamp = datetime.fromisoformat(timestamp_str)
        except ValueError:
            timestamp = None
        
        # Parse JSON data
        parsed_json = self._parse_json(json_data_str)
        if not parsed_json:
            return
        
        # Create record
        record = {
            'row_id': row_id,
            'timestamp': timestamp,
            'station_id': station_id,
            'raw_json': parsed_json,
            'extension': extension
        }
        
        # Process ETA data
        eta_entries = self._process_eta_entries(parsed_json, timestamp)
        record['eta_entries'] = eta_entries
        
        # Update stations dictionary
        if eta_entries:
            station_name = eta_entries[0].get('station_name')
            if station_name:
                self.stations[station_id] = station_name
        
        self.parsed_data.append(record)
    
    def _parse_json(self, json_data_str):
        """
        Parse the JSON data string from the CTA data
        """
        global error_count
        if not json_data_str:
            return None
        
        # Clean the JSON string for parsing
        json_data_str = json_data_str.strip()

        # Remove wrapping quotes
        if json_data_str.startswith('"') and json_data_str.endswith('"'):
            json_data_str = json_data_str[1:-1]

        # Fix single quotes and special characters
        json_data_str = json_data_str.replace("O'Hare", "OHare")
        json_data_str = json_data_str.replace("'", '"')  # Replace single quotes with double
        json_data_str = json_data_str.replace('None', '"None"')

        # Optional: remove any newline characters
        json_data_str = json_data_str.replace('\n', '').replace('\r', '')

        try:
            cleaned = re.sub(r':\s*""(.*?)""', r': "\1"', json_data_str)
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            print(f"Problematic JSON: {json_data_str[:100]}...")
            return self._safe_parse_json(json_data_str)
    
    def _safe_parse_json(self, raw_json_string):
        global error_count
        try:
            # Try normal JSON first (if it happens to be valid already)
            return json.loads(raw_json_string)
        except json.JSONDecodeError:
            try:
                # Try turning it into a Python dict via ast.literal_eval
                # (This handles single quotes, None, etc.)
                parsed = ast.literal_eval(raw_json_string)
                # Then convert back to string and parse as JSON (to get it in proper dict format)
                return json.loads(json.dumps(parsed))
            except Exception as e:
                error_count += 1
                print(f"Failed to parse JSON: {e}")
                return None

    
    def _process_eta_entries(self, json_data, timestamp):
        """
        Process ETA entries from parsed JSON
        """
        if not json_data or 'ctatt' not in json_data:
            return []
        
        eta_list = json_data.get('ctatt', {}).get('eta', [])
        processed_entries = []
        
        for eta in eta_list:
            entry = {
                'station_id': eta.get('staId', -1),
                'station_name': eta.get('staNm', 'Unknown'),
                'stop_id': eta.get('stpId', -1),
                'stop_description': eta.get('stpDe', 'Unknown'),
                'run_number': eta.get('rn', 'Unknown'),
                'route': eta.get('rt', 'Unknown'),
                'destination_id': eta.get('destSt', 'Unknown'),
                'destination_name': eta.get('destNm', 'Unknown'),
                'direction': eta.get('trDr', 'Unknown'),
                'predicted_time': self._parse_datetime(eta.get('prdt', None)),
                'arrival_time': self._parse_datetime(eta.get('arrT', None)),
                'is_approaching': eta.get('isApp', '0') == '1',
                'is_scheduled': eta.get('isSch', '0') == '1',
                'is_delayed': eta.get('isDly', '0') == '1',
                'latitude': eta.get('lat', '0') if eta.get('lat') else None,
                'longitude': eta.get('lon', '0') if eta.get('lon') else None,
                'heading': eta.get('heading', '0') if eta.get('heading') else None
            }
            
            # Calculate minutes until arrival
            if timestamp and entry['arrival_time']:
                time_diff = entry['arrival_time'] - timestamp.replace(tzinfo=None)
                entry['minutes_until_arrival'] = time_diff.total_seconds() / 60
            else:
                entry['minutes_until_arrival'] = None
            
            processed_entries.append(entry)
        
        # Sort by arrival time
        processed_entries.sort(key=lambda x: x['arrival_time'] if x['arrival_time'] else datetime.max)
        
        return processed_entries
    
    def _parse_datetime(self, datetime_str):
        """
        Parse datetime string to datetime object
        """
        if not datetime_str:
            return None
        
        try:
            # Format: 2025-04-01T16:23:03
            return datetime.fromisoformat(datetime_str.replace('T', ' '))
        except ValueError:
            return None
    
    def get_entries_by_station(self, station_id):
        """
        Get all entries for a specific station
        """
        result = []
        for record in self.parsed_data:
            if record['station_id'] == station_id:
                result.append((record['timestamp'], record['eta_entries']))
        return result

    def get_next_arriving_trains(self, station_id=None, limit=3):
        """
        Get the next arriving trains, optionally filtered by station
        """
        all_trains = []
        for record in self.parsed_data:
            if station_id and record['station_id'] != station_id:
                continue
                
            for eta in record['eta_entries']:
                all_trains.append(eta)
        
        # Sort by minutes until arrival
        all_trains.sort(key=lambda x: x['minutes_until_arrival'] if x['minutes_until_arrival'] is not None else float('inf'))
        
        # Group by station and get top trains for each
        stations = {}
        result = []
        
        for train in all_trains:
            station = train['station_id']
            if station not in stations:
                stations[station] = 0
            
            if stations[station] < limit:
                result.append(train)
                stations[station] += 1
        
        return result
    
    def get_trains_by_route(self, route):
        """
        Get all trains for a specific route (e.g., 'Red', 'Blue', 'Brn')
        """
        result = []
        
        for record in self.parsed_data:
            for eta in record['eta_entries']:
                if eta['route'] == route:
                    result.append(eta)
        
        # Sort by arrival time
        result.sort(key=lambda x: x['arrival_time'] if x['arrival_time'] else datetime.max)
        
        return result
    
    def get_station_stats(self):
        """
        Get statistics for each station
        """
        stats = {}
        
        for record in self.parsed_data:
            station_id = record['station_id']
            if station_id not in stats:
                stats[station_id] = {
                    'station_name': self.stations.get(station_id, 'Unknown'),
                    'total_trains': 0,
                    'routes': set(),
                    'approaching_trains': 0
                }
            
            for eta in record['eta_entries']:
                stats[station_id]['total_trains'] += 1
                stats[station_id]['routes'].add(eta['route'])
                if eta['is_approaching']:
                    stats[station_id]['approaching_trains'] += 1
        
        # Convert sets to lists for easier display
        for station in stats:
            stats[station]['routes'] = list(stats[station]['routes'])
        
        return stats

    def print_next_arrivals(self, limit=3):
        """
        Print a formatted list of next arrivals
        """
        next_trains = self.get_next_arriving_trains(limit=limit)
        
        print("\nNext arriving trains:")
        print("-" * 80)
        print(f"{'Station':<15} {'Route':<5} {'Destination':<15} {'Arrival Time':<20} {'Minutes':<8}")
        print("-" * 80)
        
        for train in next_trains:
            station = train['station_name']
            route = train['route']
            dest = train['destination_name']
            arr_time = train['arrival_time'].strftime('%Y-%m-%d %H:%M:%S') if train['arrival_time'] else 'Unknown'
            minutes = f"{train['minutes_until_arrival']:.1f}" if train['minutes_until_arrival'] is not None else 'Unknown'
            
            print(f"{station:<15} {route:<5} {dest:<15} {arr_time:<20} {minutes:<8}")


# Example usage
if __name__ == "__main__":
    main()