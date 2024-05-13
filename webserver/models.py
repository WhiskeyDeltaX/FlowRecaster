from pydantic import BaseModel, Field
from uuid import UUID, uuid4
from datetime import datetime

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
    online: bool = False

    last_heartbeat: datetime = None
    last_boot: datetime = None
    first_heartbeat: datetime = None

class ServerStatus(BaseModel):
    server_uuid: str
    date_created: datetime = Field(default_factory=datetime.utcnow)
    uuid:  str = None
    cpu_usage: float
    ram_usage: float
    bytes_sent: int
    bytes_recv: int
    selected_source: str
    youtube_stream_key: str
    ffmpeg_active: bool = False
