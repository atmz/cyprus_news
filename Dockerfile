FROM mcr.microsoft.com/playwright/python:v1.53.0-jammy

# Install cron, xvfb, ffmpeg
RUN apt-get update && apt-get install -y cron ffmpeg xvfb

# Set working directory
WORKDIR /app

# Copy application code and dependencies
COPY src/ src/
COPY requirements.txt .

# Copy and install cron job
COPY cyprus-news-cron /tmp/cyprus-news-cron
RUN crontab /tmp/cyprus-news-cron && rm /tmp/cyprus-news-cron

# Create log file
RUN touch /var/log/cyprus_news.log

# Copy secrets (env.sh must be executable and use KEY=VALUE format)
COPY secrets/env.sh secrets/env.sh
RUN chmod +x /app/secrets/env.sh

# Install Python packages and Playwright
RUN pip install --no-cache-dir -r requirements.txt && playwright install

# Run cron in foreground and tail log
CMD ["sh", "-c", "cron && tail -f /var/log/cyprus_news.log"]