from fastapi import APIRouter, Body, HTTPException, Depends, status
import httpx
from models import StreamServer
from security import get_current_user
from uuid import uuid4, UUID
import datetime
import os
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from database import stream_servers_table
import base64

# Define the user data script
user_data_script = """#!/bin/bash
wget https://raw.githubusercontent.com/WhiskeyDeltaX/FlowRecaster/main/streamserver/update.sh
chmod +x update.sh
./update.sh {uuid}
"""

# Encode the script
encoded_user_data = base64.b64encode(user_data_script.encode()).decode('utf-8')

router = APIRouter()

VULTR_API_KEY = os.getenv('VULTR_API_KEY', "Z123123123123123123123123123")
PUBLIC_IP = os.getenv('PUBLIC_IP', "127.0.0.1")
SSH_KEY_PATH = os.getenv('SSH_KEY_PATH', './server@flowrecaster.com.pem')
VULTR_V4_SUBNET = os.getenv('VULTR_V4_SUBNET', "10.69.2.0")

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

async def create_or_get_firewall_group(vpc_ip_block: str):
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

        await ensure_rtmp_firewall_rules(client, firewall_group_id, vpc_ip_block, headers)

        return firewall_group_id

async def ensure_rtmp_firewall_rules(client, firewall_group_id, ip_block, headers):
    """Ensure that the firewall rules allow TCP and UDP on port 1385 for the given IP block."""
    rules_response = await client.get(f"https://api.vultr.com/v2/firewalls/{firewall_group_id}/rules", headers=headers)
    rules_response.raise_for_status()
    rules = rules_response.json()['firewall_rules']

    # Check existing rules for the required access
    tcp_rule_exists = udp_rule_exists = False
    for rule in rules:
        if rule['ip_type'] == 'v4' and rule['subnet'] == ip_block and rule['port'] == "1385":
            if rule['protocol'] == 'tcp':
                tcp_rule_exists = True
            elif rule['protocol'] == 'udp':
                udp_rule_exists = True

    # Add missing rules
    if not tcp_rule_exists:
        await add_rtmp_firewall_rule(client, firewall_group_id, ip_block, 'tcp', headers)
    if not udp_rule_exists:
        await add_rtmp_firewall_rule(client, firewall_group_id, ip_block, 'udp', headers)

async def add_rtmp_firewall_rule(client, firewall_group_id, ip_block, protocol, headers):
    """Add a firewall rule for the specified protocol and IP block."""
    await client.post(
        f"https://api.vultr.com/v2/firewalls/{firewall_group_id}/rules",
        headers=headers,
        json={
            "ip_type": "v4",
            "protocol": protocol,
            "subnet": ip_block,
            "subnet_size": 24,  # Adjust subnet size based on your VPC configuration
            "port": "1385",
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
async def get_streamservers(workspace_id: UUID, user: dict = Depends(get_current_user)):
    if str(workspace_id) not in user['workspaces']:
        raise HTTPException(status_code=401, detail="Access to the workspace is denied")
    streamservers = await stream_servers_table.find({"workspace": str(workspace_id)}).to_list(None)
    return streamservers

@router.post("/streamservers/", status_code=status.HTTP_201_CREATED)
async def create_streamserver(server: StreamServer, user: dict = Depends(get_current_user)):
    if server.workspace not in user['workspaces']:
        raise HTTPException(status_code=401, detail="Access to the workspace is denied")

    server.uuid = str(uuid4())
    server.hostname = ""

    region = "ewr"
    public_key = generate_ssh_key()
    ssh_key_id = await get_or_create_vultr_ssh_key(public_key)
    vpc = await get_or_create_vpc(region, server.workspace)
    print("VPC", vpc)
    firewall_group_id = await create_or_get_firewall_group(vpc["ip_block"])
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
                "attach_vpc2": [vpc["id"]],
                "user_data": encoded_user_data = base64.b64encode(user_data_script.format(
                    uuid=server.uuid
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
        server.vpc_id = vpc["id"]
        server.ip_block = vpc["ip_block"]

        server.ip = server_data['instance']['main_ip']
        server.service_uuid = server_data['instance']['id']
        server.internal_ip = server_data['instance']['internal_ip']

        await stream_servers_table.insert_one(server.dict())
        return {"message": "Server created", "server": server}

@router.delete("/streamservers/{server_id}")
async def delete_streamserver(server_id: str, user: dict = Depends(get_current_user)):
    server = await stream_servers_table.find_one({"uuid": str(server_id)})
    if not server or server['workspace'] not in user['workspaces']:
        raise HTTPException(status_code=404, detail="Server not found or access denied")

    async with httpx.AsyncClient() as client:
        response = await client.delete(
            f"https://api.vultr.com/v2/instances/{server['service_uuid']}",
            headers={"Authorization": f"Bearer {VULTR_API_KEY}"}
        )
        response.raise_for_status()
        await stream_servers_table.delete_one({"uuid": str(server_id)})
        return {"message": "Server deleted"}
