FROM python:3.11-slim

# Install cron and any tools you need
RUN apt-get update && apt-get install -y cron

# Set workdir
WORKDIR /app

# Copy source code and data folders
# COPY src/ src/
# COPY data/ data/
# COPY summaries/ summaries/
COPY requirements.txt .
COPY cyprus-news-cron /etc/cron.d/cyprus-news-cron

# Set permissions for cron job
RUN chmod 0644 /etc/cron.d/cyprus-news-cron

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run cron in foreground
CMD ["cron", "-f"]
