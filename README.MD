# Chartist

This application is the backend server for Chartist, a tool designed to analyze and visualize voting patterns of political parties based on their voting records.

## Features
- Import voting data from the API of the Dutch House of Representatives (Tweede Kamer)
- Run PCA (Principal Component Analysis) on voting data to identify patterns among political parties
- Provide an API to access processed data for frontend visualization


## Installation

```bash
# Install dependencies
pip install -r requirements/dev.txt

# run migrations
python manage.py migrate

# Load initial data
python manage.py import_data

# Run initial analysis
python manage.py run_analysis

# Create a superuser for admin access
python manage.py createsuperuser
```

## Starting the server:

```bash
python manage.py runserver
```

## Important urls
- API Root (Interactive): `http://127.0.0.1/8000/api/v1/`
- Admin Panel: `http://127.0.0.1/8000/admin/`
