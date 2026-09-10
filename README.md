# ISR Repository

A comprehensive Django-based platform for managing, accessing, and analyzing research datasets. Built with modern web technologies and designed for researchers, data scientists, and academic institutions.


## 🛠️ Technology Stack

- **Backend**: Django 5.2.6
- **Database**: PostgreSQL 15 with PostGIS 3.3
- **Frontend**: Bootstrap 5.3.3, Bootstrap Icons
- **Authentication**: Django Allauth
- **Containerization**: Docker & Docker Compose
- **Web Server**: Nginx
- **Geospatial**: GDAL 3.6.2
- **Python**: 3.13

## 📋 Prerequisites

- Docker and Docker Compose
- Git

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd isr-repository
```

### 2. Environment Configuration

Create a `.env` file in the project root.

### 3. Build and Run

```bash
# Build and start all services
docker compose up --build -d

# Check service status
docker compose ps

# View logs
docker compose logs app
```

## 🏗️ Project Structure

```
isr-repository/
├── app/                          # Django application
│   ├── main/                     # Main Django project
│   │   ├── settings.py           # Django settings
│   │   ├── urls.py              # Main URL configuration
│   │   └── wsgi.py              # WSGI configuration
│   ├── pages/                    # Pages app
│   │   ├── views.py             # Page views
│   │   ├── urls.py              # Page URLs
│   │   └── models.py            # Page models
│   ├── user/                     # User management app
│   │   ├── views.py             # User views
│   │   ├── models.py            # User models
│   │   ├── forms.py             # User forms
│   │   └── urls.py              # User URLs
│   ├── templates/                # Django templates
│   │   ├── _base.html           # Base template
│   │   ├── home.html            # Home page
│   │   ├── account/             # Allauth templates
│   │   └── user/                # User templates
│   ├── static/                   # Static files
│   ├── media/                    # Media files
│   └── manage.py                 # Django management script
├── nginx/                        # Nginx configuration
│   ├── Dockerfile               # Nginx Dockerfile
│   └── nginx.conf               # Nginx configuration
├── docker compose.yml            # Docker Compose configuration
├── Dockerfile                    # Main application Dockerfile
├── entrypoint.sh                 # Container entrypoint script
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

## 🔧 Development

### Local Development Setup

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Database Setup**:
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```

3. **Run Development Server**:
   ```bash
   python manage.py runserver
   ```

### Docker Development

```bash
# Build and run in development mode
docker compose up --build

# Run specific service
docker compose up app

# Execute commands in container
docker compose exec app python manage.py migrate
docker compose exec app python manage.py createsuperuser

# Collect static files (for development)
docker compose exec app python manage.py collectstatic --noinput
```

## 🧪 Testing

The application includes comprehensive unit tests for all major features, including API key functionality.

```bash
# Run all tests
docker compose exec app python manage.py test

# Run tests with verbosity
docker compose exec app python manage.py test --verbosity=2
```

## 🗄️ Database

The application uses PostgreSQL with PostGIS extension for geospatial data support.

### Database Management

```bash
# Access database shell
docker compose exec db psql -U isruser -d isrrepository

# Create database backup
docker compose exec db pg_dump -U isruser isrrepository > backup.sql

# Restore database backup
docker compose exec -T db psql -U isruser -d isrrepository < backup.sql
```

### Database Admin (pgAdmin)

Access pgAdmin at http://localhost:8080:
- **Email**: admin@example.com
- **Password**: admin

## 📧 Email Configuration & Testing

The application includes comprehensive email functionality with debugging and testing capabilities.

### Email Features

- **Password Reset**: Custom branded HTML emails
- **Email Confirmation**: User account verification emails
- **Dataset Notifications**: Email alerts for dataset updates, new versions, and comments
- **Multilingual Support**: German and English email templates
- **Comprehensive Logging**: Detailed email operation logging

### Email Backend Configuration

The application automatically configures email backends based on environment:

- **Development**: Console backend (emails printed to console)
- **Production**: SMTP backend (real email sending)

### Testing Email Configuration

#### 1. Run Email Test Script

```bash
# Test email configuration
docker compose exec app python test_email.py
```

This script will:
- Display current email settings
- Test email sending functionality
- Verify SMTP configuration
- Provide troubleshooting guidance

#### 2. Test Email Notifications

```bash
# Test comment notification emails
docker compose exec app python manage.py shell -c "
from datasets.models import Dataset, Comment
from user.models import CustomUser
from datasets.views import send_comment_notification_email

# Create a test comment to trigger email notification
dataset = Dataset.objects.first()
user = CustomUser.objects.first()
if dataset and user:
    comment = Comment.objects.create(
        dataset=dataset,
        author=user,
        content='Test comment for email notification'
    )
    send_comment_notification_email(comment)
    comment.delete()
    print('Email notification test completed')
"
```

#### 3. Check Email Logs

```bash
# View email operation logs
docker compose exec app cat logs/email.log

# Monitor email logs in real-time
docker compose exec app tail -f logs/email.log
```

### Email Logging Features

The application provides comprehensive email logging:

- **Email Backend Logging**: Tracks all email sending operations
- **Notification Function Logging**: Detailed logging for dataset notifications
- **Template Rendering**: Logs email template rendering success/failure
- **User Preferences**: Tracks notification preferences
- **Success/Failure Tracking**: Monitors email delivery success rates

#### Log File Locations

- **`logs/email.log`**: Dedicated email operation logging
- **`logs/django.log`**: General application logging


## 🎨 Customization

### Site Configuration

The application uses environment variables to configure the site name and URL, which are used throughout the application for links, page titles, email templates, and front-end elements.

#### Environment Variables

- **`SITE_NAME`**: The name of the site displayed in the navbar, page titles, email templates, and footer. Default: `ISR Repository`
- **`SITE_URL`**: The base URL of the installation used for generating absolute links in emails and notifications. Default: `http://localhost:8000`

These variables are automatically available in all templates via the context processor as `{{ SITE_NAME }}` and `{{ SITE_URL }}`.

### Branding

The application uses custom ISR branding with the following color scheme:

```css
:root {
    --isr-primary: #0047BB;
    --isr-secondary: #001A70;
    --isr-accent: #92C1E9;
    --isr-primary-light: #0056d6;
    --isr-primary-dark: #003a99;
}
```

### Templates

Templates are located in `app/templates/` and use Django's template system with Bootstrap 5.


## 📊 Monitoring

### Logs

```bash
# View application logs
docker compose logs app

# View database logs
docker compose logs db

# View nginx logs
docker compose logs nginx

# Follow logs in real-time
docker compose logs -f app
```

### Health Checks

The application includes health checks for:
- Database connectivity
- Service availability
- Container status

## 🚀 Deployment

1. **Environment Variables**:
   - Set `DEBUG=False`
   - Configure production database
   - Set secure `DJANGO_SECRET_KEY`
   - Configure email settings

2. **Static Files**:
   ```bash
   # Collect static files (required for production)
   docker compose exec app python manage.py collectstatic --noinput
   
   # Or with verbosity for debugging
   docker compose exec app python manage.py collectstatic --noinput --verbosity=2
   ```

3. **Database Migration**:
   ```bash
   docker compose exec app python manage.py migrate
   ```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.