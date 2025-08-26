FROM python:3.11-slim

WORKDIR /app

# Copy all the required project directories
COPY ./python_integration /app/python_integration
COPY ./google_api /app/google_api
COPY ./llm_integration /app/llm_integration

# Install Python dependencies from the correct location
RUN pip install --no-cache-dir -r /app/python_integration/requirements.txt

# Set the command to run the application
CMD ["python", "/src/main.py"]
