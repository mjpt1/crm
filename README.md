# سیستم CRM — جنگو

یک سیستم مدیریت ارتباط با مشتری (CRM) آماده برای محیط تولید، ساخته‌شده با Django 5، Django REST Framework، PostgreSQL، Redis و Celery.

---

## پشته فناوری

| لایه | فناوری |
|---|---|
| بک‌اند | Django 5.0.6 + DRF 3.15.2 |
| احراز هویت | simplejwt 5.3.1 |
| پایگاه داده | PostgreSQL 16 |
| کش / صف | Redis 7 + Celery 5 |
| پرداخت | درگاه زیبال |
| مستندات API | drf-spectacular (Swagger / ReDoc) |
| کانتینر | Docker + Gunicorn + Nginx |

---

## راه‌اندازی سریع — محیط توسعه

### ۱. کلون و تنظیم محیط

```bash
cp .env.example .env
# فایل .env را باز کنید و مقادیر SECRET_KEY، اطلاعات دیتابیس، آدرس Redis، کلیدهای زیبال و غیره را تکمیل کنید.
```

### ۲. ساخت و فعال‌سازی محیط مجازی

```bash
python -m venv venv
# ویندوز
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate
```

### ۳. نصب وابستگی‌ها

```bash
pip install -r requirements.txt
```

### ۴. اجرای migration ها

```bash
python manage.py makemigrations
python manage.py migrate
```

### ۵. ساخت کاربر مدیر ارشد

```bash
python manage.py createsuperuser
```

### ۶. راه‌اندازی سرور توسعه

```bash
python manage.py runserver
```

### ۷. (اختیاری) راه‌اندازی Celery worker و beat scheduler

```bash
# در یک ترمینال جداگانه
celery -A config worker -l info

# در ترمینال دیگری
celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

---

## محیط تولید — Docker Compose

### ۱. ساخت و راه‌اندازی تمام سرویس‌ها

```bash
docker-compose up --build -d
```

### ۲. اجرای migration ها داخل کانتینر

```bash
docker-compose exec web python manage.py migrate
```

### ۳. ساخت کاربر مدیر ارشد

```bash
docker-compose exec web python manage.py createsuperuser
```

### ۴. جمع‌آوری فایل‌های استاتیک

```bash
docker-compose exec web python manage.py collectstatic --no-input
```

---

## دیپلوی روی Vercel

این پروژه با فایل `vercel.json` برای اجرای Django WSGI روی Vercel آماده شده است.

متغیرهای محیطی پیشنهادی در Vercel:

```env
DJANGO_SETTINGS_MODULE=config.settings.production
SECRET_KEY=your-strong-secret-key
ALLOWED_HOSTS=.vercel.app,crm-jet-chi.vercel.app
CSRF_TRUSTED_ORIGINS=https://crm-jet-chi.vercel.app,https://*.vercel.app
```

نکات مهم:

- اگر PostgreSQL روی Vercel/سرویس خارجی ست نشده باشد، پروژه برای جلوگیری از کرش اولیه با SQLite موقت در `/tmp/db.sqlite3` بالا می‌آید.
- برای محیط واقعی production حتما دیتابیس خارجی (PostgreSQL) را تنظیم کنید.
- برای مشاهده خطای دقیق، از بخش Logs در داشبورد Vercel استفاده کنید.

---

## مستندات API

| آدرس | توضیح |
|---|---|
| `/api/docs/` | رابط کاربری Swagger |
| `/api/redoc/` | رابط کاربری ReDoc |
| `/admin/` | پنل مدیریت جنگو |

---

## ساختار پروژه

```
crm/
├── apps/
│   ├── users/          # احراز هویت، نقش‌ها، تیم‌ها، لاگ حسابرسی
│   ├── leads/          # مدیریت و تخصیص سرنخ‌ها
│   ├── sales/          # فاکتورها و پرداخت‌های دستی
│   ├── payments/       # یکپارچه‌سازی با درگاه زیبال
│   ├── reports/        # داشبورد و گزارش‌های عملکرد
│   ├── rewards/        # اهداف فروش و پاداش‌ها
│   ├── leave/          # درخواست مرخصی و تأییدیه
│   └── voip/           # کلیک برای تماس و لاگ مکالمات
├── config/
│   ├── settings/
│   │   ├── base.py
│   │   ├── development.py
│   │   └── production.py
│   ├── urls.py
│   ├── celery.py
│   ├── wsgi.py
│   └── asgi.py
├── templates/          # قالب‌های HTML جنگو (Bootstrap 5)
├── static/             # فایل‌های CSS / JS
├── nginx/              # تنظیمات Nginx
├── docker-compose.yml
├── Dockerfile
├── manage.py
├── requirements.txt
└── .env.example
```

---

## نقش‌های RBAC

| نقش | دسترسی‌ها |
|---|---|
| `super_admin` | دسترسی کامل به همه چیز |
| `sales_manager` | مدیریت تمام تیم‌ها، سرنخ‌ها و فاکتورها |
| `supervisor` | مدیریت سرنخ‌ها و فاکتورهای تیم خود |
| `sales_expert` | فقط سرنخ‌ها و فاکتورهای خود |
| `finance` | تأیید/رد فاکتورها، مشاهده پرداخت‌ها |

---

## اندپوینت‌های کلیدی API

```
POST   /api/v1/auth/login/                     # ورود با JWT
POST   /api/v1/auth/token/refresh/             # تجدید توکن دسترسی
POST   /api/v1/auth/logout/                    # ابطال توکن refresh

GET    /api/v1/leads/                          # لیست سرنخ‌ها (محدود به نقش/تیم)
POST   /api/v1/leads/{id}/update_status/       # تغییر وضعیت سرنخ
POST   /api/v1/leads/request_leads/            # تخصیص خودکار سرنخ‌های جدید به خود

GET    /api/v1/invoices/                       # لیست فاکتورها
POST   /api/v1/invoices/{id}/submit/           # ارسال برای تأیید
POST   /api/v1/invoices/{id}/approve/          # مالی/ادمین: تأیید
POST   /api/v1/invoices/{id}/reject/           # مالی/ادمین: رد

POST   /api/v1/payments/{id}/initiate/         # شروع پرداخت زیبال
GET    /api/v1/payments/callback/              # بازگشت مرورگر از زیبال

GET    /api/v1/reports/dashboard/              # خلاصه KPI
GET    /api/v1/reports/charts/                 # داده‌های نمودار Chart.js
GET    /api/v1/reports/performance/            # عملکرد کارشناسان
```
# crm
