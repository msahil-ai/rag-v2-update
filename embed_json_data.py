import os
import json

# 1. THIS MUST BE BEFORE CHROMADB IS IMPORTED! Shuts off the telemetry warnings.
os.environ["ANONYMIZED_TELEMETRY"] = "False"

import chromadb
import shutil
from chromadb.utils import embedding_functions
from fetch_api_data import fetch_data

# Initialize ChromaDB
DB_DIR = "./chroma_db"

if os.path.exists(DB_DIR):
    shutil.rmtree(DB_DIR)
os.makedirs(DB_DIR, exist_ok=True)
client = chromadb.PersistentClient(path=DB_DIR)

embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

collection_name = "travel_packages_json"
try:
    client.delete_collection(name=collection_name)
except Exception:
    pass
collection = client.create_collection(name=collection_name, embedding_function=embed_fn)

def build_vector_db_from_api():
    print("Fetching live data from API...")
    
    data = fetch_data()
    
    if not data:
        print("Failed to retrieve data from API.")
        return

    # ---> NEW: DEBUG PRINT <---
    # This will tell us EXACTLY what the API is handing over
    print("\n--- DEBUG: API Data Structure ---")
    if isinstance(data, dict):
        print(f"Format: Dictionary")
        print(f"Keys found: {list(data.keys())}")
    elif isinstance(data, list):
        print(f"Format: List")
        print(f"Total items in list: {len(data)}")
    else:
        print(f"Format: {type(data)}")
    print("---------------------------------\n")

    if isinstance(data, dict):
        master_list = data.get("Master_DMC", [])
    elif isinstance(data, list):
        master_list = data
    else:
        print("Error: API returned an unexpected data format.")
        return
    
    #---------------------------------------------------------------------------------------------

    # This will dig through as many 'data' wrappers as the API uses until it finds 'Master_DMC'
    master_list = []
    current_data = data
    
    # Try to drill down safely up to 5 layers deep
    for _ in range(5): 
        if isinstance(current_data, dict):
            if "Master_DMC" in current_data:
                master_list = current_data.get("Master_DMC", [])
                print("Found 'Master_DMC' successfully!")
                break
            elif "data" in current_data:
                print("... Drilling deeper into another 'data' wrapper ...")
                current_data = current_data["data"]
            else:
                break
        elif isinstance(current_data, list):
            # If the API eventually hands us the raw list
            master_list = current_data
            print("Found raw list successfully!")
            break

    if not master_list:
        print("Error: Could not find 'Master_DMC' anywhere in the API response.")
        return


    #----------------------------------------------------------------------------------------------

    documents = []
    metadatas = []
    ids = []

    # Flatten the structure
    for master in master_list:
        master_dmc_id = master.get("Master_DMC_id") 
        
        for destination in master.get("destinations", []):
            
            for dmc_node in destination.get("DMC", []):
                dmc_id = dmc_node.get("DMC_id")
                country = dmc_node.get("country", "").strip().lower()

                list_all_services = dmc_node.get("list_all_services", {})
                list_all_transport = dmc_node.get("list_all_transport", {})

                for pkg_idx, pkg in enumerate(dmc_node.get("packages", [])):
                    days_dict = pkg.get("days", {})
                    
                    for index_key, day_data in days_dict.items():
                        max_days = int(day_data.get("day", 1))

                        day_cities = day_data.get("cities", {})
                        primary_city = ""
                        if isinstance(day_cities, dict) and "0" in day_cities:
                            primary_city = day_cities["0"].get("city", "").strip().lower()

                        hotels_dict = day_data.get("hotels", {})
                        attractions_dict = day_data.get("attractions", {})
                        restaurants_dict = day_data.get("restaurants", {})
                        
                        transfers_dict = day_data.get("Transfer", {}) 
                        guides_dict = day_data.get("Guide", [])

                        hotel_names = [h.get("hotel_name", "") for h in hotels_dict.values() if isinstance(h, dict)]
                        attraction_names = [a.get("name", "") for a in attractions_dict.values() if isinstance(a, dict)]
                        
                        hotels_text = ", ".join(hotel_names) if hotel_names else "None specified"
                        attractions_text = ", ".join(attraction_names) if attraction_names else "None specified"

                        document = (
                            f"Premium travel package to {primary_city.title()}, {country.title()} for day {max_days}. "
                            f"Accommodation options include: {hotels_text}. "
                            f"Key attractions available: {attractions_text}."
                        )

                        metadata = {
                            "Master_DMC_id": master_dmc_id,
                            "DMC_id": dmc_id,
                            "country": country,
                            "city": primary_city, 
                            "max_days": max_days,
                            "index_key": index_key,
                            "raw_hotels": json.dumps(hotels_dict),
                            "raw_attractions": json.dumps(attractions_dict),
                            "raw_restaurants": json.dumps(restaurants_dict),
                            "raw_services": json.dumps(transfers_dict), 
                            "raw_activities": json.dumps(guides_dict),  
                            "raw_cities": json.dumps(day_cities),               
                            "raw_all_services": json.dumps(list_all_services),  
                            "raw_all_transport": json.dumps(list_all_transport) 
                        }

                        doc_id = f"dmc_{dmc_id}_{primary_city}_{max_days}_{pkg_idx}_{index_key}"

                        documents.append(document)
                        metadatas.append(metadata)
                        ids.append(doc_id)

    # 2. THE SAFETY NET: Check for 0 documents BEFORE saving to ChromaDB
    if len(documents) == 0:
        print("Warning: 0 packages were found in the API data.")
        print("Please check the Debug output above to see if the JSON structure changed!")
        return

    print(f" Embedding {len(documents)} daily legs into Vector DB...")
    collection.add(
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )
    print(" Embeddings successfully stored!")

if __name__ == "__main__":
    build_vector_db_from_api()