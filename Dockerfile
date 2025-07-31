FROM mcr.microsoft.com/playwright/python:v1.53.0-jammy

# Install additional tools
RUN apt-get update && apt-get install -y cron ffmpeg

# Set workdir
WORKDIR /app

# Copy source code and configuration
COPY src/ src/
# COPY data/ data/
# COPY summaries/ summaries/
COPY requirements.txt .
COPY cyprus-news-cron .

RUN crontab cyprus-news-cron

# Create log file
RUN touch /var/log/cyprus_news.log

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN playwright install --with-deps

# Run cron in foreground
CMD ["cron", "-f"]