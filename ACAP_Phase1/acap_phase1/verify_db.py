import psycopg2
from psycopg2 import sql

# Database connection details
DB_PARAMS = {
    "dbname": "postgres",
    "user": "postgres",
    "password": "your_password_here", # REPLACE WITH YOUR PASSWORD
    "host": "localhost",
    "port": "5432"
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
