FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY data/ ./data/
COPY config.py .
COPY indicators.py .
COPY strategy.py .
COPY risk_manager.py .
COPY risk_filter.py .
COPY dca_engine.py .
COPY modos.py .
COPY ai_regime.py .
COPY data_collector.py .
COPY metrics.py .
COPY backtester.py .
COPY monte_carlo.py .
COPY walk_forward.py .
COPY optimizer.py .
COPY market_regime.py .
COPY --from=frontend-builder /app/frontend/dist ./static/

EXPOSE 8000

CMD ["sh", "-c", "cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT"]
