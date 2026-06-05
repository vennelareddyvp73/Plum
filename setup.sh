#!/bin/bash
set -e

echo "Setting up Plum OPD Claims..."

# Backend
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -q -r requirements.txt
echo "Python dependencies installed."

# Database
DB_NAME=$(grep DATABASE_URL .env | sed 's/.*\///')
createdb "$DB_NAME" 2>/dev/null && echo "Database '$DB_NAME' created." || echo "Database '$DB_NAME' already exists."
cd ..

# Frontend
cd frontend
npm install -q
npm run build
cp -r dist ../backend/static
echo "Frontend built and copied to backend/static."
cd ..

echo ""
echo "Setup complete."
echo ""
echo "Start the server:"
echo "  cd backend && source venv/bin/activate"
echo "  uvicorn app.main:app --reload --port 8000"
echo ""
echo "Then open: http://localhost:8000"
echo "API docs:  http://localhost:8000/docs"
echo "Run tests: cd backend && python run_tests.py"