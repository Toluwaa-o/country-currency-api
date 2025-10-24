from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import httpx
import random
import os
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

load_dotenv()

app = FastAPI(title="Country Currency & Exchange API")

app.mount("/cache", StaticFiles(directory="cache"), name="cache")
    
MONGODB_URL = os.getenv("MONGODB_URL")
DATABASE_NAME = os.getenv("DATABASE_NAME")

client = AsyncIOMotorClient(MONGODB_URL)
db = client[DATABASE_NAME]
countries_collection = db.countries
metadata_collection = db.metadata

# Models
class Country(BaseModel):
    name: str
    capital: Optional[str] = None
    region: Optional[str] = None
    population: int
    currency_code: Optional[str] = None
    exchange_rate: Optional[float] = None
    estimated_gdp: Optional[float] = None
    flag_url: Optional[str] = None
    last_refreshed_at: datetime


class CountryResponse(Country):
    id: str = Field(alias="_id")

    class Config:
        populate_by_name = True


class StatusResponse(BaseModel):
    total_countries: int
    last_refreshed_at: Optional[datetime] = None


class ErrorResponse(BaseModel):
    error: str
    details: Optional[dict] = None



# Utility functions
async def fetch_countries_data():
    """Fetch country data from external API"""
    url = "https://restcountries.com/v2/all?fields=name,capital,region,population,flag,currencies"
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "External data source unavailable",
                    "details": f"Could not fetch data from restcountries.com: {str(e)}"
                }
            )


async def fetch_exchange_rates():
    """Fetch exchange rates from external API"""
    url = "https://open.er-api.com/v6/latest/USD"
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            return data.get("rates", {})
        except httpx.HTTPError as e:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "External data source unavailable",
                    "details": f"Could not fetch data from open.er-api.com: {str(e)}"
                }
            )


def calculate_estimated_gdp(population: int, exchange_rate: Optional[float]) -> Optional[float]:
    """Calculate estimated GDP"""
    if exchange_rate is None or exchange_rate == 0:
        return None
    random_multiplier = random.uniform(1000, 2000)
    return (population * random_multiplier) / exchange_rate


async def generate_summary_image(countries: List[dict], timestamp: datetime):
    """Generate summary image with country statistics"""
    width, height = 800, 600
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)
    
    try:
        title_font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
        header_font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        text_font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
    except:
        title_font = ImageFont.load_default()
        header_font = ImageFont.load_default()
        text_font = ImageFont.load_default()

    draw.text((50, 30), "Country Statistics Summary",
              fill='#2c3e50', font=title_font)

    draw.text(
        (50, 100), f"Total Countries: {len(countries)}", fill='#34495e', font=header_font)

    timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
    draw.text(
        (50, 140), f"Last Refreshed: {timestamp_str}", fill='#7f8c8d', font=text_font)

    draw.text((50, 200), "Top 5 Countries by Estimated GDP:",
              fill='#2c3e50', font=header_font)

    sorted_countries = sorted(
        [c for c in countries if c.get('estimated_gdp') is not None],
        key=lambda x: x.get('estimated_gdp', 0),
        reverse=True
    )[:5]

    y_position = 250
    for idx, country in enumerate(sorted_countries, 1):
        gdp_formatted = f"${country['estimated_gdp']:,.2f}"
        text = f"{idx}. {country['name']}: {gdp_formatted}"
        draw.text((70, y_position), text, fill='#34495e', font=text_font)
        y_position += 40

    os.makedirs("cache", exist_ok=True)
    img.save("cache/summary.png")


# Endpoints
@app.post("/countries/refresh")
async def refresh_countries():
    """Fetch and cache country data with exchange rates"""
    try:
        countries_data = await fetch_countries_data()
        exchange_rates = await fetch_exchange_rates()

        refresh_timestamp = datetime.utcnow()
        processed_countries = []

        for country_data in countries_data:
            currencies = country_data.get("currencies", [])
            currency_code = None
            exchange_rate = None
            estimated_gdp = 0

            if currencies and len(currencies) > 0:
                currency_code = currencies[0].get("code")
                if currency_code and currency_code in exchange_rates:
                    exchange_rate = exchange_rates[currency_code]
                    estimated_gdp = calculate_estimated_gdp(
                        country_data.get("population", 0),
                        exchange_rate
                    )

            country_doc = {
                "name": country_data.get("name"),
                "capital": country_data.get("capital"),
                "region": country_data.get("region"),
                "population": country_data.get("population", 0),
                "currency_code": currency_code,
                "exchange_rate": exchange_rate,
                "estimated_gdp": estimated_gdp,
                "flag_url": country_data.get("flag"),
                "last_refreshed_at": refresh_timestamp
            }

            await countries_collection.update_one(
                {"name": {
                    "$regex": f"^{country_data.get('name')}$", "$options": "i"}},
                {"$set": country_doc},
                upsert=True
            )

            processed_countries.append(country_doc)

        await metadata_collection.update_one(
            {"_id": "global"},
            {"$set": {"last_refreshed_at": refresh_timestamp}},
            upsert=True
        )

        await generate_summary_image(processed_countries, refresh_timestamp)

        return {
            "message": "Countries data refreshed successfully",
            "total_countries": len(processed_countries),
            "timestamp": refresh_timestamp
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={
                            "error": "Internal server error", "details": str(e)})


@app.get("/countries")
async def get_countries(
    region: Optional[str] = Query(None),
    currency: Optional[str] = Query(None),
    sort: Optional[str] = Query(None)
):
    """Get all countries with optional filters and sorting"""
    try:
        query = {}
        if region:
            query["region"] = {"$regex": f"^{region}$", "$options": "i"}
        if currency:
            query["currency_code"] = {
                "$regex": f"^{currency}$", "$options": "i"}

        sort_criteria = []
        if sort:
            if sort == "gdp_desc":
                sort_criteria = [("estimated_gdp", -1)]
            elif sort == "gdp_asc":
                sort_criteria = [("estimated_gdp", 1)]
            elif sort == "population_desc":
                sort_criteria = [("population", -1)]
            elif sort == "population_asc":
                sort_criteria = [("population", 1)]

        cursor = countries_collection.find(query)
        if sort_criteria:
            cursor = cursor.sort(sort_criteria)

        countries = await cursor.to_list(length=None)

        for country in countries:
            country["id"] = str(country.pop("_id"))

        return countries

    except Exception as e:
        raise HTTPException(status_code=500, detail={
                            "error": "Internal server error"})


@app.get("/countries/image")
async def get_summary_image():
    """Serve the generated summary image"""
    image_path = "cache/summary.png"

    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail={
                            "error": "Summary image not found"})

    return FileResponse(image_path, media_type="image/png")


@app.get("/countries/{name}")
async def get_country(name: str):
    """Get a single country by name"""
    try:
        country = await countries_collection.find_one(
            {"name": {"$regex": f"^{name}$", "$options": "i"}}
        )

        if not country:
            raise HTTPException(status_code=404, detail={
                                "error": "Country not found"})

        country["id"] = str(country.pop("_id"))
        return country

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={
                            "error": "Internal server error"})


@app.delete("/countries/{name}")
async def delete_country(name: str):
    """Delete a country by name"""
    try:
        result = await countries_collection.delete_one(
            {"name": {"$regex": f"^{name}$", "$options": "i"}}
        )

        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail={
                                "error": "Country not found"})

        return {"message": f"Country '{name}' deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={
                            "error": "Internal server error"})


@app.get("/status")
async def get_status():
    """Get API status with total countries and last refresh time"""
    try:
        total_countries = await countries_collection.count_documents({})

        metadata = await metadata_collection.find_one({"_id": "global"})
        last_refreshed = metadata.get(
            "last_refreshed_at") if metadata else None

        return {
            "total_countries": total_countries,
            "last_refreshed_at": last_refreshed
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail={
                            "error": "Internal server error"})


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Country Currency & Exchange API",
        "version": "1.0.0",
        "endpoints": {
            "POST /countries/refresh": "Refresh country data from external APIs",
            "GET /countries": "Get all countries (supports filters: ?region=Africa&currency=NGN&sort=gdp_desc)",
            "GET /countries/{name}": "Get single country by name",
            "DELETE /countries/{name}": "Delete country by name",
            "GET /status": "Get API status",
            "GET /countries/image": "Get summary statistics image"
        }
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT"))
    uvicorn.run(app, host="0.0.0.0", port=port)