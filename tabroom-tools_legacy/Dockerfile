# Stage 1: Builder
FROM python:3.10-slim AS builder
WORKDIR /app

# Install build dependencies and Chromium with its driver
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Stage 2: Final Image
FROM python:3.10-slim
WORKDIR /app

# Install runtime dependencies: Chromium is needed at runtime too.
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from the builder stage
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy the full application code (with the new directory structure)
COPY . .

# Declare /data as a volume for external storage persistence
VOLUME ["/data"]

# Expose port 8502 for Streamlit
EXPOSE 8502

# Set the entrypoint for Streamlit using port 8502 and disabling CORS for local testing.
ENTRYPOINT ["streamlit", "run", "app/app.py", "--server.port", "8502", "--server.enableCORS", "false"]