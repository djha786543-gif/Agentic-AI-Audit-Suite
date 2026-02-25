from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from core import security

router = APIRouter()

@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # Phase 2 Testing Credentials
    if form_data.username == "admin" and form_data.password == "Audit123!":
        token = security.create_access_token(data={"sub": form_data.username})
        return {"access_token": token, "token_type": "bearer"}
    
    raise HTTPException(status_code=401, detail="Invalid credentials")
