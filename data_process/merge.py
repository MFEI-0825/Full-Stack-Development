from pymongo import MongoClient


client = MongoClient("mongodb://localhost:27017")
db = client["book"]
collection = db["bookdata"]

# Update the condition, here use an empty query object which matches all documents
query = {}

# Add a new empty array field
new_values = {"$set": {"review": []}}

# Update all documents
collection.update_many(query, new_values)

