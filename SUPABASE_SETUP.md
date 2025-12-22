# Supabase Setup Guide for Secret Santa

## Overview

This Secret Santa app uses **Supabase** for persistent database storage via the official `st-supabase-connection` library recommended by Streamlit.

**Why Supabase?**
- ✅ Free tier with 500MB storage
- ✅ No IP restrictions (works reliably on Streamlit Cloud)
- ✅ Built-in connection pooling and caching
- ✅ Official Streamlit integration
- ✅ Data persists through all redeployments

---

## Step 1: Create Supabase Account & Project

### 1.1 Sign Up for Supabase

1. Go to https://supabase.com
2. Click **Start your project**
3. Sign in with GitHub (recommended)

### 1.2 Create a New Project

1. Click **New Project**
2. Fill in:
   - **Name**: `secret-santa` (or any name you prefer)
   - **Database Password**: Create a strong password (save this!)
   - **Region**: Choose closest to your users
3. Click **Create new project**
4. Wait ~2 minutes for provisioning

### 1.3 Get Your Connection Credentials

Once your project is ready:

1. Go to **Settings** (gear icon in sidebar)
2. Click **API**
3. You'll need two values:
   - **Project URL**: (looks like `https://xxxxx.supabase.co`)
   - **anon public** API Key: (in the "Project API keys" section)

**📝 Save these values** - you'll need them in Step 3!

---

## Step 2: Create Database Tables

### 2.1 Open SQL Editor

1. In your Supabase dashboard, click **SQL Editor** (left sidebar)
2. Click **New query**

### 2.2 Run Schema Script

1. Open the file `supabase_schema.sql` in this repo
2. Copy the entire contents
3. Paste into the SQL editor
4. Click **Run** (or press `Cmd/Ctrl + Enter`)

You should see: "Success. No rows returned"

### 2.3 Verify Tables Created

1. Click **Table Editor** in the left sidebar
2. You should see 8 tables:
   - teams
   - participants
   - assignments
   - logs
   - wishlists
   - survey_questions
   - survey_responses
   - messages

---

## Step 3: Configure Secrets

### For Local Development

1. Create/edit `.streamlit/secrets.toml` in your project root:

```toml
# .streamlit/secrets.toml

SECRETSANTA_ADMIN_PIN = "your-admin-pin-here"

[connections.supabase]
SUPABASE_URL = "https://xxxxx.supabase.co"
SUPABASE_KEY = "your-anon-public-key-here"
```

2. Replace `xxxxx.supabase.co` with your **Project URL** from Step 1.3
3. Replace `your-anon-public-key-here` with your **anon public key** from Step 1.3
4. Replace `your-admin-pin-here` with your desired admin PIN

**⚠️ Important**: Make sure `.streamlit/secrets.toml` is in your `.gitignore`!

### For Streamlit Cloud

1. Go to your Streamlit Cloud app dashboard
2. Click on your app → **Settings** → **Secrets**
3. Add the following:

```toml
SECRETSANTA_ADMIN_PIN = "your-admin-pin-here"

[connections.supabase]
SUPABASE_URL = "https://xxxxx.supabase.co"
SUPABASE_KEY = "your-anon-public-key-here"
```

4. Click **Save**
5. Your app will restart automatically

---

## Step 4: Test Your Connection

### Local Testing

1. Run your app:
   ```bash
   streamlit run secret_santa.py
   ```

2. The app should start without errors
3. Try creating a team to verify database connectivity

### On Streamlit Cloud

1. Push your code to GitHub:
   ```bash
   git add .
   git commit -m "Add Supabase connection"
   git push
   ```

2. Deploy on Streamlit Cloud:
   - Go to https://share.streamlit.io
   - Click **New app**
   - Select your repository
   - Select `secret_santa.py` as the main file
   - Click **Deploy**

3. Once deployed, verify:
   - App loads without errors
   - You can create a team
   - Data persists after restarting the app

---

## Troubleshooting

### Error: "Table doesn't exist"

**Solution**: Make sure you ran the `supabase_schema.sql` script in Step 2.

### Error: "Invalid API key"

**Solutions**:
- ✅ Verify you're using the **anon public** key (not the service role key)
- ✅ Check for typos in your secrets.toml
- ✅ Make sure the key is from the correct project

### Error: "Connection refused" or "Network error"

**Solutions**:
- ✅ Verify your Supabase project is active (check dashboard)
- ✅ Check your SUPABASE_URL is correct
- ✅ Ensure you're using `https://` in the URL

### App says "Database tables not found"

**Solution**:
1. Go to Supabase SQL Editor
2. Run the `supabase_schema.sql` script again
3. Verify tables appear in Table Editor

### Data not persisting

**Solution**:
- ✅ Check that secrets are configured correctly in Streamlit Cloud
- ✅ Verify you're not using SQLite locally (should see no `.db` files)
- ✅ Test by restarting your app and checking if data remains

---

## Security Best Practices

### 1. Protect Your Secrets

```bash
# Add to .gitignore
.streamlit/secrets.toml
*.db
.env
```

### 2. Use Row Level Security (RLS)

For production apps, enable RLS in Supabase:

1. Go to **Authentication** → **Policies**
2. Enable RLS on all tables
3. Create policies to control access

Example policy for the `teams` table:
```sql
-- Allow anyone to read teams
CREATE POLICY "Enable read access for all users" ON teams
FOR SELECT USING (true);

-- Allow anyone to insert teams
CREATE POLICY "Enable insert for all users" ON teams
FOR INSERT WITH CHECK (true);
```

### 3. Rotate Your API Key

Periodically (every 6 months):
1. Generate a new anon key in Supabase
2. Update secrets in Streamlit Cloud
3. Invalidate old key

---

## Monitoring & Maintenance

### Check Database Usage

1. Go to Supabase Dashboard → **Settings** → **Database**
2. Monitor:
   - Disk usage (500MB free tier limit)
   - Connection count
   - Query performance

### Backup Your Data

**Option 1: Export via Supabase**
1. Go to **Table Editor**
2. Select each table → Export as CSV
3. Store backups securely

**Option 2: Use the Admin Panel**
1. Login as admin in your app
2. Download Participants CSV
3. Download Audit Logs CSV

### Free Tier Limits

Supabase free tier includes:
- 500MB database space
- 2GB bandwidth
- 50MB file storage
- Unlimited API requests

For Secret Santa apps with <200 participants, this is more than enough!

---

## Migration from PostgreSQL Direct Connection

If you previously used direct PostgreSQL connection (`psycopg2`):

1. Your data is already in Supabase - no need to migrate!
2. Just update your secrets format from:
   ```toml
   DATABASE_URL = "postgresql://..."
   ```
   To:
   ```toml
   [connections.supabase]
   SUPABASE_URL = "https://..."
   SUPABASE_KEY = "..."
   ```

3. Redeploy your app

---

## Advantages of st-supabase-connection

Compared to direct PostgreSQL connection:

| Feature | st-supabase-connection | Direct PostgreSQL |
|---------|----------------------|-------------------|
| IP Restrictions | ❌ None | ✅ Often blocked on Streamlit Cloud |
| Connection Pooling | ✅ Built-in | ⚠️ Manual setup |
| Caching | ✅ Automatic | ⚠️ Manual setup |
| Setup Complexity | ✅ Simple | ⚠️ More config needed |
| Streamlit Integration | ✅ Official | ⚠️ Third-party |

---

## Need Help?

- **Supabase Docs**: https://supabase.com/docs
- **st-supabase-connection**: https://github.com/SiddhantSadangi/st_supabase_connection
- **Streamlit Connections**: https://docs.streamlit.io/library/api-reference/connections

---

## Summary Checklist

- [ ] Created Supabase account and project
- [ ] Copied Project URL and anon public key
- [ ] Ran `supabase_schema.sql` in SQL Editor
- [ ] Verified 8 tables created
- [ ] Added secrets to `.streamlit/secrets.toml` (local)
- [ ] Added secrets to Streamlit Cloud (production)
- [ ] Tested app locally
- [ ] Deployed to Streamlit Cloud
- [ ] Verified data persists through restarts

🎉 Your Secret Santa app is now ready with persistent database storage!
