from models import User
from fastapi import *
import security
from fastapi.security import OAuth2PasswordRequestForm
from pymongo import MongoClient
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
import uuid
from database import users_table

router = APIRouter()

@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(user: User):
    if await users_table.find_one({"email": user.email}):
        print("Email already exists")
        raise HTTPException(status_code=400, detail="Email already exists")
    user_dict = user.dict()
    print("User Dict", user_dict)
    user_dict['uuid'] = str(uuid.uuid4())
    user_dict['password'] = security.hash_password(user_dict['password'])  # Implement password hashing
    user_dict['created_at'] = datetime.now()  # Set the creation time
    user_dict['workspaces'] = []
    user_dict['role'] = "admin"
    await users_table.insert_one(user_dict)
    return {"message": "User created successfully"}

@router.get("/users/{email}")
async def read_user(email: str):
    user_data = await users_table.find_one({"email": email}, {"_id": 0, "password": 0})
    if user_data:
        return user_data
    raise HTTPException(status_code=404, detail="User not found")

@router.put("/users/{email}")
async def update_user(email: str, user: User):
    updated_data = user.dict(exclude_unset=True)
    updated_data["updated_at"] = datetime.now()
    if "password" in updated_data:
        updated_data['password'] = security.hash_password(updated_data['password'])
    result = await users_table.update_one({"email": email}, {"$set": updated_data})
    if result.modified_count:
        return {"message": "User updated successfully"}
    raise HTTPException(status_code=404, detail="User not found")

@router.delete("/users/{email}")
async def delete_user(email: str):
    result = await users_table.delete_one({"email": email})
    if result.deleted_count:
        return {"message": "User deleted successfully"}
    raise HTTPException(status_code=404, detail="User not found")

@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await users_table.find_one({"email": form_data.username})

    if not user or not security.verify_password(form_data.password, user['password']):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=99999) # security.ACCESS_TOKEN_EXPIRE_MINUTES
    access_token = security.create_access_token(
        data={"sub": user['email']}, expires_delta=access_token_expires
    )

    del user["password"]
    del user["_id"]

    return {"access_token": access_token, "token_type": "bearer", "user": user}
