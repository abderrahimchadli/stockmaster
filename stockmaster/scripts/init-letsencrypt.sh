#!/bin/bash

# This script sets up Let's Encrypt certificates for the StockMaster app
# Usage: ./init-letsencrypt.sh

# Exit on error
set -e

# Domain and email for Let's Encrypt registration
domains=(cloud-549585597.onetsolutions.network)
email="admin@stockmaster.com"  # Change to your email
staging=0  # Set to 1 for testing (avoids rate limits)

# Create certbot directory structure
echo "Creating certbot directory structure..."
mkdir -p ./certbot/conf/live/$domains
mkdir -p ./certbot/www

# Generate dummy certificate
echo "Generating dummy certificate for $domains..."
openssl req -x509 -nodes -newkey rsa:4096 -days 1 \
  -keyout ./certbot/conf/live/$domains/privkey.pem \
  -out ./certbot/conf/live/$domains/fullchain.pem \
  -subj "/CN=$domains"

echo "Starting nginx container..."
docker-compose up -d nginx

# Delete dummy certificate
echo "Deleting dummy certificate..."
rm -rf ./certbot/conf/live/$domains

# Request Let's Encrypt certificate
echo "Requesting Let's Encrypt certificate for $domains..."
if [ $staging = 1 ]; then
  staging_arg="--staging"
else
  staging_arg=""
fi

docker-compose run --rm certbot certonly \
  $staging_arg \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email $email \
  --agree-tos \
  --no-eff-email \
  -d $domains

echo "Reloading nginx..."
docker-compose exec nginx nginx -s reload

echo "Let's Encrypt initialization complete!"
echo "Certificate will be renewed automatically by the certbot service." 