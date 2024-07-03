import datetime
import jwt
from flask import g
from functools import wraps
from flask import Flask, request, jsonify, make_response 
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient
from bson import ObjectId
from bson.json_util import dumps
from flask_cors import CORS
from collections import Counter

app = Flask(__name__)
app.config['SECRET_KEY'] = 'myverycomplexandlongsecretkey123456789' # Key for JWT encryption
CORS(app) 

client = MongoClient("mongodb://127.0.0.1:27017")
db = client["book"]
bookdata = db["bookdata"]
users = db["users"]

def custom_round(number):
    # Round up to the nearest 0.5
    rounded_number = round(number * 2) / 2
    # Check if further rounding to whole numbers is required
    if rounded_number - int(rounded_number) == 0.5:
        if number - rounded_number >= 0.25:
            return rounded_number + 0.5
    return rounded_number

def calculate_average_score(book):
    if 'review' in book and len(book['review']) > 0:
        total_score = sum(review['review/score'] for review in book['review'])
        average_score = total_score / len(book['review'])
        # Using customized rounding functions
        average_score = custom_round(average_score)
    else:
        average_score = 0  # Default rating is 0 if there are no comments
    return average_score

def update_average_score(book_id):
    book = bookdata.find_one({'_id': book_id})
    if book:
        average_score = calculate_average_score(book)
        bookdata.update_one({'_id': book_id}, {'$set': {'averageScore': average_score}})

# Search Books
@app.route('/api/searchbooks', methods=['GET'])
def search_books():
    title_query = request.args.get('title', '')
    authors_query = request.args.get('authors', '')
    categories_query = request.args.getlist('categories')  # Get a list of categories
    sort_order = request.args.get('sort', None)
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 12))

    query_conditions = []
    if title_query:
        query_conditions.append({"Title": {"$regex": title_query, "$options": "i"}})
    if authors_query:
        regex_pattern = f"\\['.*{authors_query}.*'\\]"
        query_conditions.append({"authors": {"$regex": regex_pattern, "$options": "i"}})
    if categories_query:
        query_conditions.append({"categories": {"$in": categories_query}})

    combined_query = {"$and": query_conditions} if query_conditions else {}

    if sort_order == 'asc':
        books_cursor = bookdata.find(combined_query).sort('averageScore', 1)
    elif sort_order == 'desc':
        books_cursor = bookdata.find(combined_query).sort('averageScore', -1)
    else:
        books_cursor = bookdata.find(combined_query)

    skip = (page - 1) * per_page
    books_cursor.skip(skip).limit(per_page)

    books = []
    for book in books_cursor:
        book['_id'] = str(book['_id'])
        if 'review' in book:
            for review in book['review']:
                review['_id'] = str(review['_id'])
        books.append(book)

    return jsonify(books)


@app.route('/api/popular_categories', methods=['GET'])
def get_popular_categories():
    # Set the maximum number of categories to return
    limit = int(request.args.get('limit', 10))
    # Get all categories
    categories_cursor = bookdata.find({}, {'categories': 1, '_id': 0})
    all_categories = [category for doc in categories_cursor for category in doc.get('categories', [])]
    # Count the number of occurrences of each category and get the most common category
    most_common_categories = [category for category, count in Counter(all_categories).most_common(limit)]
    return jsonify({'categories': most_common_categories})

@app.route('/api/showbooks', methods=['GET'])
def get_books():
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 10))
    categories = request.args.getlist('categories')  # Get a list of category parameters
    skip = (page - 1) * per_page

    query = {}
    if categories:
        query['categories'] = {'$in': categories}  # If there is a category, add it to the query

    total = bookdata.count_documents(query)  # Get the total number of books based on the query
    books_cursor = bookdata.find(query).skip(skip).limit(per_page)
    books = [serialize_book(book) for book in books_cursor]
    return jsonify({'books': books, 'total': total})

def serialize_book(book):
    book['_id'] = str(book['_id'])
    if 'review' in book:
        book['review'] = [{**review, '_id': str(review['_id'])} for review in book['review']]
    return book

@app.route('/api/showbooks/<string:id>', methods=['GET'])
def show_one_book(id):
    try:
        # Try to convert a string ID to an ObjectId
        obj_id = ObjectId(id)
    except:
        # Returns an error message if the ID is not formatted correctly
        return make_response(jsonify({"error": "Invalid book ID"}), 400)

    # Query individual book data by ID
    book = bookdata.find_one({'_id': obj_id})
    if book is not None:
        # Convert ObjectId to string for JSON serialization
        book['_id'] = str(book['_id'])
        
        # If there is a comment, the ObjectId in the comment is also converted
        if 'review' in book:
            for review in book['review']:
                review['_id'] = str(review['_id'])
        
        # Returns book data and 200 OK status code
        return make_response(jsonify(book), 200)
    else:
        # Returns an error message and 404 status code if the book was not found
        return make_response(jsonify({"error": "Book not found"}), 404)
    
# JWT Decoding Decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split(" ")[1]

        if not token:
            return jsonify({'message': 'Token is missing!'}), 401

        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = users.find_one({'_id': ObjectId(data['userId'])})
        except:
            return jsonify({'message': 'Token is invalid!'}), 401

        g.user = current_user
        return f(*args, **kwargs)

    return decorated

# Add New Review
@app.route('/api/showbooks/<string:id>/comments', methods=['POST'])
@token_required
def add_comment(id):
    # Get user submitted data
    data = request.json

    user_record = g.user
    if not user_record:
        return jsonify({'error': 'User not found'}), 404
    
    # Search for book information
    book = bookdata.find_one({'_id': ObjectId(id)})
    if not book:
        return jsonify({'error': 'Book not found'}), 404

    # Get Book Title
    book_title = book.get('Title')
    profile_name = user_record.get('profileName')
    userId = user_record.get('userId')

    review_score = data.get('review/score')
    review_time = datetime.datetime.utcnow()
    review_summary = data.get('review/summary')
    review_text = data.get('review/text')

    comment = {
        "_id": ObjectId(),
        "userId": userId,
        "Title": book_title,
        "profileName": profile_name,
        "review/score": review_score,
        "review/time": review_time,
        "review/summary": review_summary,
        "review/text": review_text
    }
    # Update review data for books
    bookdata.update_one({'_id': ObjectId(id)}, {'$push': {'review': comment}})
    # Get updated book files
    updated_book = bookdata.find_one({'_id': ObjectId(id)})
    # Recalculate and update average ratings
    new_average_score = calculate_average_score(updated_book)
    bookdata.update_one({'_id': ObjectId(id)}, {'$set': {'averageScore': new_average_score}})
    return jsonify({'message': 'Comment added','commentId': str(comment['_id'])}), 200

# Delete user's own comments
@app.route('/api/user/comments/<comment_id>', methods=['DELETE'])
@token_required
def delete_user_comment(comment_id):
    user_id = g.user['userId']

    # Find Comments
    comment = bookdata.find_one({"review": {"$elemMatch": {"_id": ObjectId(comment_id)}}})

    # Check if the comment exists and belongs to the current user
    if comment and any(review.get('userId') == str(user_id) for review in comment.get('review', [])):
        bookdata.update_one({"_id": comment['_id']}, {"$pull": {"review": {"_id": ObjectId(comment_id)}}})
        return jsonify({'message': 'Comment deleted'}), 200
    else:
        return jsonify({'error': 'Comment not found or user not authorized to delete'}), 404

# Edit Review
@app.route('/api/user/comments/<comment_id>', methods=['PUT'])
@token_required
def update_user_comment(comment_id):
    user_id = g.user['userId']  # Get the ID of the currently logged in user
    updated_comment_data = request.json  # Get updated comment data

    # Get current time
    current_time = datetime.datetime.utcnow()

    # Finds the document containing the specified comment ID
    book_with_comment = bookdata.find_one(
        {"review._id": ObjectId(comment_id)}
    )

    if book_with_comment:
        # Iterating through the comments array
        for index, review in enumerate(book_with_comment.get("review", [])):
            if review.get("_id") == ObjectId(comment_id):
                if review.get("userId") == user_id:
                    # Constructing an update query
                    update_query = {"$set": {}}
                    for key, value in updated_comment_data.items():
                        # Ensure that the '_id' field is not updated
                        if key != '_id':
                            update_query["$set"][f"review.{index}.{key}"] = value

                    # Time to update comments
                    update_query["$set"][f"review.{index}.review/time"] = current_time

                    # Perform update operations
                    result = bookdata.update_one(
                        {"_id": book_with_comment["_id"]},
                        update_query
                    )

                    if result.modified_count > 0:
                        return jsonify({'message': 'Comments are updated'}), 200

                return jsonify({'error': 'User is not authorized to update this comment'}), 403

        return jsonify({'error': 'Specified comment not found'}), 404
    else:
        return jsonify({'error': 'No document containing this comment was found'}), 404

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data['userId']
    password = data['password']
    profileName = data['profileName']
    email = data['email']

    # Check if the username already exists
    if users.find_one({"userId": username}):
        return jsonify({'error': 'Username already exists'}), 409

    users.insert_one({
        "userId": username,
        "password": password,
        "profileName": profileName,
        "email":email,
        "star": []  # Create an empty star array
    })

    return jsonify({'message': 'User registered successfully'}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data['userId']
    password = data['password']

    user = users.find_one({"userId": username})
    if not user or user['password'] != password:
        return jsonify({'error': 'Invalid credentials'}), 401

    # Create JWT 
    token = jwt.encode({
        'userId': str(user['_id']),
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    }, app.config['SECRET_KEY'])

    return jsonify({'token': token}), 200

# Read user information
@app.route('/api/user', methods=['GET'])
@token_required
def get_user_info():
    user = g.user
    if 'password' in user:
        del user['password']

    if '_id' in user:
        user['_id'] = str(user['_id'])

   # Get details of books in user's favorites
    if 'star' in user:
        user['star_details'] = []
        for book_id in user['star']:
            book = bookdata.find_one({'_id': ObjectId(book_id)})
            if book:
                book['_id'] = str(book['_id'])
                # Convert ObjectId from comment to string
                if 'review' in book:
                    for review in book['review']:
                        review['_id'] = str(review['_id'])
                user['star_details'].append(book)

    return jsonify(user)



# User Review
@app.route('/api/user/comments', methods=['GET'])
@token_required
def get_user_comments():
    # Get the ID of the currently logged in user
    user_id = g.user['userId']

   # Use aggregation pipelines to filter reviews
    pipeline = [
        {"$unwind": "$review"},
        {"$match": {"review.userId": str(user_id)}},
        {"$project": {"review": 1, "_id": 0}}
    ]
    comments = list(bookdata.aggregate(pipeline))

    # Convert ObjectId to a string
    user_comments = []
    for comment in comments:
        if '_id' in comment['review']:
            comment['review']['_id'] = str(comment['review']['_id'])
        user_comments.append(comment['review'])

    return jsonify(user_comments)


@app.route('/api/user/star', methods=['POST'])
@token_required
def add_book_to_star():
    # Get user-submitted data
    data = request.json
    book_id = data.get('bookId')

    # Get the currently logged in user
    current_user = g.user
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    # Trying to add books to a user's favorites list
    result = users.update_one(
        {"_id": ObjectId(current_user['_id'])},
        {"$addToSet": {"star": book_id}}
    )

    # Check if books are actually added
    if result.modified_count > 0:
        return jsonify({'message': 'Book added to star list'}), 200
    else:
        # Check if the book is already in the favorites list
        user = users.find_one({"_id": ObjectId(current_user['_id']), "star": book_id})
        if user:
            return jsonify({'message': 'Book already in star list'}), 200
        else:
            return jsonify({'error': 'Unable to add book to star list'}), 400


@app.route('/api/user/star', methods=['DELETE'])
@token_required
def remove_book_from_star():
    # Get user-submitted data
    data = request.json
    book_id = data.get('bookId')

    # Get the currently logged in user
    current_user = g.user
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    # Trying to remove books from a user's favorites list
    result = users.update_one(
        {"_id": ObjectId(current_user['_id'])},
        {"$pull": {"star": book_id}}
    )

    # Check if books are actually deleted
    if result.modified_count > 0:
        return jsonify({'message': 'Book removed from star list'}), 200
    else:
        # Check if the book is no longer in the favorites list
        user = users.find_one({"_id": ObjectId(current_user['_id']), "star": book_id})
        if not user:
            return jsonify({'message': 'Book not in star list'}), 200
        else:
            return jsonify({'error': 'Unable to remove book from star list'}), 400

if __name__ == "__main__":
    app.run(debug=True)