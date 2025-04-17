FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the Python script and config
COPY wilma.py .
COPY wilmanotify.py .
COPY config.json .
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
RUN touch /var/log/wilma.log

# Install cron
RUN apt-get update && apt-get install -y cron && rm -rf /var/lib/apt/lists/*
COPY crontab /etc/crontab

# Set up cron job
RUN crontab /etc/crontab

# Start cron and keep container running
CMD ["/entrypoint.sh"]