FROM python:3.11-slim

# Install cron
RUN apt-get update && apt-get install -y cron && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy all project files including src/, data/, summaries/, requirements.txt, etc.
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Add and register cron job
COPY crontab /etc/cron.d/cyprus-news-cron
RUN chmod 0644 /etc/cron.d/cyprus-news-cron && crontab /etc/cron.d/cyprus-news-cron