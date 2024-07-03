from pymongo import MongoClient
import random
import string
from tqdm import tqdm

client = MongoClient('mongodb://localhost:27017/')
db = client['book'] 
books_collection = db['bookdata']  
users_collection = db['users']

# Extract all the different users
unique_users = {}
for book in books_collection.find({}, {"review": 1}):
    for review in book.get('review', []):
        user_id = review.get('userId')
        profile_name = review.get('profileName')
        if user_id and user_id not in unique_users:
            unique_users[user_id] = profile_name

# Iterate over users and add them to the users collection
for user_id, profile_name in tqdm(unique_users.items(), desc="Processing users"):
    # Generate random passwords
    password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))

    # Check if the user already exists, and if not, add the
    if not users_collection.find_one({"userId": user_id}):
        users_collection.insert_one({
            "userId": user_id,
            "profileName": profile_name,
            "password": password,
            "star": []  
        })

print('Completed updating users')
