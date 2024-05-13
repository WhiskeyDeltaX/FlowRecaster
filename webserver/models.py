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
