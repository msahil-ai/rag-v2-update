import requests

def fetch_data():
    url = "http://192.168.0.48:8080/api/v1/day-level/combined-json"

    response = requests.get(url)
    response.raise_for_status()  # ensures no silent failure

    json_response = response.json()

    data = json_response.get("data")

    #print(data)  # full "data" object

    return data


if __name__ == "__main__":
    data = fetch_data()