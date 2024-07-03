from pymongo import MongoClient


client = MongoClient("mongodb://localhost:27017")
db = client["book"]

# Define the aggregation pipeline
pipeline = [
    {
        '$lookup': {
            'from': "review",  
            'localField': "Title",  
            'foreignField': "Title",  
            'as': "review"  # Put the results in the review array
        }
    },
    {
        '$merge': {
            'into': "bookdata",  
            'on': "_id",  
            'whenMatched': "replace" # Replace the entire document when matched
        }
    }
]

# Execute the aggregation pipeline
db["bookdata"].aggregate(pipeline)

