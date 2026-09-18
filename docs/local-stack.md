# Local V2 stack

The V2 stack can now run as three services:

- PostgreSQL for application, ledger, metric, offer and audit records
- FastAPI for document analysis and underwriting services
- React/Vite dashboard served as a static web application

## Start

Copy .env.example to .env and add an OpenAI API key if AI classification is
required. The deterministic parser and rules still run without a key.

Then run:

    docker compose up --build

Open:

- Dashboard: http://localhost:8080
- API docs: http://localhost:8000/docs
- API health: http://localhost:8000/health

The API container initializes the current database schema on startup.

## Data durability

PostgreSQL data is stored in the postgres_data Docker volume. Uploaded
statements are stored in the statement_uploads volume in local development.

For a real deployment, set OBJECT_STORAGE_BACKEND=s3 and configure a private
S3-compatible bucket. Raw bank statements should not be committed to Git or
stored in a public web directory.
