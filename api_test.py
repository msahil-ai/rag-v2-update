import requests

def send_data():
    url = "http://192.168.0.48:8080/api/v1/external/receive"

    payload = {
        "response": "Sahil"
    }

    try:
        response = requests.post(url, json=payload, timeout=10)

        print("Status Code:", response.status_code)

        # Safe handling
        if response.headers.get("Content-Type", "").startswith("application/json"):
            print("JSON Response:", response.json())
        else:
            print("Raw Response:", response.text)

    except requests.exceptions.RequestException as e:
        print(" Request Error:", e)


send_data()