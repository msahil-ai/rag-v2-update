from llama_index.core import SimpleDirectoryReader
import json
import os

OUTPUT_DIR = "email_json_extractions"

def load_all_emails():
    reader = SimpleDirectoryReader(
        input_dir=OUTPUT_DIR,
        recursive=False
    )

    documents = reader.load_data()

    emails = []

    for doc in documents:
        try:
            email_data = json.loads(doc.text)
            emails.append(email_data)
        except json.JSONDecodeError:
            print(f"Skipping invalid JSON: {doc.metadata}")

    return emails