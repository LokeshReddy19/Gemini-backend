from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import os
from pymongo import MongoClient
from textblob import TextBlob
from datetime import datetime
from bson import ObjectId
from collections import defaultdict
from fastapi.responses import JSONResponse

app = FastAPI()
# CORS configuration
origin = [

    "*"

]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origin,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],)

class SentimentRequest(BaseModel):
    text: str

class QueryModel(BaseModel):
    user_query:str

#Gemini API configuration

API_KEY='AIzaSyCT67i2JlhxygOkE-oidN9z31Ul6XH9tE8'
API_URL=f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={API_KEY}"



#MongoDB configuration
MONGO_URI =  "mongodb+srv://narralokeshreddy859:KDag76fPNbPKt0wx@analysis.6kz1qmc.mongodb.net/"

client = MongoClient(MONGO_URI)
db = client.get_database("gemini_analysis")
collection = db.get_collection("queries")


#Function defining
#Thus is for function for sentiment analysis

def sentiment_analysis(text: str) -> str:
    analysis = TextBlob(text)
    sentiment_score= analysis.sentiment.polarity
    sentiment = "Positive" if sentiment_score > 0 else "Negative" if sentiment_score < 0 else "Neutral"
    return sentiment_score, sentiment
    
    

#POST Method
@app.post("/sentiment")
async def analyze_sentiment(request:SentimentRequest):

    try:
        sentiment_score, sentiment = sentiment_analysis(request.text)
        return {
            "sentiment_score": sentiment_score,
            "sentiment": sentiment
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing sentiment: {str(e)}")

@app.post("/analyze")
async def analyze_text(request: QueryModel):
    user_query = request.user_query

    # Prepare the data in the proper API request format
    data = {
        "contents": [{"parts": [{"text": user_query}]}]
    }

    try:
        # Send request to Gemini API
        response = requests.post(API_URL, json=data)
        response.raise_for_status()  # Raise an error for 4xx/5xx responses

        # Extract AI response safely
        response_data = response.json()
        generated_text = (
            response_data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "No response received.")
        )

        # Get sentiment analysis
        sentiment_score, sentiment = sentiment_analysis(user_query)

        # Save the query to the database
        collection.insert_one({
            "user_query": user_query,
            "generated_text": generated_text,
            "sentiment_score": sentiment_score,
            "sentiment": sentiment,
            "timestamp": datetime.utcnow().isoformat()
        })

        return {
            "user_query": user_query,
            "generated_text": generated_text
        }

    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"API Request Failed: {str(e)}")

    except KeyError:
        raise HTTPException(status_code=500, detail="Unexpected API response format")
    
    
    # Check if the query exists in the database
    # query_data = collection.find_one({"user_query

#Query Category Distribution

@app.get("/query-category-distribution")
async def get_query_category_distribution():
    res = collection.find({})
    category_distribution = defaultdict(int)

    for doc in res:
        sentiment = doc.get("sentiment")
        category_distribution[sentiment] += 1

        formatted_data=[{"category": k, "count": v} for k,v in category_distribution.items()]
        return formatted_data



#Query Trends
@app.get("/query-trends")
async def get_query_trends():
    res = collection.find({})
    trends = defaultdict(int)

    for doc in res:
        timestamp = doc.get("timestamp")

        if isinstance(timestamp, datetime):
            date_str = timestamp.strftime('%Y-%m-%d')  # Extract date as string
            trends[date_str] += 1
        else:
            print(f"Skipping invalid timestamp: {timestamp}")

    return [{"date": date, "query_count": count} for date, count in trends.items()]
        
#User Engagement
@app.get("/user-engagement")
async def get_user_engagement():
    res = collection.find({})
    user_engagement = defaultdict(int)

    for doc in res:
        user_query = doc.get("user_query", "Unknown")  # Default to "Unknown" if key is missing
        user_engagement[user_query] += 1

    # Convert to a JSON-friendly format
    engagement_list = [{"user_query": key, "count": value} for key, value in user_engagement.items()]
    return engagement_list

    #return JSONResponse(content=engagement_list)



@app.get("/")
def home():
    return {"message": "Welcome to the Gemini Analysis API"}




if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8080, reload=True)