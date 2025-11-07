import os
from pymongo import MongoClient

cluster=MongoClient(os.getenv('MONGO_CLUSTER_URI'))

db=cluster['jjinchin']
collection = db['chats']

collection.delete_many({})