from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient
import os

client = AsyncIOMotorClient(os.getenv('MONGO_URL', "mongodb://localhost:27017/"))
db = client.flowrecaster
stream_servers_table = db['stream_servers']
stream_servers_status_table = db['stream_servers_status']
