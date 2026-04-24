# Render Deployment Guide for LILIT Chatbot

## Problem Summary

Server was crashing on Render when Pinecone database was unavailable, causing the entire chat application to fail.

## Solution Overview

The server now has **graceful degradation** - it will start and serve hardcoded course data even if Pinecone is unreachable. This ensures the application stays online.

---

## Step 1: Set Environment Variables in Render

Go to your Render service dashboard:

1. Navigate to **Settings** → **Environment**
2. Add/verify these variables:

```
OPENAI_API_KEY=sk-...your-key...
PINECONE_API_KEY=your-pinecone-api-key
PINECONE_INDEX_NAME=lilit-lms
```

### Where to Get These Keys

**OpenAI API Key:**

- Visit https://platform.openai.com/api-keys
- Create a new API key (or use existing one)
- Cost-effective: uses `text-embedding-3-small` and `gpt-5-nano`

**Pinecone Keys:**

- Visit https://app.pinecone.io
- Get your API key from **API Keys** section
- Ensure index `lilit-lms` exists (or use your index name)

---

## Step 2: Verify Pinecone Index Exists

Before deploying, check your Pinecone setup:

```bash
# Option A: Via Pinecone UI
1. Go to https://app.pinecone.io
2. Look for index named "lilit-lms"
3. Verify it has data (at least some embeddings)

# Option B: Via Python
python -c "
from pinecone import Pinecone
pc = Pinecone(api_key='YOUR_API_KEY')
indexes = pc.list_indexes()
print('Indexes:', [i.name for i in indexes.indexes])
"
```

**If index doesn't exist:**

- The server will still work with hardcoded course data
- Knowledge base queries will fail gracefully
- Users will see: "I cannot access my knowledge base at the moment..."

---

## Step 3: Rebuild Knowledge Base (Optional but Recommended)

If you've made changes to course data or documents, rebuild the Pinecone index locally:

```bash
# Local environment setup
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Set API keys
export OPENAI_API_KEY=sk-...
export PINECONE_API_KEY=...
export PINECONE_INDEX_NAME=lilit-lms

# Rebuild index
python indexer.py
```

This will:

- Crawl https://lms.lilit.lk and fetch course data
- Read all files from `docs/` directory
- Create embeddings using `text-embedding-3-small`
- Upload to Pinecone index

---

## Step 4: Update Render Build Settings

Ensure your `render.yaml` or Build Command includes:

```yaml
# In Render Dashboard -> Settings -> Build Command
pip install -r requirements.txt

# Start Command (if using Render Native)
uvicorn server:app --host 0.0.0.0 --port $PORT
```

Or for `render.yaml` (Web Service):

```yaml
services:
  - type: web
    name: lilit-chatbot
    runtime: python
    buildCommand: "pip install -r requirements.txt"
    startCommand: "uvicorn server:app --host 0.0.0.0 --port $PORT"
    envVars:
      - key: OPENAI_API_KEY
        sync: false
      - key: PINECONE_API_KEY
        sync: false
      - key: PINECONE_INDEX_NAME
        value: "lilit-lms"
```

---

## Step 5: Deploy

### Option A: Manual Deploy on Render

1. Push changes to your Git repository
2. Go to Render dashboard
3. Click **Manual Deploy** → **Deploy latest commit**

### Option B: Auto Deploy

- Enable "Auto-Deploy" in Render settings
- Every git push will trigger deployment

---

## Step 6: Verify Deployment

### Check Server Status

1. Visit your Render URL: `https://your-app.onrender.com`
2. You should see the LILIT chatbot homepage

### Check Console Logs

In Render Dashboard → **Logs**:

**Expected Output:**

```
... Loading Database ...
✓ Successfully loaded Pinecone index: lilit-lms
INFO:     Uvicorn running on http://0.0.0.0:10000
```

**If Pinecone Fails:**

```
... Loading Database ...
⚠ Warning: Failed to load Pinecone index 'lilit-lms': [error reason]
  Falling back to hardcoded data for responses.
INFO:     Uvicorn running on http://0.0.0.0:10000
```

✅ **Both are OK!** The server will work either way.

### Test Course Queries

Open the chatbot and ask:

- "What are the courses available in lilit?"
- "Tell me about all courses"
- "What courses does LILIT offer?"

**Expected:** Should show all course details with duration, fee, and overview.

### Test Knowledge Base (if Pinecone connected)

Ask: "What's LILIT's vision?"  
**Expected:** Should return the vision statement from Pinecone

---

## Troubleshooting

### Problem: "I cannot access my knowledge base..."

**Cause:** Pinecone is not available or not properly configured

**Solution:**

1. Check `PINECONE_API_KEY` is set correctly in Render
2. Verify index exists: `pinecone.io` → Check indexes
3. Check Render logs for connection errors
4. Course queries will still work with hardcoded data

### Problem: Server won't start

**Cause:** Usually a syntax error or missing environment variable

**Solution:**

1. Check Render logs in dashboard
2. Run locally: `python server.py` to verify
3. Check all required environment variables are set
4. Verify Python version is 3.8+

### Problem: Course queries still being rejected

**Cause:** Old code may not be deployed

**Solution:**

1. Force redeploy: `git push --force` (if applicable)
2. Manual deploy in Render: Click "Deploy latest commit"
3. Check Render logs show the updated code

### Problem: Slow response on Render

**Cause:** Cold start or rate limiting

**Solution:**

1. First request is slower (cold start) - wait 10 seconds
2. Subsequent requests are fast
3. Check rate limit: `20/minute` for `/chat` endpoint
4. For high traffic, upgrade Render plan

---

## Key Features of This Fix

✅ **Server won't crash** if Pinecone is down  
✅ **Graceful degradation** - core features work without knowledge base  
✅ **Course data always available** - hardcoded courses never fail  
✅ **Clear diagnostic messages** - you'll know what's working  
✅ **Production ready** - handles errors like a pro

---

## Monitoring

### Recommended Monitoring

1. **Error Rate**: Check Render logs weekly
2. **Latency**: Pinecone queries should be <2 seconds
3. **API Usage**: Monitor OpenAI and Pinecone costs

### Important Metrics

- **Vectorstore health**: Check if Pinecone is loading
- **Chat endpoint health**: Verify `/chat` endpoint is responding
- **Error messages**: Monitor for connection failures

---

## Cost Optimization

### OpenAI Costs

- Using `text-embedding-3-small`: $0.02 per 1M tokens (very cheap)
- Using `gpt-5-nano`: ~$0.30 per 1M input tokens (reasonable)
- Current: ~$5-20/month for typical usage

### Pinecone Costs

- Free tier: 1,000 vectors storage
- Pro tier: Pay as you grow ($0.03 per vector/month)
- Current usage: ~1,000-5,000 vectors (usually free)

### Render Costs

- Free tier: Limited, slower cold starts
- Starter: $7/month (recommended)
- Pro: $25+/month (high traffic)

---

## Rollback (if needed)

If something breaks:

```bash
# Revert to previous version
git revert HEAD
git push origin main

# Then in Render Dashboard: Manual Deploy → Deploy latest commit
```

---

## Support & Debugging

### Enable Debug Mode

Temporarily add to `server.py`:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check Pinecone Connection

```python
# Run this locally to test
from pinecone import Pinecone
pc = Pinecone(api_key="your_key")
print(pc.list_indexes())
```

### Check OpenAI API

```python
from langchain_openai import OpenAIEmbeddings
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
print(embeddings.embed_query("test"))
```

---

## Next Steps

1. ✅ Set environment variables in Render
2. ✅ Verify Pinecone index exists (or create new one)
3. ✅ Deploy the updated code
4. ✅ Test course queries in the chatbot
5. ✅ Monitor logs for any issues
6. ✅ Share with team that deployment is ready

**Questions?** Check the logs in Render dashboard or run locally to debug.
