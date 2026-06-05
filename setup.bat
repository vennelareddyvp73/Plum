@echo off
setlocal

echo Setting up Plum OPD Claims...

REM Backend
cd backend
python -m venv venv
call venv\Scripts\activate
pip install -q -r requirements.txt
echo Python dependencies installed.

REM Database — requires psql to be in PATH (installed with PostgreSQL)
for /f "tokens=2 delims=/" %%a in ('findstr "DATABASE_URL" .env') do set DB_NAME=%%a
psql -U postgres -c "CREATE DATABASE plum_claims;" 2>nul && echo Database created. || echo Database already exists.

cd ..

REM Frontend
cd frontend
call npm install --silent
call npm run build
xcopy /E /I /Y dist ..\backend\static >nul
echo Frontend built and copied to backend\static.

cd ..

echo.
echo Setup complete.
echo.
echo Start the server:
echo   cd backend
echo   venv\Scripts\activate
echo   uvicorn app.main:app --reload --port 8000
echo.
echo Then open: http://localhost:8000
echo API docs:  http://localhost:8000/docs
echo Run tests: cd backend ^&^& python run_tests.py