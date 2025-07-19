FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy

# Install additional tools
RUN apt-get update && apt-get install -y cron ffmpeg

# Set workdir
WORKDIR /app

# Copy source code and configuration
COPY src/ src/
# COPY data/ data/
# COPY summaries/ summaries/
COPY requirements.txt .
COPY cyprus-news-cron /etc/cron.d/cyprus-news-cron

# Set permissions for cron job
RUN chmod 0644 /etc/cron.d/cyprus-news-cron

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run cron in foreground
CMD ["cron", "-f"]