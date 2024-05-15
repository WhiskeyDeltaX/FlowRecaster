from pydantic import BaseModel, Field
from typing import List
from uuid import UUID, uuid4
from datetime import datetime

class Workspace(BaseModel):
    name: str
    date_created: datetime = None
    date_modified: datetime = None
    region: str = "ewr"
    uuid: str = None

class StreamServer(BaseModel):
    date_created: datetime = Field(default_factory=datetime.utcnow)
    date_modified: datetime = Field(default_factory=datetime.utcnow)
    region: str = None
    operating_system: str = None
    plan: str = None
    cores: int = None
    memory: int = None
    cost: float = None
    ip: str = None
    firewall_group: str = None
    hostname: str = None
    uuid: str = None
    workspace: str = None
    operational: bool = None
    label: str = None
    service_uuid: str = None
    vpc_id: str = None
    ip_block: str = None
    internal_ip: str = None
    os: str = None
    fqdn: str = None
    online: bool = False
    last_heartbeat: datetime = None
    last_boot: datetime = None
    first_heartbeat: datetime = None
    stream_key: str = None
    youtube_key: str = None
    noise_reduction: str = None
    is_youtube_streaming: bool = False

class ServerStatus(BaseModel):
    server_uuid: str
    date_created: datetime = Field(default_factory=datetime.utcnow)
    uuid:  str = None
    cpu_usage: float
    ram_usage: float
    bytes_sent: str
    bytes_recv: str
    selected_source: str
    youtube_key: str
    ffmpeg_alive: bool = False
    stream1_live: bool = False
    stream2_live: bool = False
    noise_reduction: str = None
    stream1_url: str = None
    stream2_url: str = None

from pydantic import BaseModel, Field, EmailStr
from typing import List, Dict
from datetime import datetime 

class User(BaseModel):
    email: str
    password: str  # In production, ensure this is hashed before storing
    # role: str = Field(..., pattern="^(viewer|manager|admin)$")
    workspaces: List[str] = None
    created_at: datetime = None
    updated_at: datetime = None

    class Config:
        json_schema_extra = {
            "example": {
                "email": "test@example.com",
                "password": "s3cr3t",  # Reminder: Hash this password in real scenarios
                "role": "manager",
                "workspaces": ["123", "456"]
            }
        }
