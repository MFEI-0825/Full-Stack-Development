from pymongo import MongoClient

def custom_round(number):
    rounded_number = round(number * 2) / 2
    if rounded_number - int(rounded_number) == 0.5:
        if number - rounded_number >= 0.25:
            return rounded_number + 0.5
    return rounded_number


client = MongoClient('mongodb://localhost:27017/')
db = client['book'] 
books_collection = db['bookdata']  

def calculate_average_score(book):
    if 'review' in book and len(book['review']) > 0:
        total_score = sum(review['review/score'] for review in book['review'])
        average_score = total_score / len(book['review'])
        average_score = custom_round(average_score)
    else:
        average_score = 0  
    return average_score


for book in books_collection.find():
    average_score = calculate_average_score(book)
    books_collection.update_one({'_id': book['_id']}, {'$set': {'averageScore': average_score}})

print("Average score update completed.")


