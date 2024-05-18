# app/main.py
from fastapi import FastAPI, HTTPException, Depends, Request, Form
from pydantic import BaseModel
import requests
from typing import List, Dict, Any
from datetime import datetime, timedelta
import logging
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from pymongo import MongoClient
from fastapi import Query


logger = logging.getLogger(__name__)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

# Dummy data for historical prices
historical_data = {
    "XAU": [{"timestamp": datetime.now() - timedelta(days=i), "price": 1800 + i, "currency": "USD"} for i in range(30)],
    "XAG": [{"timestamp": datetime.now() - timedelta(days=i), "price": 25 + i * 0.1, "currency": "USD"} for i in range(30)],
    "XPT": [{"timestamp": datetime.now() - timedelta(days=i), "price": 950 + i * 2, "currency": "USD"} for i in range(30)],
    "XPD": [{"timestamp": datetime.now() - timedelta(days=i), "price": 2300 + i * 5, "currency": "USD"} for i in range(30)],
}

class HistoricalPrice(BaseModel):
    timestamp: datetime
    price: float
    currency: str


API_KEY = "goldapi-1uuxslwc511dk-io"
BASE_URL = "https://www.goldapi.io/api/"

class MetalPrice(BaseModel):
    metal: str
    price: float
    currency: str
    timestamp: datetime

users_db = {}

client = MongoClient("mongodb+srv://harvey:natividad@cluster0.xcod1uv.mongodb.net/mydatabase")
db = client.mydatabase
users_collection = db.users
conversions_collection = db.conversions

templates = Jinja2Templates(directory="templates")


class Conversion(BaseModel):
    metal: str
    amount: float
    currency: str
    price_per_piece: float
    total_price: float
    date: datetime


class User(BaseModel):
    username: str
    password: str

def get_metal_price(metal: str, currency: str = "USD"):
    url = f"{BASE_URL}{metal}/{currency}"
    headers = {
        "x-access-token": API_KEY,
        "Content-Type": "application/json"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return MetalPrice(metal=metal, price=data['price'], currency=currency, timestamp=datetime.now())
    else:
        raise HTTPException(status_code=500, detail="Error fetching data from API")
    
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/register", response_class=JSONResponse)
async def register(username: str = Form(...), password: str = Form(...)):
    if users_collection.find_one({"username": username}):
        raise HTTPException(status_code=400, detail="Username already registered")
    user_id = users_collection.insert_one({"username": username, "password": password}).inserted_id
    return JSONResponse(content={"message": "User registered successfully", "user_id": str(user_id)})

@app.post("/login", response_class=JSONResponse)
async def login(username: str = Form(...), password: str = Form(...)):
    user = users_collection.find_one({"username": username, "password": password})
    if not user:
        raise HTTPException(status_code=400, detail="Invalid username or password")
    return JSONResponse(content={"message": "Login successful", "user_id": str(user["_id"])})


@app.get("/prices/{metal}", response_model=MetalPrice)
def read_metal_price(metal: str, currency: str = "USD"):
    return get_metal_price(metal, currency)

@app.get("/historical/{metal}", response_model=List[MetalPrice])
def read_historical_prices(metal: str, start_date: datetime = Query(None), end_date: datetime = Query(None)):
    # Calculate the default start and end dates if not provided
    if not start_date:
        start_date = datetime.now() - timedelta(days=30)
    if not end_date:
        end_date = datetime.now()

    # Convert start_date and end_date to string format for the API call
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')

    url = f"{BASE_URL}{metal}/historical/{start_date_str}/{end_date_str}"
    headers = {
        "x-access-token": API_KEY,
        "Content-Type": "application/json"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        try:
            data = response.json()
            logger.info(f"Response data: {data}")  # Log the response data
            historical_prices = [
                MetalPrice(metal=metal, price=entry['price'], currency=entry['currency'], timestamp=datetime.strptime(entry['timestamp'], '%Y-%m-%d %H:%M:%S'))
                for entry in data
            ]
            return historical_prices
        except Exception as e:
            logger.error(f"Error parsing historical data response: {e}")
            raise HTTPException(status_code=500, detail="Error parsing historical data response")
    else:
        logger.error(f"Error fetching historical data from API: {response.text}")
        raise HTTPException(status_code=500, detail="Error fetching historical data from API")



@app.get("/convert/{metal}/{amount}", response_class=JSONResponse)
async def convert_price(metal: str, amount: float, currency: str = "USD"):
    try:
        # Get metal price
        metal_price = get_metal_price(metal, currency)

        # Calculate total price
        total_price = metal_price.price * amount

        # Create a Conversion object
        conversion = Conversion(
            metal=metal,
            amount=amount,
            currency=currency,
            price_per_piece=metal_price.price,
            total_price=total_price,
            date=datetime.now()
        )

        # Insert the conversion into MongoDB
        result = conversions_collection.insert_one(conversion.dict())

        return JSONResponse(content={"price": total_price, "currency": currency, "conversion_id": str(result.inserted_id)})
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error converting price")


@app.get("/last_conversions/{metal}", response_model=List[Conversion])
async def get_last_conversions(metal: str, amount: int = Query(..., gt=0)):
    # Query the database to get the last `amount` conversions for the specified metal
    last_conversions = list(conversions_collection.find({"metal": metal}).sort("date", -1).limit(amount))

    # If no conversions found, return 404 Not Found
    if not last_conversions:
        raise HTTPException(status_code=404, detail=f"No conversions found for metal {metal}")

    # Convert the database documents to Conversion objects
    conversion_objects = [
        Conversion(
            metal=conv["metal"],
            amount=conv["amount"],
            currency=conv["currency"],
            price_per_piece=conv["price_per_piece"],
            total_price=conv["total_price"],
            date=conv["date"]
        )
        for conv in last_conversions
    ]

    return conversion_objects

 
