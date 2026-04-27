import json
import os
import chromadb
import shutil
from chromadb.utils import embedding_functions
from api_data import fetch_data

# 1. Initialize ChromaDB
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

def build_vector_db_from_json(json_filepath):
    print(f"Loading data from {json_filepath}...")
    
    with open(json_filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    documents = []
    metadatas = []
    ids = []

    # 2. Flatten the structure
    for master in data.get("Master_DMC", []):
        master_dmc_id = master.get("Master_DMC_id") # NEW: Grab Master ID
        
        for destination in master.get("destinations", []):
            dmc_id = destination.get("DMC_id")
            country = destination.get("country", "").strip().lower()

            for city_node in destination.get("cities", []):
                city = city_node.get("city", "").strip().lower()

                for pkg_idx, pkg in enumerate(city_node.get("packages", [])):
                    days_dict = pkg.get("days", {})
                    
                    for index_key, day_data in days_dict.items():
                        max_days = int(day_data.get("day", 1))

                        # 3. Read the raw nested dictionaries
                        hotels_dict = day_data.get("hotels", {})
                        attractions_dict = day_data.get("attractions", {})
                        restaurants_dict = day_data.get("restaurants", {})
                        activities_dict = day_data.get("activities", {})

                        # Extract names for the text document
                        hotel_names = [h.get("hotel_name", "") for h in hotels_dict.values()]
                        attraction_names = [a.get("name", "") for a in attractions_dict.values()]
                        
                        hotels_text = ", ".join(hotel_names) if hotel_names else "None specified"
                        attractions_text = ", ".join(attraction_names) if attraction_names else "None specified"

                        # 4. Build the Semantic Document
                        document = (
                            f"Premium travel package to {city.title()}, {country.title()} for day {max_days}. "
                            f"Accommodation options include: {hotels_text}. "
                            f"Key attractions available: {attractions_text}."
                        )

                        # 5. Build the Metadata (Using json.dumps to bypass ChromaDB limits)
                        metadata = {
                            "Master_DMC_id": master_dmc_id,
                            "DMC_id": dmc_id,
                            "country": country,
                            "city": city,
                            "max_days": max_days,
                            "index_key": index_key, # Stores "0", "1", "2"
                            "raw_hotels": json.dumps(hotels_dict),
                            "raw_attractions": json.dumps(attractions_dict),
                            "raw_restaurants": json.dumps(restaurants_dict),
                            "raw_activities": json.dumps(activities_dict)
                        }

                        doc_id = f"dmc_{dmc_id}_{city}_{max_days}_{pkg_idx}_{index_key}"

                        documents.append(document)
                        metadatas.append(metadata)
                        ids.append(doc_id)

    # 6. Push to Vector DB
    print(f" Embedding {len(documents)} master packages into Vector DB...")
    collection.add(
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )
    print(" Embeddings successfully stored!")

if __name__ == "__main__":
    build_vector_db_from_json("data.json") # Make sure this matches your filename