from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from core import security

router = APIRouter()

import os

@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # Phase 2 Testing Credentials (from environment)
    expected_user = os.getenv("API_USER", "admin")
    expected_pass = os.getenv("API_PASSWORD", "Audit123!")
    
    if form_data.username == expected_user and form_data.password == expected_pass:
        token = security.create_access_token(data={"sub": form_data.username})
        return {"access_token": token, "token_type": "bearer"}
    
    raise HTTPException(status_code=401, detail="Invalid credentials")
