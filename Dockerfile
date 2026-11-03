FROM python:3.12-slim-bookworm

# Xvfb : écran virtuel pour faire tourner Chrome en mode « fenêtré » (moins détectable que le headless)
RUN apt-get update \
 && apt-get install -y --no-install-recommends xvfb xauth \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && playwright install --with-deps chrome

COPY app ./app
COPY static ./static

EXPOSE 8000
CMD ["xvfb-run", "-a", "--server-args=-screen 0 1366x768x24", \
     "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]