from fastapi import APIRouter, Body, HTTPException, Depends, status, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import httpx
from models import StreamServer, ServerStatus
from security import get_current_user
from uuid import uuid4, UUID
import datetime
import os
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from database import stream_servers_table, users_table
import base64
from routers.sockets import manager
from utils import ser

# Define the user data script
user_data_script = """#!/bin/bash
wget https://raw.githubusercontent.com/WhiskeyDeltaX/FlowRecaster/main/streamserver/update.sh
chmod +x update.sh
./update.sh {uuid} {host_url} {record_name} {fqdn} {zone_id} {api_token} {server_ip} {stream_key} {youtube_key} > /stream_report.txt
"""

router = APIRouter()

VULTR_API_KEY = os.getenv('VULTR_API_KEY', "Z123123123123123123123123123")
SERVER_HOST_URL = os.getenv('SERVER_HOST_URL', "https://flowrecaster") # This is for the RTMP clients to broadcast back to us
SSH_KEY_PATH = os.getenv('SSH_KEY_PATH', './server@flowrecaster.com.pem')
VULTR_V4_SUBNET = os.getenv('VULTR_V4_SUBNET', "10.69.2.0")
PUBLIC_IP = os.getenv('PUBLIC_IP', "127.0.0.1")

# Cloudflare token
# https://dash.cloudflare.com/profile/api-tokens
CF_DOMAIN_NAME = os.getenv('CF_DOMAIN_NAME', "flowrecaster.com")
CF_API_TOKEN = os.getenv('CF_API_TOKEN', "asdfasdfasdfasdf")
CF_ZONE_ID = os.getenv('CF_ZONE_ID', "asdfasdfasdfasdf")

def generate_ssh_key():
    """Generate an RSA key pair and save it locally if not exists."""
    if not os.path.exists(SSH_KEY_PATH):
        key = rsa.generate_private_key(
            backend=default_backend(),
            public_exponent=65537,
            key_size=2048
        )
        private_key = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        public_key = key.public_key().public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH
        )
        with open(SSH_KEY_PATH, 'wb') as priv_file:
            priv_file.write(private_key)
        return public_key.decode('utf-8')
    else:
        with open(SSH_KEY_PATH, 'rb') as priv_file:
            key = serialization.load_pem_private_key(
                priv_file.read(),
                password=None,
                backend=default_backend()
            )
        public_key = key.public_key().public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH
        )
        return public_key.decode('utf-8')

async def get_or_create_vultr_ssh_key(public_key):
    """Check if the SSH key exists on Vultr, if not, create it."""
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {VULTR_API_KEY}"}
        print("HEADERS", headers)
        response = await client.get("https://api.vultr.com/v2/ssh-keys", headers=headers)
        response.raise_for_status()
        keys = response.json()
        for key in keys['ssh_keys']:
            if key['name'] == "server@flowrecaster.com":
                return key['id']
        
        # Key not found, create a new one
        response = await client.post(
            "https://api.vultr.com/v2/ssh-keys",
            headers=headers,
            json={
                "name": "server@flowrecaster.com",
                "ssh_key": public_key
            }
        )
        response.raise_for_status()
        key = response.json()
        return key['ssh_key']['id']

async def create_or_get_firewall_group(vpc_ip_block: str, subnet_size: int):
    """Check for the 'flowrecaster' firewall group and create it if it does not exist."""
    headers = {"Authorization": f"Bearer {VULTR_API_KEY}"}
    async with httpx.AsyncClient() as client:
        # Check existing firewall groups
        response = await client.get("https://api.vultr.com/v2/firewalls", headers=headers)
        response.raise_for_status()
        firewall_groups = response.json()['firewall_groups']
        firewall_group_id = None

        for group in firewall_groups:
            if group['description'] == "flowrecaster":
                firewall_group_id = group['id']
                break
        
        if not firewall_group_id:
            # Create a new firewall group
            create_response = await client.post(
                "https://api.vultr.com/v2/firewalls",
                headers=headers,
                json={"description": "flowrecaster"}
            )
            create_response.raise_for_status()
            firewall_group_id = create_response.json()['firewall_group']['id']

            # Add rules to the new firewall group
            rule_response = await client.post(
                f"https://api.vultr.com/v2/firewalls/{firewall_group_id}/rules",
                headers=headers,
                json={
                    "ip_type": "v4",
                    "protocol": "tcp",
                    "subnet": PUBLIC_IP,
                    "subnet_size": 32,
                    "port": "22",
                    "action": "accept"
                }
            )
            rule_response.raise_for_status()

        await ensure_firewall_rules(client, firewall_group_id, vpc_ip_block, subnet_size, headers)

        return firewall_group_id

async def ensure_firewall_rules(client, firewall_group_id, ip_block, subnet_size, headers):
    """Ensure that the firewall rules allow TCP and UDP on port 1385 for the given IP block."""
    rules_response = await client.get(f"https://api.vultr.com/v2/firewalls/{firewall_group_id}/rules", headers=headers)
    rules_response.raise_for_status()
    rules = rules_response.json()['firewall_rules']
    
    # Define rules to ensure based on IP and ports
    rules_to_ensure = [
        (22, 'tcp', PUBLIC_IP, '32'),   # SSH port for PUBLIC_IP
        (8453, 'tcp', ip_block, subnet_size),  # RTMP specific port, for given ip_block
        (80, 'tcp', ip_block, subnet_size),
        (443, 'tcp', ip_block, subnet_size),
        # (19751, 'tcp', ip_block, subnet_size)  # RTMP specific port, for given ip_block
    ]

    # Check and add missing rules
    for port, protocol, ip, subnet in rules_to_ensure:
        rule_exists = any(rule['ip_type'] == 'v4' and rule['subnet'] == ip and rule['subnet_size'] == subnet and
                          rule['port'] == str(port) and rule['protocol'] == protocol for rule in rules)
        
        if not rule_exists:
            await add_firewall_rule(client, firewall_group_id, ip, subnet, protocol, port, headers)

async def add_firewall_rule(client, firewall_group_id, ip_block, subnet_size, protocol, port, headers):
    """Add a firewall rule for the specified protocol and IP block."""
    await client.post(
        f"https://api.vultr.com/v2/firewalls/{firewall_group_id}/rules",
        headers=headers,
        json={
            "ip_type": "v4",
            "protocol": protocol,
            "subnet": ip_block,
            "subnet_size": subnet_size,  # Adjust subnet size based on your VPC configuration
            "port": port,
            "action": "accept"
        }
    )

async def get_or_create_vpc(region: str, description: str):
    """Check for an existing VPC with the given description or create one."""
    headers = {"Authorization": f"Bearer {VULTR_API_KEY}"}
    async with httpx.AsyncClient() as client:
        # Check existing VPC networks
        response = await client.get("https://api.vultr.com/v2/vpc2", headers=headers)
        response.raise_for_status()
        vpcs = response.json()['vpcs']
        print("VPCs found", vpcs)

        for vpc in vpcs:
            if vpc['description'] == description:
                return vpc
        
        # Create a new VPC
        create_response = await client.post(
            "https://api.vultr.com/v2/vpc2",
            headers=headers,
            json={
                "region": region,
                "description": description,
                "v4_subnet": VULTR_V4_SUBNET,
                "v4_subnet_mask": 24
            }
        )
        create_response.raise_for_status()
        vpc_data = create_response.json()
        print("Created vpc", vpc_data)
        return vpc_data['vpc']

@router.get("/streamservers/{workspace_id}")
async def get_streamservers(workspace_id: str, user: dict = Depends(get_current_user)):
    user_data = await users_table.find_one({"email": user}, {"_id": 0, "password": 0})
    
    if user_data and (user_data["role"] != "admin" and workspace_id not in user_data["workspaces"]):
        raise HTTPException(status_code=401, detail="Access to the workspace is denied")

    streamservers = await stream_servers_table.find({"workspace": str(workspace_id)}).to_list(None)
    return ser(streamservers)

@router.post("/streamservers/", status_code=status.HTTP_201_CREATED)
async def create_streamserver(server: StreamServer, user: dict = Depends(get_current_user)):
    user_data = await users_table.find_one({"email": user}, {"_id": 0, "password": 0})
    
    if user_data and (user_data["role"] != "admin" and server.workspace not in user_data["workspaces"]):
        raise HTTPException(status_code=401, detail="Access to the workspace is denied")

    server.uuid = str(uuid4())

    if not server.hostname:
        server.hostname = str(uuid4())[:8]

    if not server.stream_key:
        server.stream_key = server.uuid

    server.hostname = f"{server.hostname}.streams"
    server.fqdn = f"{server.hostname}.{CF_DOMAIN_NAME}"

    region = "ewr"
    public_key = generate_ssh_key()
    ssh_key_id = await get_or_create_vultr_ssh_key(public_key)
    print("SSH key id", ssh_key_id)
    firewall_group_id = await create_or_get_firewall_group("0.0.0.0", 0)
    print("FWG", firewall_group_id)
    plan = "vc2-1c-1gb"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.vultr.com/v2/instances",
            json={
                "region": region,
                "plan": plan,
                "os_id": "2136",  # Debian 12 x64
                "label": server.uuid,
                "backups": "disabled",
                "sshkey_id": [ssh_key_id],
                "firewall_group_id": firewall_group_id,
                "tags": [server.workspace],
                "user_data": base64.b64encode(user_data_script.format(
                    uuid=server.uuid, host_url=SERVER_HOST_URL,
                    record_name=f"{server.hostname}", fqdn=server.fqdn,
                    zone_id=CF_ZONE_ID, api_token=CF_API_TOKEN,
                    server_ip=PUBLIC_IP, stream_key=server.stream_key,
                    youtube_key=server.youtube_key or "None"
                ).encode()).decode('utf-8')
            },
            headers={"Authorization": f"Bearer {VULTR_API_KEY}"}
        )

        print (response.text)

        response.raise_for_status()
        server_data = response.json()

        server.plan = plan
        server.os = server_data['instance']['os']
        server.cores = server_data['instance']['vcpu_count']
        server.memory = server_data['instance']['ram']
        server.cost = 0.018
        server.operating_system = "Debian 12 x64"
        server.region = region
        server.date_created = datetime.datetime.now()
        server.operational = True
        server.date_modified = datetime.datetime.now()
        server.firewall_group = firewall_group_id
        # server.vpc_id = vpc["id"]
        # server.ip_block = vpc["ip_block"]

        server.ip = None
        server.online = False
        server.service_uuid = server_data['instance']['id']
        server.internal_ip = server_data['instance']['internal_ip']

        server.is_streaming = False

        await stream_servers_table.insert_one(server.dict())
        return ser(server.dict())

class UpdateStreamServer(BaseModel):
    label: Optional[str] = None
    stream_key: Optional[str] = None
    youtube_key: Optional[str] = None
    noise_reduction: Optional[str] = None

@router.put("/streamservers/{server_id}")
async def update_streamserver(server_id: str, update_data: UpdateStreamServer, user: dict = Depends(get_current_user)):
    server = await stream_servers_table.find_one({"uuid": str(server_id)})
    user_data = await users_table.find_one({"email": user}, {"_id": 0, "password": 0})

    if not server or (user_data["role"] != "admin" and server.workspace not in user_data["workspaces"]):
        raise HTTPException(status_code=404, detail="Server not found or access denied")

    update_data = update_data.dict(exclude_unset=True)

    if update_data:
        await stream_servers_table.update_one(
            {"uuid": str(server_id)},
            {"$set": update_data}
        )

        server["label"] = update_data["label"]
        server["stream_key"] = update_data["stream_key"]
        server["youtube_key"] = update_data["youtube_key"]
        server["noise_reduction"] = update_data["noise_reduction"]

    return ser(server)

async def delete_dns_record(client, hostname):
    # Retrieve the DNS record ID
    dns_records_response = await client.get(
        f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records",
        headers={"Authorization": f"Bearer {CF_API_TOKEN}"},
        params={"type": "A", "name": hostname}
    )
    dns_records_response.raise_for_status()
    dns_records = dns_records_response.json()

    if dns_records["result"]:
        dns_record_id = dns_records["result"][0]["id"]
        # Delete the DNS record
        delete_response = await client.delete(
            f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records/{dns_record_id}",
            headers={"Authorization": f"Bearer {CF_API_TOKEN}"}
        )
        delete_response.raise_for_status()
        return True
    else:
        return False

@router.delete("/streamservers/{server_id}")
async def delete_streamserver(server_id: str, user: dict = Depends(get_current_user)):
    server = await stream_servers_table.find_one({"uuid": str(server_id)})
    user_data = await users_table.find_one({"email": user}, {"_id": 0, "password": 0})

    if not server or (user_data["role"] != "admin" and server.workspace not in user_data["workspaces"]):
        raise HTTPException(status_code=404, detail="Server not found or access denied")

    async with httpx.AsyncClient() as client:
        if 'hostname' in server and server['hostname']:
            print("Deleting", server["hostname"])
    
        try:
            await delete_dns_record(client, server['hostname'])
        except Exception as e:
            print("DNS failed to delete", e)

        try:
            response = await client.delete(
                f"https://api.vultr.com/v2/instances/{server['service_uuid']}",
                headers={"Authorization": f"Bearer {VULTR_API_KEY}"}
            )
        except:
            print("Vultr failed to delete", e)

        await stream_servers_table.delete_one({"uuid": str(server_id)})
        return {"message": "Server deleted"}

@router.post("/streamservers/server_online")
async def server_online(request: Request):
    data = await request.json()
    server_uuid = data.get("server_uuid")
    
    print("UUID:", server_uuid, "data", data)

    if not server_uuid:
        raise HTTPException(status_code=400, detail="Server UUID is required.")

    # Retrieve the server document
    server = await stream_servers_table.find_one({"uuid": server_uuid})
    if not server:
        raise HTTPException(status_code=404, detail="Server not found.")

    print("HOST IP?", request.client.host)

    # Update server data
    update_data = {
        "$set": {
            "last_heartbeat": datetime.datetime.utcnow(),
            "last_boot": datetime.datetime.utcnow(),
            "ip": request.client.host,
            "online": True
        }
    }

    # If it's the first time this server is checking in
    if server.get("first_heartbeat") is None:
        update_data["$set"]["first_heartbeat"] = datetime.datetime.utcnow()

    # Update the server entry in MongoDB
    result = await stream_servers_table.update_one({"uuid": server_uuid}, update_data)

    server["last_heartbeat"] = update_data["$set"]["last_heartbeat"]
    server["last_boot"] = update_data["$set"]["last_boot"]
    server["ip"] = update_data["$set"]["ip"]
    server["online"] = update_data["$set"]["online"]

    if "first_heartbeat" in update_data["$set"]:
        server["first_heartbeat"] = update_data["$set"]["first_heartbeat"]

    print("Server Online", server)

    if result.modified_count == 1:
        await manager.broadcast({"type": "server_online", "data": ser(server)}, server["workspace"])
        return JSONResponse(status_code=200, content={"message": "Server status updated successfully."})
    else:
        return JSONResponse(status_code=500, content={"message": "Failed to update server status."})

@router.post("/streamservers/report_status")
async def report_status(status: ServerStatus):
    print("Checking", status.server_uuid)
    # Check if the server_uuid exists in the stream_servers_table
    server = await stream_servers_table.find_one({"uuid": status.server_uuid})
    if not server or not server["online"]:
        raise HTTPException(status_code=404, detail="Server UUID not found")

    # Prepare the status document to insert into MongoDB
    status = status.dict()
    status['date_created'] = datetime.datetime.utcnow()  # Add a timestamp
    status['uuid'] = str(uuid4())

    print("Logged status report", status)

    # Insert the status document into the stream_servers_status_table
    # stream_servers_status_table.insert_one(status)
    await manager.broadcast({"type": "status_report", "data": {"uuid": status["server_uuid"], "status": ser(status)}}, server["workspace"])

    return {"message": "Status reported successfully"}
