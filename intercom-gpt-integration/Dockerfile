FROM python:3.9-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV POLLING_INTERVAL=60
ENV USE_SECRET_MANAGER=true
ENV PORT=8080

# Run the webhook server
CMD ["python", "webhook_server.py"] 
