# DegreeFinder

DegreeFinder helps applicants check their eligibility for university programs in Israel (Technion, Hebrew University, Ben-Gurion University) based on Bagrut and Psychometric scores.

## Features
- FastAPI backend with modular eligibility engine
- Institution-specific policies and loaders
- Frontend for user input and results display

## Setup
1. Install Python 3.10+
2. Install dependencies:
   ```bash
   pip install fastapi uvicorn pydantic pytest
   ```
3. Run backend:
   ```bash
   uvicorn backend.app:app --reload
   ```
4. Open `frontend/index.html` in your browser

## Testing
- Backend: Run `pytest` in the `backend/tests/` directory
- Frontend: See `frontend/TESTING.md` for manual test checklist

## Security & Improvements
- Add authentication for sensitive endpoints
- Validate all user inputs
- Restrict CORS origins
- Add more automated tests

## License
MIT

