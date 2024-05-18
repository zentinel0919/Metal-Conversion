# app/main.py
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
import requests
from typing import List
from datetime import datetime
import logging
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

API_KEY = "goldapi-3mt0vslwbo5vdq-io"
BASE_URL = "https://www.goldapi.io/api/"

class MetalPrice(BaseModel):
    metal: str
    price: float
    currency: str
    timestamp: datetime

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
async def read_root():
    with open("templates/index.html", "r") as file:
        return file.read()

@app.get("/prices/{metal}", response_model=MetalPrice)
def read_metal_price(metal: str, currency: str = "USD"):
    return get_metal_price(metal, currency)

@app.get("/historical/{metal}", response_model=List[MetalPrice])
def read_historical_prices(metal: str, days: int = 30):
    url = f"{BASE_URL}{metal}/historical/{days}"
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
                MetalPrice(metal=metal, price=entry['price'], currency=entry['currency'], timestamp=datetime.strptime(entry['time'], '%Y-%m-%d %H:%M:%S'))
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
        metal_price = get_metal_price(metal, currency)
        converted_price = metal_price.price * amount  # Apply conversion logic here
        return JSONResponse(content={"price": converted_price, "currency": currency})
    except Exception as e:
        logger.error(f"Error converting price: {e}")
        raise HTTPException(status_code=500, detail="Error converting price")
