import os
import psycopg2
from psycopg2 import sql
DB_PARAMS = {
    "dbname": os.getenv("POSTGRES_DB", "audit_vault"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", "password123"),
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": os.getenv("POSTGRES_PORT", "5444")
}

def reset_vault():
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()
        
        # This clears the table so your dashboard starts at 0
        cur.execute("TRUNCATE TABLE audit_logs RESTART IDENTITY;")
        conn.commit()
        
        print("? DATABASE RESET: Vault is now empty and ready for Live Evidence.")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"? CONNECTION ERROR: {e}")

if __name__ == "__main__":
    reset_vault()
