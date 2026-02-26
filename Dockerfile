FROM python:3.11-slim

WORKDIR /app

# Install system deps for PyMySQL/cryptography
RUN apt-get update && apt-get install -y --no-install-recommends gcc libffi-dev && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && pip list

# Copy app code
COPY . .

# Run the app
CMD ["python", "run.py"]
