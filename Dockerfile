FROM python:3.15-slim-bookworm

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gdal-bin \
        libgdal-dev \
        python3-dev \
        gcc \
        build-essential \
        libpq-dev \
        libgeos-dev \
        proj-bin \
        proj-data \
        libproj-dev \
        libxml2-dev \
        libxslt-dev \
        libffi-dev \
        zlib1g-dev \
        libjpeg-dev \
        tzdata \
        gettext \
    && rm -rf /var/lib/apt/lists/*

# Set timezone
ENV TZ=Europe/Vienna

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PYTHONPATH=/usr/src/app

# Set work directory
WORKDIR /usr/src/app

# Install dependencies
COPY ./requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create app user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy project
COPY ./app/ .

# Copy entrypoint script
COPY ./entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set ownership of the app directory to appuser
RUN chown -R appuser:appuser /usr/src/app

# Switch to appuser
USER appuser

# Set entrypoint
ENTRYPOINT ["/entrypoint.sh"]