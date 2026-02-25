from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import psycopg2
from psycopg2.extras import RealDictCursor
from api.v1.endpoints import audit
from api.v1.endpoints import intelligence

app = FastAPI()

# Allow the website to talk to the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# REGISTER THE ROUTER HERE (This makes the Green POST box appear)
app.include_router(audit.router, prefix="/api/v1/audit", tags=["Audit"])

# REGISTER INTELLIGENCE LAYER (Auditor Intelligence endpoints)
app.include_router(intelligence.router, prefix="/api/v1/intelligence", tags=["Intelligence"])

@app.get("/api/v1/audit/vault")
async def get_vault_data():
    try:
        conn = psycopg2.connect(
            dbname="postgres", 
            user="postgres", 
            password="your_password", 
            host="localhost",
            port="5432"
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT id, source_system, hash_sequence FROM audit_logs")
        data = cur.fetchall()
        cur.close()
        conn.close()
        return data
    except Exception as e:
        print(f"Database Error: {e}")
        return []

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8005)
