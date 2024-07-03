from pymongo import MongoClient

client = MongoClient('mongodb://localhost:27017/')
db = client['book']  
books_collection = db['bookdata'] 

# Iterate over each document
for book in books_collection.find({}):
    # Check every comment
    for review in book.get('review', []):
        # Remove the Id field
        review.pop('Id', None)
        # Rename User_id to userId
        if 'User_id' in review:
            review['userId'] = review.pop('User_id')
    
    # Update documentation
    books_collection.update_one({'_id': book['_id']}, {'$set': {'review': book['review']}})

print('Completed updates')
