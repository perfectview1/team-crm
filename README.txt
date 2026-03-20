Team CRM Anywhere Deploy Package

Files:
- app.py
- requirements.txt
- Procfile
- render.yaml
- .env.example

Quick deploy:
1. Put these files in a GitHub repo.
2. In Render, create a new Blueprint deploy from the repo.
3. Render will create the web service and PostgreSQL database.
4. Open the deployed URL.
5. Create your first account at /register.
6. Share the URL with your team.

Local run:
1. Create a PostgreSQL database.
2. Set DATABASE_URL and TEAM_CRM_SECRET.
3. pip install -r requirements.txt
4. python app.py
