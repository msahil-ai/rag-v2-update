import json
import os
import random
import chromadb
from chromadb.utils import embedding_functions
from datetime import date

# Turn off ChromaDB telemetry
os.environ["ANONYMIZED_TELEMETRY"] = "False"

# Initialize ChromaDB
client = chromadb.PersistentClient(path="./chroma_db")
embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
collection = client.get_collection(name="travel_packages_json", embedding_function=embed_fn)

def get_next_month_first_day():
    today = date.today()
    if today.month == 12:
        return date(today.year + 1, 1, 1).strftime("%Y-%m-%d")
    return date(today.year, today.month + 1, 1).strftime("%Y-%m-%d")

def find_best_package(email_json_path):
    with open(email_json_path, 'r', encoding='utf-8') as f:
        request = json.load(f)

    # 1. Core Variables & Fallbacks
    sender_email = request.get("sender_email", "").strip().lower()
    start_date = request.get("start_date") or get_next_month_first_day()
    
    target_country = (request.get("destination_country") or "").strip().lower()
    target_city = (request.get("destination_city") or "").strip().lower()
    
    requested_days = request.get("duration_days")
    requested_days = int(requested_days) if requested_days else 3

    if not target_country or not sender_email:
        print("Missing country or sender_email in the extracted email. Skipping.")
        return None

    print(f"Searching DB for DMC: {sender_email} | {target_country.title()} for {requested_days} days...")

    # 2. Strict B2B Multi-Tenant Filtering (REMOVED INVALID $contains)
    # MUST match DMC_email, Country, and Total Days
    filter_conditions = [
        {"DMC_email": {"$eq": sender_email}},
        {"country": {"$eq": target_country}},
        {"total_days": {"$eq": requested_days}}
    ]

    strict_filters = {"$and": filter_conditions}

    try:
        # Search the database - we pull top 5 so we can filter the city in Python!
        results = collection.query(
            query_texts=[f"Premium {requested_days}-day travel package to {target_city}, {target_country}"],
            n_results=5, 
            where=strict_filters
        )
        
        if not results['metadatas'] or not results['metadatas'][0]:
            print(f"No packages found for {sender_email} matching those exact criteria.")
            return None

        # ---> THE FIX: Python Post-Filtering for City <---
        best_match = None
        for meta in results['metadatas'][0]:
            if target_city:
                # If they asked for a city, ensure it's in this package's city string
                if target_city in meta.get("cities_included", ""):
                    best_match = meta
                    break
            else:
                # If they didn't ask for a specific city, the top result is fine
                best_match = meta
                break

        if not best_match:
            print(f"Found packages for DMC, but none included the specific city: {target_city.title()}")
            return None
        # --------------------------------------------------

        # 3. Extract the Winning Package & Global Lists
        raw_package = json.loads(best_match.get("raw_package", "{}"))
        all_services = json.loads(best_match.get("raw_all_services", "{}"))
        
        print(f"Found Package ID: {best_match.get('package_id')}!")

        # 4. THE SMART SWAPPER LOGIC
        requested_star_rating = request.get("preferred_hotel_star") 
        
        if requested_star_rating:
            print(f"Checking for {requested_star_rating}-star hotel upgrades...")
            global_hotels = all_services.get("hotels", {})
            
            # Loop through the days in the package
            days_dict = raw_package.get("days", {})
            for day_key, day_data in days_dict.items():
                current_hotels = day_data.get("hotels", {})
                
                # Check if current hotel matches requested stars
                needs_swap = True
                for h_key, h_val in current_hotels.items():
                    if str(h_val.get("hotel_star_rating")) == str(requested_star_rating):
                        needs_swap = False
                        break
                
                if needs_swap:
                    # Find a replacement from the global list
                    replacement_found = False
                    for glob_h_key, glob_h_val in global_hotels.items():
                        if str(glob_h_val.get("hotel_star_rating")) == str(requested_star_rating):
                            day_data["hotels"] = {glob_h_key: glob_h_val}
                            print(f"  -> Swapped Day {day_data.get('day')} hotel to {glob_h_val.get('hotel_name')} ({requested_star_rating}-star)")
                            replacement_found = True
                            break
                    
                    # Random Fallback
                    if not replacement_found and global_hotels:
                        random_hotel_key = random.choice(list(global_hotels.keys()))
                        day_data["hotels"] = {random_hotel_key: global_hotels[random_hotel_key]}
                        print(f"  -> Requested stars not found. Randomly swapped to {global_hotels[random_hotel_key].get('hotel_name')}")

        # 5. Build the Final Output
        final_response_variable = {
            "sender_email": sender_email,
            "start_date": start_date,
            "Master_DMC_id": best_match.get("Master_DMC_id"),
            "destinations": [
                {
                    "DMC": [
                        {
                            "DMC_id": best_match.get("DMC_id"),
                            "DMC_email": best_match.get("DMC_email"),
                            "country": best_match.get("country").title(),
                            "packages": [raw_package] 
                        }
                    ]
                }
            ]
        }

        print("\nFINAL PACKAGE READY!")
        print(json.dumps(final_response_variable, indent=4))
        
        return final_response_variable

    except Exception as e:
        print(f"Search Error: {e}")
        return None

if __name__ == "__main__":
    OUTPUT_DIR = "outputs"
    
    if not os.path.exists(OUTPUT_DIR) or not os.listdir(OUTPUT_DIR):
        print(f"No extracted emails found in '{OUTPUT_DIR}'. Run the fetcher first!")
    else:
        for filename in os.listdir(OUTPUT_DIR):
            if filename.endswith(".json"):
                print("\n" + "="*50)
                print(f"Processing File: {filename}")
                filepath = os.path.join(OUTPUT_DIR, filename)
                matched_package = find_best_package(filepath)