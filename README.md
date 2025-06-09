# Schedule Generator AI Service

A FastAPI-based microservice that generates optimized work schedules using Google's Generative AI.

## Project Structure

```
app/
├── __init__.py
├── main.py                 # Application entry point
├── config.py              # Configuration settings
├── api/                   # API routes
│   └── routes/
│       ├── health.py      # Health check endpoint
│       └── schedule.py    # Schedule generation endpoints
├── models/                # Pydantic models
│   └── schedule.py        # Schedule-related schemas
├── services/              # Business logic
│   └── ai_service.py      # AI service integration
└── utils/                 # Utility functions
    └── validators.py      # Data validation functions
```

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the root directory with your Google AI API key:
```
GOOGLE_API_KEY=your_api_key_here
```

## Running the Application

Start the server:
```bash
python run.py
```

The API will be available at:
- API Documentation: http://localhost:8000/docs
- Alternative Documentation: http://localhost:8000/redoc
- Health Check: http://localhost:8000/health
- Schedule Generation: http://localhost:8000/schedule/generate

## API Endpoints

### Generate Schedule

`POST /schedule/generate`

Generates an optimized work schedule based on team and worker preferences.

Request body example:
```json
{
  "equipo": {
    "idEquipo": 1,
    "tipo": "regular",
    "nombre": "Team A",
    "diasActividad": "1111100",
    "horaInicioActividad": "09:00:00",
    "horaFinActividad": "17:00:00",
    "horasMinDiaria": 4,
    "horasMaxDiaria": 8
  },
  "scheduleTrabajadores": [
    {
      "id": "T001",
      "nombre": "John Doe",
      "preferencias": {
        "dias": {
          "Monday": {
            "horaInicio": "09:00:00",
            "horaFin": "13:00:00"
          }
        }
      },
      "restricciones": {
        "dias": {}
      },
      "horarioGeneral": {
        "horasSemanales": 20
      }
    }
  ]
}
```

## Error Handling

The API uses standard HTTP status codes:
- 200: Success
- 400: Bad Request (invalid input)
- 500: Internal Server Error

## Development

The project uses:
- FastAPI for the web framework
- Pydantic for data validation
- Google's Generative AI for schedule generation
- Structured logging with structlog 