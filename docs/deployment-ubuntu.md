# Deployment on Ubuntu

Target: one Ubuntu 22.04 or 24.04 server in a US region, running Postgres, gunicorn and nginx, with HTTPS and a weekly cron job. These steps have not been run on a server yet; check each command's output as you go.

Replace `leads.example.com` with your domain and `CHANGE_ME` values with your own.

## 1. Server preparation

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip postgresql nginx git ufw
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

The app needs Python 3.11 or newer. Check with `python3 --version`. Ubuntu 22.04 ships 3.10; on that release install a newer Python (for example from the deadsnakes PPA) and use it for the virtual environment, or use Ubuntu 24.04.

Create a user for the app:

```bash
sudo adduser --system --group --home /opt/nycleads nycleads
```

## 2. Database

```bash
sudo -u postgres psql
```

```sql
CREATE USER nycleads WITH PASSWORD 'CHANGE_ME_DB_PASSWORD';
CREATE DATABASE nycleads OWNER nycleads;
\q
```

Postgres listens on localhost only by default; leave it that way.

## 3. Code and environment

```bash
sudo -u nycleads git clone <your-repo-url> /opt/nycleads/app
cd /opt/nycleads/app
sudo -u nycleads python3 -m venv .venv
sudo -u nycleads .venv/bin/pip install -r requirements.txt
sudo -u nycleads cp .env.example .env
sudo -u nycleads nano .env
sudo chmod 600 .env
```

If you are not using git yet, copy the project folder with `scp` or `rsync` instead, leaving out `.venv` and `.env`.

Production `.env`:

```
SECRET_KEY=<long random string>
DEBUG=0
ALLOWED_HOSTS=leads.example.com
CSRF_TRUSTED_ORIGINS=https://leads.example.com
DATABASE_URL=postgres://nycleads:CHANGE_ME_DB_PASSWORD@localhost:5432/nycleads
SOCRATA_APP_TOKEN=<your token>
TARGET_ZIP_CODES=10027,10030
CLASS_B_LIST_FILE=/opt/nycleads/app/data/class-b-list.xls
```

Generate a secret key:

```bash
.venv/bin/python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Initialise:

```bash
sudo -u nycleads .venv/bin/python manage.py migrate
sudo -u nycleads .venv/bin/python manage.py collectstatic --noinput
sudo -u nycleads .venv/bin/python manage.py createsuperuser
sudo -u nycleads .venv/bin/python manage.py test leads
```

With `DEBUG=0` the app sets secure cookies, so log in over HTTPS only (after step 6).

## 4. Gunicorn service

Create `/etc/systemd/system/nycleads.service`:

```ini
[Unit]
Description=NYC leads web app
After=network.target postgresql.service

[Service]
User=nycleads
Group=nycleads
WorkingDirectory=/opt/nycleads/app
ExecStart=/opt/nycleads/app/.venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8001 --workers 3
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now nycleads
sudo systemctl status nycleads
```

## 5. Nginx

Create `/etc/nginx/sites-available/nycleads`:

```nginx
server {
    listen 80;
    server_name leads.example.com;

    location /static/ {
        alias /opt/nycleads/app/staticfiles/;
    }

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/nycleads /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

Nginx must be able to read the static files:

```bash
sudo chmod 755 /opt/nycleads /opt/nycleads/app
```

## 6. HTTPS

Point the domain's DNS A record at the server first.

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d leads.example.com
```

Certbot edits the nginx file and renews automatically. Open `https://leads.example.com` and log in.

## 7. Weekly pipeline

```bash
sudo -u nycleads crontab -e
```

```
0 8 * * 1 cd /opt/nycleads/app && .venv/bin/python manage.py run_pipeline >> /opt/nycleads/pipeline.log 2>&1
```

Cron uses the server's clock. `0 8 * * 1` on a UTC server is Monday 03:00 or 04:00 in New York. Run it once by hand first:

```bash
sudo -u nycleads /opt/nycleads/app/.venv/bin/python /opt/nycleads/app/manage.py run_pipeline
```

## 8. Backups

```bash
sudo mkdir -p /var/backups/nycleads && sudo chown postgres /var/backups/nycleads
sudo -u postgres crontab -e
```

```
30 2 * * * pg_dump nycleads | gzip > /var/backups/nycleads/nycleads-$(date +\%F).sql.gz
0 3 * * 0 find /var/backups/nycleads -name '*.sql.gz' -mtime +30 -delete
```

Copy backups off the server regularly. Restore with `gunzip -c <file> | sudo -u postgres psql nycleads`.

## 9. Updating

```bash
cd /opt/nycleads/app
sudo -u nycleads git pull
sudo -u nycleads .venv/bin/pip install -r requirements.txt
sudo -u nycleads .venv/bin/python manage.py migrate
sudo -u nycleads .venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart nycleads
```

## 10. Troubleshooting

| Symptom | Check |
| --- | --- |
| 502 Bad Gateway | `sudo systemctl status nycleads`, `sudo journalctl -u nycleads -n 50` |
| Page has no styling in admin | `collectstatic` was run; nginx `alias` path ends with `/`; folder permissions |
| "CSRF verification failed" on login | `CSRF_TRUSTED_ORIGINS` has the `https://` origin; restart the service |
| "DisallowedHost" | domain is in `ALLOWED_HOSTS` |
| Login does not stick | you are on `http://`; use `https://` |
| Pipeline fails with HTTP 429 | set `SOCRATA_APP_TOKEN` |
| Pipeline fails with HTTP 400 | a dataset field name changed; see `docs/data-sources.md` |
| Database connection refused | `sudo systemctl status postgresql`; password in `DATABASE_URL` |

## Security checklist

- [ ] `DEBUG=0` and a unique `SECRET_KEY`
- [ ] `.env` readable only by the app user
- [ ] Firewall allows only SSH and nginx
- [ ] Postgres not exposed to the internet
- [ ] SSH key login; password login disabled
- [ ] Strong password on every app account
- [ ] Backups copied off the server
