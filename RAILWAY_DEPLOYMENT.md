# Railway deployment

## 1. Create Railway project
Create a Railway project and add a MySQL database service. Railway exposes MYSQLHOST, MYSQLPORT, MYSQLUSER, MYSQLPASSWORD and MYSQLDATABASE to other services.

## 2. Deploy this folder
Use GitHub or Railway CLI. CLI: `railway init`, then `railway up`.

## 3. App variables
Add these variables to the Flask service (Railway Variables):

SECRET_KEY=<long-random-secret>
DB_HOST=${{MySQL.MYSQLHOST}}
DB_PORT=${{MySQL.MYSQLPORT}}
DB_USER=${{MySQL.MYSQLUSER}}
DB_PASSWORD=${{MySQL.MYSQLPASSWORD}}
DB_NAME=${{MySQL.MYSQLDATABASE}}
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_DEFAULT_SENDER=

Replace `MySQL` in the references if your database service has a different name.

## 4. Initialize database once
After both services are running, open the Flask service shell or use Railway CLI and run:
`python init_hosted_db.py`

This creates the tables and demo teacher account in the already-created database. It does NOT try to create a database, which is appropriate for a managed MySQL service.

Demo login: teacher@example.com / teacher123

## 5. Public URL
Open the Flask service Settings > Networking and generate a domain. Railway will provide the public HTTPS URL.

## Important
Do not upload `.env` or put real passwords in GitHub. Set secrets in Railway Variables. The included `.env` from the local project was intentionally removed from this deployment package.
