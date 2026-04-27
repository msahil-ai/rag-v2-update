import shutil
import subprocess
import sys
import os
import time

OUTPUT_DIR = "./outputs"

def run_step(command, step_name):
    print(f"\nSTARTING: {step_name} \n")

    result = subprocess.run(
        [sys.executable] + command,
        capture_output=True,
        text=True
    )

    print(result.stdout)

    if result.returncode != 0:
        print(f"\n... ERROR in {step_name}")
        print(result.stderr)
        sys.exit(1)

    print(f"\nCOMPLETED: {step_name}\n")


if __name__ == "__main__":
    start_time = time.time()

    #if os.path.exists(OUTPUT_DIR): #(uncomment for production to clear old outputs, but keep for testing to preserve outputs)
            #shutil.rmtree(OUTPUT_DIR)

    # Step 1: Fetch emails + extract JSON via OpenAI
    run_step(
        ["fetcher_inference_batch_gpt.py"],
        "Email Fetching & Inference"
    )

    # Step 2: Embed the nested JSON into Vector DB (Replaces embed_DB.py)
    run_step(
        ["embed_json_data.py"],
        "Embedding Database Creation"
    )

    # Step 3: Run the new Matcher to print the variable
    run_step(
        ["rag_matcher.py"],
        "RAG Recommendation Pipeline"
    )

    # step 4: (Optional) Run API test to verify connectivity
    '''
    run_step(
        ["api_test.py"],
        "API Connectivity Test"
    )
    '''
            
    print("\n---------ALL PIPELINE STEPS COMPLETED SUCCESSFULLY------------.")

    end_time = time.time()
    print(f"Total time taken for the entire pipeline: {end_time - start_time:.2f} seconds")