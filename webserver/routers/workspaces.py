from fastapi import APIRouter, Body, HTTPException, Depends, status, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from uuid import uuid4, UUID
import datetime
import os
from security import get_current_user
from database import workspaces_table, users_table
from models import Workspace
from utils import ser

router = APIRouter()

@router.post("/workspaces", response_description="Add new workspace")
async def create_workspace(workspace: Workspace, user: dict = Depends(get_current_user)):
    print("At post workspaces")
    workspace.uuid = str(uuid4())
    workspace.date_created = datetime.datetime.utcnow()
    workspace.date_modified = workspace.date_created
    workspace_dict = workspace.dict()

    result = await workspaces_table.insert_one(workspace_dict)
    if result.inserted_id:
        return JSONResponse(status_code=status.HTTP_201_CREATED, content=ser(workspace_dict))
    raise HTTPException(status_code=500, detail="Workspace could not be created")

@router.get("/workspaces", response_description="List all workspaces")
async def list_workspaces(user: dict = Depends(get_current_user)):
    workspaces = await workspaces_table.find({}).to_list(None)
    return ser(workspaces)

@router.get("/workspaces/{workspace_uuid}", response_model=Workspace, response_description="Get a single workspace")
async def get_workspace(workspace_uuid: str, user: dict = Depends(get_current_user)):
    # Assuming MongoDB with Motor or similar async DB client
    workspace = await workspaces_table.find_one({"uuid": workspace_uuid})
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace

@router.put("/workspaces/{workspace_id}", response_description="Update a workspace")
async def update_workspace(workspace_id: str, workspace: Workspace, user: dict = Depends(get_current_user)):
    user_data = await users_table.find_one({"email": user}, {"_id": 0, "password": 0})

    print("user Data", user_data, user_data["role"] != "admin")

    if user_data and (user_data["role"] != "admin" and workspace_id not in user_data["workspaces"]):
        raise HTTPException(status_code=401, detail="Access to the workspace is denied")

    workspace.date_modified = datetime.datetime.utcnow()
    workspace_dict = {k: v for k, v in workspace.dict().items() if v is not None}

    result = await workspaces_table.update_one({"uuid": workspace_id}, {"$set": workspace_dict})
    if result.modified_count == 1:
        updated_workspace = await workspaces_table.find_one({"uuid": workspace_id})
        return ser(updated_workspace)
    raise HTTPException(status_code=404, detail="Workspace not found")

@router.delete("/workspaces/{workspace_id}", response_description="Delete a workspace")
async def delete_workspace(workspace_id: str, user: dict = Depends(get_current_user)):
    if str(workspace_id) not in user['workspaces']:
        raise HTTPException(status_code=401, detail="Access to the workspace is denied")

    result = await workspaces_table.delete_one({"uuid": workspace_id})
    if result.deleted_count == 1:
        return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content={"message": "Workspace deleted"})
    raise HTTPException(status_code=404, detail="Workspace not found")
