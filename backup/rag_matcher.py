import json
import os
import random
import chromadb
from chromadb.utils import embedding_functions
from post_response_to_api import send_data

# 1. Module-Level Initialization 
client = chromadb.PersistentClient(path="./chroma_db")
embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
collection = client.get_collection(name="travel_packages_json", embedding_function=embed_fn)

def find_best_package(email_json_path):
    """Reads the extracted JSON and queries the Vector DB for the best package."""
    
    with open(email_json_path, 'r', encoding='utf-8') as f:
        request = json.load(f)

    target_country = (request.get("destination_country") or "").strip().lower()
    target_city = (request.get("destination_city") or "").strip().lower()
    requested_days = request.get("duration_days") 
    
    if not requested_days:
        requested_days = 3  
    else:
        requested_days = int(requested_days)

    if not target_country or not target_city:
        print("Missing country or city in the extracted email. Skipping.")
        return None

    print(f"Searching Vector DB for: {target_city.title()}, {target_country.title()} for ~{requested_days} days...")

    # 2. Strict Pre-Filtering (Country -> City ONLY)
    strict_filters = {
        "$and": [
            {"country": {"$eq": target_country}}, 
            {"city": {"$eq": target_city}}
        ]
    }

    try:
        results = collection.query(
            query_texts=[f"A premium trip to {target_city}, {target_country}"],
            n_results=15, 
            where=strict_filters
        )
        
        if not results['metadatas'] or not results['metadatas'][0]:
            print("No matches found for that location.")
            return None

        # 4. Find the closest match and gather ties for Random Selection
        best_matches = []
        min_diff_absolute = float('inf')
        best_actual_difference = 0

        for meta in results['metadatas'][0]:
            pkg_days = meta.get("max_days")
            diff = pkg_days - requested_days
            abs_diff = abs(diff)

            if abs_diff < min_diff_absolute or (abs_diff == min_diff_absolute and diff > best_actual_difference):
                min_diff_absolute = abs_diff
                best_actual_difference = diff
                best_matches = [meta] 
            
            elif abs_diff == min_diff_absolute and diff == best_actual_difference:
                best_matches.append(meta)

        # 5. RANDOM SELECTION: Pick randomly if multiple DMCs tied
        best_match_metadata = random.choice(best_matches)

        # 6. Extract and parse the raw stringified JSON back into dictionaries
        index_key = best_match_metadata.get("index_key", "0")
        hotels_data = json.loads(best_match_metadata.get("raw_hotels", "{}"))
        attractions_data = json.loads(best_match_metadata.get("raw_attractions", "{}"))
        restaurants_data = json.loads(best_match_metadata.get("raw_restaurants", "{}"))
        activities_data = json.loads(best_match_metadata.get("raw_activities", "{}"))
        services_data = json.loads(best_match_metadata.get("raw_services", "{}")) # NEW: Unpack services

        display_country = target_country.upper() if len(target_country) <= 3 else target_country.title()
        display_city = target_city.title()

        # 7. Construct the EXACT requested nested JSON output structure
        final_response_variable = {
            "Master_DMC_id": best_match_metadata.get("Master_DMC_id"), 
            "DMC_id": best_match_metadata.get("DMC_id"),
            "country": display_country,
            "cities": [
                {
                    "city": display_city,
                    "packages": [
                        {
                            "days": {
                                str(index_key): {
                                    "day": best_match_metadata.get("max_days"),
                                    "diff": best_actual_difference,
                                    "hotels": hotels_data,
                                    "attractions": attractions_data,
                                    "restaurants": restaurants_data,
                                    "activities": activities_data,
                                    "services": services_data # NEW: Inject into final output
                                }
                            }
                        }
                    ]
                }
            ]
        }

        print("MATCH FOUND! Stored Variable Data:")
        print(json.dumps(final_response_variable, indent=4))

        send_data(final_response_variable)  # POST to API
        
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