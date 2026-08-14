# Reloading Nginx Configuration

If you're getting a "413 Request Entity Too Large" error, you need to reload nginx with the updated configuration.

## Quick Fix (Development)

If using `docker-compose.yml`:

```bash
# Restart nginx container
docker compose restart nginx

# Or rebuild nginx if config changed
docker compose up -d --build nginx
```

## Production Fix

If using `docker-compose.prod.yml`:

```bash
# Option 1: Rebuild and restart nginx
docker compose -f docker-compose.prod.yml up -d --build nginx

# Option 2: Use the update script
./update-nginx.sh

# Option 3: Manual rebuild and push (for container registry)
cd nginx
docker build -t isr-datasets-nginx:latest .
docker tag isr-datasets-nginx:latest ghcr.io/silvioheinze/isr-datasets-nginx:latest
docker push ghcr.io/silvioheinze/isr-datasets-nginx:latest
cd ..
docker compose -f docker-compose.prod.yml pull nginx
docker compose -f docker-compose.prod.yml up -d nginx
```

## Verify Configuration

After reloading, verify the configuration:

```bash
# Check nginx configuration is loaded
docker compose exec nginx nginx -T | grep client_max_body_size

# Should show: client_max_body_size 100G;
```

## Current Limits

- **Nginx**: 100GB (`client_max_body_size 100G`)
- **Django**: 100GB (`DATA_UPLOAD_MAX_MEMORY_SIZE` / `MAX_DATASET_UPLOAD_SIZE`)
- **Timeout**: 3600 seconds (1 hour)

Note: Files larger than `FILE_UPLOAD_MAX_MEMORY_SIZE` (10MB) are written to disk automatically during upload.
