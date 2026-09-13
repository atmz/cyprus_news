FROM mcr.microsoft.com/playwright/python:v1.53.0-jammy

# Install additional tools
RUN apt-get update && apt-get install -y cron ffmpeg

# Node 20 + Claude Code CLI for the beta pipeline (claude -p backend)
# pinned; flags/envelope verified on 2.1.269
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g @anthropic-ai/claude-code@2.1.269

# Set workdir
WORKDIR /app

# Copy source code and configuration
COPY src/ src/
COPY config/ config/
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
ENV SUMMARIES_ROOT=/app/summaries
ENV SECRETS_ROOT=/app/secrets
ENV DISABLE_AUTOUPDATER=1
RUN playwright install --with-deps

# Run cron in foreground
CMD ["cron", "-f"]