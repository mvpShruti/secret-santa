# PostgreSQL Setup Guide for Secret Santa

## Quick Start

The app supports **dual database mode**:
- **Local development**: SQLite (default, no config needed)
- **Production**: PostgreSQL (requires DATABASE_URL)

## Why PostgreSQL?

Your Secret Santa app now supports PostgreSQL for production deployments to solve a critical problem:

**Problem**: Streamlit Cloud uses an **ephemeral filesystem** - any files stored locally (including the SQLite database) get deleted every time the app redeploys. This means:
- ❌ Assignments get lost
- ❌ Messages disappear
- ❌ Wishlists are erased
- ❌ Survey responses vanish

**Solution**: PostgreSQL provides **persistent storage** that survives app restarts and redeployments!

---

## Option 1: Supabase (Recommended - Free Tier)

Supabase offers a generous free tier with PostgreSQL hosting.

### Steps:

1. **Sign up**: Go to https://supabase.com and create a free account

2. **Create a new project**:
   - Click "New Project"
   - Enter project name (e.g., "secret-santa")
   - Set a database password (save this!)
   - Choose a region close to your users
   - Click "Create new project" (takes ~2 minutes)

3. **Get connection string**:
   - Go to **Settings** > **Database**
   - Scroll to "Connection string"
   - Select **URI** format
   - Copy the connection string (looks like this):
     ```
     postgresql://postgres:[YOUR-PASSWORD]@db.abc123xyz.supabase.co:5432/postgres
     ```
   - Replace `[YOUR-PASSWORD]` with your actual database password

4. **Configure the app**:

   **For local testing:**
   - Edit `.streamlit/secrets.toml`
   - Uncomment and update the DATABASE_URL line:
     ```toml
     DATABASE_URL = "postgresql://postgres:YOUR_PASSWORD@db.abc123xyz.supabase.co:5432/postgres"
     ```

   **For Streamlit Cloud:**
   - Go to your app on Streamlit Cloud
   - Click **Settings** > **Secrets**
   - Add:
     ```toml
     DATABASE_URL = "postgresql://postgres:YOUR_PASSWORD@db.abc123xyz.supabase.co:5432/postgres"
     ```
   - Click "Save"
   - App will restart automatically

5. **Verify**:
   - Check the app logs/console
   - Look for: `🐘 Using PostgreSQL database`
   - Test by creating assignments and restarting the app
   - Assignments should persist!

---

## Option 2: Neon (Serverless PostgreSQL)

Neon provides serverless PostgreSQL with a free tier.

### Steps:

1. **Sign up**: Go to https://neon.tech and create an account

2. **Create a project**:
   - Click "Create a project"
   - Enter project name
   - Choose a region
   - Click "Create project"

3. **Get connection string**:
   - Copy the connection string from the dashboard
   - It looks like:
     ```
     postgresql://user:password@ep-cool-name-123456.us-east-2.aws.neon.tech/neondb?sslmode=require
     ```

4. **Configure the app** (same as Supabase):
   - Add DATABASE_URL to `.streamlit/secrets.toml` (local)
   - OR add to Streamlit Cloud secrets (production)

5. **Verify**: Same as Supabase steps above

---

## Option 3: Other PostgreSQL Providers

The app works with any PostgreSQL database. Compatible providers:

- **Render** (https://render.com)
- **Railway** (https://railway.app)
- **AWS RDS** (https://aws.amazon.com/rds/)
- **Google Cloud SQL** (https://cloud.google.com/sql)
- **Heroku Postgres** (https://www.heroku.com/postgres)

Just get the connection string and add it as `DATABASE_URL`.

---

## Local Development

### Using SQLite (Default)

```bash
# No configuration needed!
streamlit run secret_santa.py

# You'll see: 📁 Using SQLite database: secretsanta.db
```

### Using PostgreSQL (Testing Production Setup)

1. Add DATABASE_URL to `.streamlit/secrets.toml`:
   ```toml
   DATABASE_URL = "postgresql://..."
   ```

2. Run the app:
   ```bash
   streamlit run secret_santa.py

   # You'll see: 🐘 Using PostgreSQL database
   ```

---

## Deployment to Streamlit Cloud

### Prerequisites
- PostgreSQL database created (Supabase/Neon/other)
- Connection string ready

### Steps:

1. **Push code to GitHub**:
   ```bash
   git add .
   git commit -m "Add PostgreSQL support for persistence"
   git push
   ```

2. **Deploy on Streamlit Cloud**:
   - Go to https://share.streamlit.io
   - Click "New app"
   - Select your repository
   - Click "Deploy"

3. **Add DATABASE_URL secret**:
   - In Streamlit Cloud, go to your app
   - Click **Settings** > **Secrets**
   - Add:
     ```toml
     DATABASE_URL = "postgresql://postgres:PASSWORD@db.PROJECT.supabase.co:5432/postgres"
     SECRETSANTA_ADMIN_PIN = "your-admin-pin"
     ```
   - Click "Save"

4. **Verify deployment**:
   - App will restart automatically
   - Check logs for: `🐘 Using PostgreSQL database`
   - Test persistence:
     - Generate assignments
     - Manually restart the app (Settings > Reboot)
     - Verify assignments are still there

---

## Data Migration (Optional)

If you have existing SQLite data you want to migrate:

### Export from SQLite:

```python
import sqlite3
import pandas as pd

conn = sqlite3.connect('secretsanta.db')

# Export each table
tables = ['teams', 'participants', 'assignments', 'wishlists',
          'survey_responses', 'messages', 'logs']

for table in tables:
    try:
        df = pd.read_sql(f"SELECT * FROM {table}", conn)
        df.to_csv(f'{table}_backup.csv', index=False)
        print(f"✅ Exported {table}: {len(df)} rows")
    except Exception as e:
        print(f"⚠️  Skipped {table}: {e}")

conn.close()
```

### Import to PostgreSQL:

Use the admin panel's CSV upload feature to restore participants, or manually insert data using SQL.

---

## Troubleshooting

### Connection Errors

**Error**: `connection refused` or `could not connect`

**Solutions**:
- ✅ Check DATABASE_URL format is correct
- ✅ Verify database is accessible (check Supabase/Neon dashboard)
- ✅ Check firewall settings
- ✅ Ensure you're using the correct host/port

---

### SSL Errors

**Error**: `SSL connection required`

**Solution**: Add `?sslmode=require` to your connection string:
```
postgresql://user:pass@host/db?sslmode=require
```

---

### Permission Errors

**Error**: `permission denied to create table`

**Solution**: Ensure your database user has CREATE TABLE privileges:
```sql
GRANT CREATE ON SCHEMA public TO your_user;
```

---

### App Still Using SQLite

**Problem**: Logs show `📁 Using SQLite database`

**Solutions**:
- ✅ Check DATABASE_URL is in secrets (Streamlit Cloud) or `.streamlit/secrets.toml` (local)
- ✅ Restart the app after adding DATABASE_URL
- ✅ Check for typos in secret name (must be exactly `DATABASE_URL`)
- ✅ Check connection string format

---

### Tables Not Created

**Problem**: App starts but tables don't exist

**Solution**:
- Delete the database and let the app recreate it
- Or manually run the schema from init_db() function

---

## Security Best Practices

### Protect Your Secrets

1. **Never commit secrets to git**:
   ```bash
   # Add to .gitignore:
   .streamlit/secrets.toml
   secretsanta.db
   *.db
   ```

2. **Use environment variables** for CI/CD:
   ```bash
   export DATABASE_URL="postgresql://..."
   ```

3. **Rotate credentials** periodically:
   - Change database password every 3-6 months
   - Update all deployments with new credentials

### Database Security

1. **Enable SSL** for production:
   ```
   DATABASE_URL = "postgresql://...?sslmode=require"
   ```

2. **Use strong passwords**:
   - Minimum 16 characters
   - Mix of letters, numbers, symbols
   - Use a password manager

3. **Limit permissions**:
   - Create a dedicated database user for the app
   - Grant only necessary privileges (CREATE, SELECT, INSERT, UPDATE, DELETE)

4. **Enable backups**:
   - Supabase: Automatic backups enabled
   - Neon: Enable point-in-time recovery
   - Others: Configure backup schedule

---

## Monitoring and Maintenance

### Check Database Usage

**Supabase**:
- Dashboard > Settings > Database
- View disk space, connections, queries

**Neon**:
- Dashboard shows storage usage and connections

### Backup Strategy

**Recommended**:
1. Regular exports via admin panel:
   - Download Participants CSV (weekly)
   - Download Audit Logs CSV (weekly)

2. Database snapshots:
   - Supabase: Automatic daily backups
   - Neon: Point-in-time recovery enabled

3. Pre-deployment backups:
   - Before major updates, export all data

### Performance Optimization

For large teams (100+ participants):
1. Add indexes on frequently queried columns
2. Use connection pooling (already implemented)
3. Consider read replicas for heavy traffic

---

## Frequently Asked Questions

### Q: Do I need PostgreSQL for local development?

**A**: No! SQLite works great for local development. Only use PostgreSQL for production deployment on Streamlit Cloud.

---

### Q: What happens to my SQLite data when I switch to PostgreSQL?

**A**: SQLite and PostgreSQL are separate. Your local SQLite data remains untouched. You can migrate it using the export/import process above.

---

### Q: How much does PostgreSQL hosting cost?

**A**: Both Supabase and Neon offer **free tiers** that are more than sufficient for Secret Santa apps with up to 100-200 participants.

**Limits**:
- Supabase Free: 500MB storage, unlimited API requests
- Neon Free: 512MB storage, 100 hours/month compute

---

### Q: Can I use my own PostgreSQL server?

**A**: Yes! Any PostgreSQL 12+ database works. Just provide the connection string.

---

### Q: How do I know which database I'm using?

**A**: Check the app console/logs on startup:
- `📁 Using SQLite database: secretsanta.db` = SQLite
- `🐘 Using PostgreSQL database` = PostgreSQL

---

### Q: What if my database connection fails?

**A**: The app will show an error on startup. Check:
1. DATABASE_URL is correct
2. Database is running and accessible
3. Network/firewall allows connections
4. Credentials are valid

---

## Need Help?

- **Supabase docs**: https://supabase.com/docs
- **Neon docs**: https://neon.tech/docs
- **PostgreSQL docs**: https://www.postgresql.org/docs/

---

## Summary

✅ **Development**: SQLite (automatic, no setup)
✅ **Production**: PostgreSQL (persistent, survives redeploys)
✅ **Free tier**: Available on Supabase and Neon
✅ **Migration**: Simple CSV export/import
✅ **Security**: SSL support, secrets management

Your Secret Santa assignments, messages, and wishlists will now persist forever! 🎉
