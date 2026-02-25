import requests
import hashlib
import time

API_URL = "http://127.0.0.1:8002/api/v1/audit/evidence"

def send_test(name, content, tamper=False):
    # 1. Generate the original fingerprint
    clean_hash = hashlib.sha256(content.encode()).hexdigest()
    
    # 2. If we are simulating a breach, we "mess up" the hash
    final_hash = clean_hash if not tamper else "CORRUPT_HASH_DATA_999"
    
    payload = {
        "source_system": "Security-Test-Node",
        "payload_summary": name,
        "hash_sequence": final_hash
    }
    
    try:
        requests.post(API_URL, json=payload)
        status = "?? TAMPERED" if tamper else "?? SECURE"
        print(f"Sent {name} as {status}")
    except:
        print("Error: Is the Backend (uvicorn) running?")

if __name__ == "__main__":
    print("Sending test records to ACAP...")
    send_test("Valid_Invoice_001", "Amount: $500")
    time.sleep(2)
    send_test("Hacked_Payroll_Log", "Amount: $99,000", tamper=True)
