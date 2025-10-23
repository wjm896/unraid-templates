# Use a lightweight Python image
FROM python:3.11-slim

# Workdir
WORKDIR /app

# Copy project
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port
EXPOSE 5555

# Define environment variables (can be overridden in Unraid)
ENV BASE_DIR="/tv" \
    PROCESSED_DIR_FILE="/data/processed_directories.json" \
    PNG_FILE="plex.png" \
    DELUGE_HOST="localhost" \
    DELUGE_PORT=58846 \
    DELUGE_USER="localclient" \
    DELUGE_PASS="" \
    SONARR_URL="http://localhost:8989" \
    SONARR_API_KEY="" \
    SONARR_MIN_AGE=120

CMD ["python", "app.py"]
