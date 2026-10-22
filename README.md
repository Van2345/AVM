# Assistance and Volunteer Management

The application backend is Django. It keeps the existing browser interface and
provides JSON endpoints for requester, volunteer, and administrator workflows.
GitHub Pages cannot run Django; deploy the app to a Python host instead. The
included Render Blueprint creates a Django web service and a fresh PostgreSQL
database.

## Run locally

Requirements: Python 3.11 or later.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

The development server is available at <http://127.0.0.1:8000/>. A
superuser created with `createsuperuser` is given the administrator role.
Public registration creates requester accounts; create volunteer accounts
from the administrator dashboard.

For local development, Django uses SQLite by default. To use PostgreSQL or
another supported database, set `DATABASE_URL`.

## Publish the source to GitHub

After reviewing the changes, commit and push them to the existing `origin`
remote:

```powershell
git add -A
git commit -m "Convert assistance app to Django"
git push origin main
```

These commands are documented for later; this workspace has not been pushed.

## Deploy from GitHub with Render

1. Push this project to a GitHub repository.
2. In Render, choose **New > Blueprint** and select the repository containing
   `render.yaml`.
3. Review and apply the Blueprint. It creates a web service and a new database.
4. Wait for the build to finish, then open the service URL and register a
   requester account.
5. Create the first administrator through Render's Shell:

   ```sh
   python manage.py createsuperuser
   ```

   Set its username, full name, email, and a strong password. The command sets
   the administrator role.

The Blueprint sets `DJANGO_SECRET_KEY` and `DATABASE_URL`. Do not put secrets,
production database credentials, or real user data in the repository. The
initial deployment uses a fresh database; records in the former XAMPP/MySQL
database are not imported.

## Operations

- Django admin: `/django-admin/`
- Static files are collected during the Render build and served by WhiteNoise.
- Set `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` if using a
  different domain or host.
- Run `python manage.py migrate` after pulling any future database model
  changes.
