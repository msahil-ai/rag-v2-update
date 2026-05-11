import os
import json

# Shuts off the telemetry warnings.
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

    # Strip wrapper if it exists
    if isinstance(data, dict) and "data" in data:
        data = data["data"]

    # THE RECURSIVE HUNTER
    def hunt_for_master_dmc(node):
        found_items = []
        if isinstance(node, dict):
            if "Master_DMC" in node:
                val = node["Master_DMC"]
                if isinstance(val, list):
                    found_items.extend(val)
                else:
                    found_items.append(val)
            for value in node.values():
                found_items.extend(hunt_for_master_dmc(value))
        elif isinstance(node, list):
            for item in node:
                found_items.extend(hunt_for_master_dmc(item))
        elif isinstance(node, str):
            if "Master_DMC" in node: 
                try:
                    parsed = json.loads(node)
                    found_items.extend(hunt_for_master_dmc(parsed))
                except Exception:
                    pass
        return found_items

    print("Hunting for Master_DMC packages...")
    master_list = hunt_for_master_dmc(data)

    if not master_list:
        print("Error: Could not find 'Master_DMC' anywhere in the API response.")
        return

    documents = []
    metadatas = []
    ids = []

    # Flatten the NEW Package-Level structure
    for master in master_list:
        master_dmc_id = master.get("Master_DMC_id") 
        
        for destination in master.get("destinations", []):
            for dmc_node in destination.get("DMC", []):
                
                dmc_id = dmc_node.get("DMC_id")
                dmc_email = dmc_node.get("DMC_email", "").strip().lower() # NEW: Capture the DMC Email
                country = dmc_node.get("country", "").strip().lower()

                list_all_services = dmc_node.get("list_all_services", {})
                list_all_transport = dmc_node.get("list_all_transport", {})

                # ---> NEW: We now loop through and embed WHOLE PACKAGES, not just days <---
                for pkg in dmc_node.get("packages", []):
                    package_id = pkg.get("package_id")
                    total_days = int(pkg.get("total_days", 3))
                    days_dict = pkg.get("days", {})
                    
                    # Extract all cities involved in this package for text search
                    package_cities = set()
                    for day_data in days_dict.values():
                        cities_data = day_data.get("cities", {})
                        for c_info in cities_data.values():
                            if isinstance(c_info, dict) and c_info.get("city"):
                                package_cities.add(c_info.get("city").strip().lower())
                    
                    cities_text = ", ".join(list(package_cities))

                    # The document now represents the ENTIRE package
                    document = f"Premium {total_days}-day travel package to {cities_text}, {country.title()}."

                    # Pack the ENTIRE package JSON into the metadata
                    metadata = {
                        "Master_DMC_id": master_dmc_id,
                        "DMC_id": dmc_id,
                        "DMC_email": dmc_email, # Critical for exact matching
                        "country": country,
                        "cities_included": cities_text, 
                        "total_days": total_days,
                        "package_id": package_id,
                        "raw_package": json.dumps(pkg), # Store the whole package!
                        "raw_all_services": json.dumps(list_all_services),  
                        "raw_all_transport": json.dumps(list_all_transport) 
                    }

                    doc_id = f"pkg_{dmc_id}_{package_id}"

                    documents.append(document)
                    metadatas.append(metadata)
                    ids.append(doc_id)

    if len(documents) == 0:
        print("Warning: 0 packages were found in the API data.")
        return

    print(f" Embedding {len(documents)} FULL PACKAGES into Vector DB...")
    collection.add(
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )
    print(" Embeddings successfully stored!")

if __name__ == "__main__":
    build_vector_db_from_api()