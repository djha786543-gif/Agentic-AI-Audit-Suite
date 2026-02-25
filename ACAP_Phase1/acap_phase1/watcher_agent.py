import os
import time
import hashlib
import requests
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# --- CONFIGURATION ---
# Target aligned to Port 8002 to match the Backend Engine
API_URL = "http://127.0.0.1:8005/api/v1/audit/evidence/"
WATCH_DIRECTORY = "./audit_logs"

class AuditHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            self.process_file(event.src_path)

    def process_file(self, file_path):
        print(f"[DETECTED] New file: {file_path}")
        
        # Buffer to allow Windows to complete the file write process
        time.sleep(1)
        
        try:
            with open(file_path, "rb") as f:
                file_content = f.read()
                sha256_hash = hashlib.sha256(file_content).hexdigest()

            payload = {
                "source_system": "WATCHER_NODE_01",
                "hash_sequence": sha256_hash,
                "metadata": {"file_name": os.path.basename(file_path)}
            }

            response = requests.post(API_URL, json=payload, timeout=10)
            if response.status_code == 200:
                print(f"[SUCCESS] File sealed and sent to Vault: {os.path.basename(file_path)}")
            else:
                print(f"[ERROR] Vault rejected data. Status Code: {response.status_code}")

        except Exception as e:
            print(f"[ERROR] Processing failed: {e}")

if __name__ == "__main__":
    if not os.path.exists(WATCH_DIRECTORY):
        os.makedirs(WATCH_DIRECTORY)

    event_handler = AuditHandler()
    observer = Observer()
    observer.schedule(event_handler, WATCH_DIRECTORY, recursive=False)
    
    print("-" * 50)
    print("ACAP WATCHER AGENT ACTIVE")
    print(f"Monitoring: {os.path.abspath(WATCH_DIRECTORY)}")
    print(f"Target API: {API_URL}")
    print("-" * 50)
    
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
