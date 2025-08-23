FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy everything
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Default command (can be overridden by docker-compose command)
CMD ["python", "src/main.py"]
