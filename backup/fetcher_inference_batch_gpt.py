import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from email_fetcher import fetch_next_pending_email

# -------------------------
# SETUP & AUTHENTICATION
# -------------------------
load_dotenv()

endpoint = os.getenv("OPENAI_ENDPOINT")
deployment_name = os.getenv("DEPLOYMENT_NAME")
api_key = os.getenv("OPENAI_API_KEY")

client = OpenAI(
    base_url=endpoint,
    api_key=api_key
)

# -------------------------
# PATHS
# -------------------------
output_folder = "outputs"  # Keeping it 'outputs' so your RAG pipeline finds them easily
os.makedirs(output_folder, exist_ok=True)

print("Starting live email processing mode.....\n")

# -------------------------
# JSON SCHEMA (SKIPPED)
# -------------------------

# -------------------------
# PROCESS EMAILS FROM INBOX
# -------------------------
counter = 1

while True:
    email_text = fetch_next_pending_email()

    if not email_text:
        print("......No more pending emails. Exiting.")
        break

    print(f"\n......Processing email #{counter} with gpt-4o-mini")

    # 3. Define the strict JSON schema in the System Prompt
    system_prompt = """You are an AI system specialized in extracting tour booking information from travel-related emails.

Your task is to read the email content and extract structured tour details.

The email may contain:
- spelling mistakes
- informal sentences
- incomplete information
- travel abbreviations (e.g., 5N/6D)

You must understand the intent and predict the most likely meaning.

Rules:
1. Always return ONLY JSON.
2. Do not return explanations.
3. If information is missing, return null.
4. Correct spelling mistakes in locations if possible.
5. Convert dates to YYYY-MM-DD format if available.
6. Passenger counts must be integers.
7. If only total passengers mentioned, assume adults unless specified.
8. If duration is mentioned (example: 5N/6D), calculate nights and days.
9. Identify destination even if misspelled.

Return JSON in this format:

{
  "tour_name": "",
  "destination_country": "",
  "destination_city": "",
  "departure_city": "",
  "start_date": "",
  "end_date": "",
  "duration_nights": null,
  "duration_days": null,
  "adults": null,
  "children": null,
  "infants": null,
  "hotel_category": "",
  "meal_plan": "",
  "budget": null,
  "currency": "",
  "special_requests": "",
  "confidence_score": 0.0
}

Confidence score must be between 0 and 1.

Never return anything outside JSON.
    """

    try:
        # 4. Call the OpenAI API
        response = client.chat.completions.create(
            model=deployment_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Here is the email to process:\n\n{email_text}"}
            ],
            response_format={ "type": "json_object" }, # Forces guaranteed JSON output
            temperature=0.0 # Keeps the AI deterministic and factual
        )
        
        # 5. Extract and parse the JSON directly
        json_text = response.choices[0].message.content
        extracted_data = json.loads(json_text)
        print("..... JSON extracted successfully")

    except Exception as e:
        extracted_data = {
            "raw_output": str(e),
            "error": "Failed to process with OpenAI"
        }
        print(f"..... JSON extraction failed: {e}")

    # 6. Save to the outputs folder exactly as before
    output_path = os.path.join(output_folder, f"email_{counter}.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(extracted_data, f, indent=4, ensure_ascii=False)

    print(f":: Saved: {output_path}")

    counter += 1

print("\n......All emails processed.")