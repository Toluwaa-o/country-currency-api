# Country Currency & Exchange API

A RESTful API built with FastAPI and MongoDB that fetches country data, exchange rates, and provides CRUD operations with automatic data caching.

## Features

- Fetch and cache country data from external APIs
- Real-time exchange rate integration
- Automatic GDP estimation
- Generate statistical summary images
- Advanced filtering and sorting
- Complete CRUD operations
- Fast async operations with MongoDB

## Installation

### 1. Clone or Download the Project

```bash
# Clone project
git clone https://github.com/Toluwaa-o/country-currency-api
```

### 2. Set Up Python Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

```bash
# Copy example env file
cp .env.example .env

# Edit .env with your settings
# For local MongoDB (default):
MONGODB_URL=mongodb://localhost:27017
DATABASE_NAME=countries_db
PORT=8000

# For MongoDB Atlas:
MONGODB_URL=mongodb+srv://username:password@cluster.mongodb.net/
DATABASE_NAME=countries_db
PORT=8000
```

### 6. Run the Application

```bash
# Start the server
python main.py

# Or using uvicorn directly
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at: `http://localhost:8000`

## API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API Endpoints

### 1. Refresh Country Data
```http
POST /countries/refresh
```
Fetches country data and exchange rates from external APIs, then caches in database.

**Response:**
```json
{
  "message": "Countries data refreshed successfully",
  "total_countries": 250,
  "timestamp": "2025-10-24T12:00:00"
}
```

### 2. Get All Countries
```http
GET /countries
```

**Query Parameters:**
- `region` - Filter by region (e.g., `Africa`, `Europe`)
- `currency` - Filter by currency code (e.g., `NGN`, `USD`)
- `sort` - Sort results: `gdp_desc`, `gdp_asc`, `population_desc`, `population_asc`

**Examples:**
```bash
# Get all African countries
GET /countries?region=Africa

# Get countries using Nigerian Naira
GET /countries?currency=NGN

# Get all countries sorted by GDP (descending)
GET /countries?sort=gdp_desc

# Combine filters
GET /countries?region=Africa&sort=gdp_desc
```

**Response:**
```json
[
  {
    "id": "507f1f77bcf86cd799439011",
    "name": "Nigeria",
    "capital": "Abuja",
    "region": "Africa",
    "population": 206139589,
    "currency_code": "NGN",
    "exchange_rate": 1600.23,
    "estimated_gdp": 25767448125.2,
    "flag_url": "https://flagcdn.com/ng.svg",
    "last_refreshed_at": "2025-10-24T12:00:00Z"
  }
]
```

### 3. Get Single Country
```http
GET /countries/{name}
```

**Example:**
```bash
GET /countries/Nigeria
```

### 4. Delete Country
```http
DELETE /countries/{name}
```

**Example:**
```bash
DELETE /countries/Nigeria
```

**Response:**
```json
{
  "message": "Country 'Nigeria' deleted successfully"
}
```

### 5. Get Status
```http
GET /status
```

**Response:**
```json
{
  "total_countries": 250,
  "last_refreshed_at": "2025-10-24T12:00:00Z"
}
```

### 6. Get Summary Image
```http
GET /countries/image
```

Returns a PNG image with:
- Total number of countries
- Top 5 countries by estimated GDP
- Last refresh timestamp

## Data Model

Each country document contains:

```json
{
  "id": "MongoDB ObjectId as string",
  "name": "Country name (required)",
  "capital": "Capital city (optional)",
  "region": "Geographic region (optional)",
  "population": 123456789,
  "currency_code": "NGN (optional)",
  "exchange_rate": 1600.23,
  "estimated_gdp": 25767448125.2,
  "flag_url": "https://flagcdn.com/ng.svg",
  "last_refreshed_at": "2025-10-24T12:00:00Z"
}
```

## GDP Calculation

```
estimated_gdp = (population × random(1000, 2000)) ÷ exchange_rate
```

A new random multiplier is generated on each refresh for each country.

## Error Handling

The API returns consistent JSON error responses:

**404 Not Found:**
```json
{
  "error": "Country not found"
}
```

**400 Bad Request:**
```json
{
  "error": "Validation failed",
  "details": {
    "currency_code": "is required"
  }
}
```

**503 Service Unavailable:**
```json
{
  "error": "External data source unavailable",
  "details": "Could not fetch data from restcountries.com"
}
```

**500 Internal Server Error:**
```json
{
  "error": "Internal server error"
}
```

## Testing with cURL

```bash
# Refresh data
curl -X POST http://localhost:8000/countries/refresh

# Get all countries
curl http://localhost:8000/countries

# Get African countries
curl "http://localhost:8000/countries?region=Africa"

# Get specific country
curl http://localhost:8000/countries/Nigeria

# Get status
curl http://localhost:8000/status

# Download summary image
curl http://localhost:8000/countries/image --output summary.png

# Delete country
curl -X DELETE http://localhost:8000/countries/Nigeria
```