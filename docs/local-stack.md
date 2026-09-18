# Local V2 stack

The local V2 stack contains two services:

- FastAPI for document analysis and underwriting calculations
- React/Vite dashboard served as a static web application

No SQL database is required.

## Start

Copy .env.example to .env and add an OpenAI API key if AI classification or
vision fallback is required.

Then run:

    docker compose up --build

Open:

- Dashboard: http://localhost:8080
- API docs: http://localhost:8000/docs
- API health: http://localhost:8000/health

## Document handling

The stateless API processes uploaded documents in memory and returns the
analysis directly to the client. The React dashboard can download the complete
analysis, including its audit manifest, as JSON.

Real bank statements and credit reports must not be committed to Git.

## OCR

The API container includes Tesseract English and French language support.
Native positioned PDF extraction is attempted first. OCR is used only when
enabled and native positioned words are unavailable. Vision fallback can then
be used for remaining unreadable pages when an OpenAI API key is configured.
