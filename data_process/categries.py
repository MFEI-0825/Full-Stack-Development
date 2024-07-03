import re
from pymongo import MongoClient
from tqdm import tqdm

client = MongoClient('mongodb://localhost:27017/')
db = client['book']  
books_collection = db['bookdata']  

# Get the total number of documents for setting the progress bar
total_books = books_collection.count_documents({})

# Create a progress bar with tqdm
for book in tqdm(books_collection.find({}), total=total_books, desc="Processing books"):
    categories_str = book.get('categories', "[]")
    
    try:
        # Extract categories using regular expressions
        categories_list = re.findall(r"'([^']*)'", categories_str)
        new_categories = []
        for category in categories_list:
            split_categories = [c.strip() for c in category.split('&')]
            new_categories.extend(split_categories)

        # Update the book's categories field
        books_collection.update_one({'_id': book['_id']}, {'$set': {'categories': new_categories}})
    except Exception as e:
        print(f"Error processing book ID {book['_id']}: {e}")

print('Completed updating categories')