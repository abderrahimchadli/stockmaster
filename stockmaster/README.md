# StockMaster - Shopify Inventory Management App

StockMaster is a powerful Shopify app for automating out-of-stock product management. Built with Django and integrated with Shopify's APIs, it helps merchants efficiently manage inventory levels and product visibility.

## Features

- Real-time inventory tracking across multiple locations
- Automated product visibility controls based on stock levels
- Smart redirects to maintain SEO value for out-of-stock products
- Notification system for inventory changes
- Analytics dashboard for stock performance insights
- Background synchronization with Shopify API

## Technology Stack

- Backend: Django 4.2+ with Python 3.12
- Frontend: HTML, CSS, JavaScript, Bootstrap
- API: Shopify GraphQL and REST APIs
- Authentication: OAuth 2.0 with Shopify
- Background Tasks: Celery with Redis
- Database: PostgreSQL

## Installation & Setup

1. Clone the repository
2. Create and activate a virtual environment
3. Install dependencies: `pip install -r requirements.txt`
4. Configure environment variables in `.env` file
5. Run migrations: `python manage.py migrate`
6. Start the server: `python manage.py runserver`

For automatic setup, run:
```
python auto_install.py
```

## Project Structure

- `apps/`: Django applications
- `config/`: Project settings and configuration
- `core/`: Core functionality and utilities
- `templates/`: HTML templates
- `static/`: Static assets

## License

This project is proprietary software. All rights reserved. 