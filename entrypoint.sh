#!/bin/sh
echo "Starting cron..."
service cron start
tail -f /var/log/wilma.log