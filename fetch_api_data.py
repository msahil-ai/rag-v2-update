import requests

def fetch_data():
    url = "http://192.168.0.48:8080/api/v1/day-level/combined-json"
    # url = "http://192.168.0.48:8080/api/v1/day-level/combined-json"

    try:
        print(f"Connecting to API...")
        response = requests.get(url)
        
        print(f"API Status Code: {response.status_code}")

        # Try to decode the JSON safely
        try:
            json_response = response.json()
        except requests.exceptions.JSONDecodeError:
            print("\nCRITICAL: The API did not return JSON. Here is what it sent instead:")
            print(response.text[:500]) 
            return None

        # ---> THE FIX: Return the absolute RAW response <---
        # We will let the "Deep Searcher" in embed_json_data.py dig through the wrappers!
        return json_response
        
    except requests.exceptions.ConnectionError:
        print("\n CRITICAL: Could not connect to the API.")
        return None

if __name__ == "__main__":
    data = fetch_data()
    if data:
        print("Data fetched successfully!")