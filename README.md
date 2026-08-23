# Shopify Taxonomy Classifier

## Project Overview

The Shopify Taxonomy Classifier is an automated product classification system designed to categorize high volumes of e-commerce products directly into Shopify's standard taxonomy. It leverages Google Gemini AI alongside Django and Celery to ingest product data, parse attributes, predict categories, and extract key details, reducing hours of manual tagging work into an automated background process.

## Features

- **AI-Powered Categorization:** Maps products to one of the 14,606 official Shopify taxonomy categories with high accuracy.
- **Background Processing Pipeline:** Uses Celery and Redis to handle robust background classification with automatic retrying, rate limiting, and failure handling.
- **Modern Monitoring Dashboard:** A Bootstrap 5 UI displaying classification metrics, success rates, interactive Chart.js charts, and a real-time review queue.
- **Comprehensive API:** Exposes endpoints powered by Django REST Framework (DRF) for integration with other apps or automated headless ingestion.
- **Smart Taxonomy Caching:** Aggressively caches the 14k+ category mapping to avoid repetitive DB hits.
- **Hash-Based Idempotency:** Creates SHA-256 hashes for each product entry to prevent redundant identical classifications.
- **Human-In-The-Loop:** A user interface that identifies low-confidence results and flags them for manual review, enabling "Approve" or "Reject" via UI.

## Architecture

1. **Django Web Framework:** Handles ORM, models, database interactions, routing, and the MVC dashboard UI.
2. **Celery Task Queue:** Manages batching and heavy processing pipelines to prevent timeouts during LLM API interactions.
3. **Redis Broker:** Facilitates messaging between Django and Celery workers, and is also used for robust Taxonomy caching.
4. **Google GenAI / Gemini:** Analyzes product titles, descriptions, and materials via structured LLM prompt mapping to deduce categories.
5. **SQLite / PostgreSQL:** Stores product information, batches, statuses, and classification logs. (SQLite is used locally).
6. **Bootstrap 5 & Chart.js:** Front-end stack for interactive tables and visual reporting.

## Installation

1. **Clone the repository** and navigate to the root directory.
2. **Set up the virtual environment:**
   ```bash
   python -m venv venv
   .\venv\Scripts\activate  # Windows
   # source venv/bin/activate  # macOS/Linux
   ```
3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Environment Variables:**
   Create a `.env` file containing:
   ```env
   GEMINI_API_KEY=your_gemini_key
   SECRET_KEY=your_django_secret
   DEBUG=True
   ```
5. **Run Migrations:**
   ```bash
   python manage.py migrate
   ```
6. **Start Redis Server:** Ensure Redis is running on `localhost:6379`.
7. **Run Celery Worker:**
   ```bash
   celery -A config worker --loglevel=info -P solo
   ```
8. **Run Django Server:**
   ```bash
   python manage.py runserver
   ```

## API Documentation

The RESTful APIs are provided via Django REST Framework with OpenAPI schema configuration.

- `GET /api/products/` - List products (Paginated)
- `GET /api/classifications/` - List classification outputs
- `GET /api/batches/` - View system batches
- `GET /api/stats/` - Core system KPI metrics
- `POST /api/products/{id}/approve/` - Approve classification result
- `POST /api/products/{id}/reject/` - Reject classification result
- **Swagger UI:** `/api/docs/`
- **ReDoc:** `/api/redoc/`

## Dashboard Screenshots

*(Future versions will include screenshots here)*

- **Home Dashboard:** `/dashboard/`
- **Review Queue:** `/dashboard/review/`
- **Results Viewer:** `/dashboard/results/`
- **Batch Monitoring:** `/dashboard/batches/`
- **Product Details:** `/dashboard/product/<id>/`

## Future Improvements

- Add asynchronous WebSocket channels for real-time progress bar updates in UI.
- Introduce dynamic Shopify API Webhook integrations (auto-push classifications directly to Shopify store).
- Fine-tune custom ML categorization models as a fallback layer when LLM APIs rate limit.
