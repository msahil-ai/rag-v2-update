import requests

def send_data(final_response):
    url = "http://192.168.0.48:8080/api/v1/external/receive"

    payload = {
        "response": final_response   # RAG output goes here
    }

    try:
        response = requests.post(url, json=payload, timeout=10)

        print("Status Code:", response.status_code)

        if response.status_code == 204:
            print("Success (No Content)")
            return

        # Safe response handling
        try:
            print("JSON Response:", response.json())
        except ValueError:
            print("Raw Response:", response.text)

    except requests.exceptions.RequestException as e:
        print("Request Error:", e)