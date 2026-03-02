# 🚀 Step-by-Step Guide: Free Hosting on GitHub

Follow these exact steps to get your scraper running for free every day.

## Step 1: Create a Repository on GitHub
1.  Log in to [GitHub.com](https://github.com).
2.  Click the **+** icon in the top-right corner -> **New repository**.
3.  **Repository name**: `visa-scraper` (or any name you like).
4.  **Visibility**: Select **Private** (Important! To keep your data safe).
5.  Click **Create repository**.
6.  **Copy the URL** of your new repository. It will look like:
    `https://github.com/YOUR_USERNAME/visa-scraper.git`

## Step 2: Push Your Code (Do this on your computer)
Open your terminal (Command Prompt or PowerShell) in this project folder and run these commands one by one:

```bash
# 1. Initialize Git (if not done)
git init

# 2. Add all files
git add .

# 3. Commit the files
git commit -m "Setup daily scraper"

# 4. Rename branch to main
git branch -M main

# 5. Link to your GitHub repo (REPLACE THE URL BELOW!)
git remote add origin https://github.com/YOUR_USERNAME/visa-scraper.git

# 6. Push the code
git push -u origin main
```

*(Note: If it asks for a password, you might need to use a Personal Access Token if you have 2FA enabled, or just sign in via the browser popup if available.)*

## Step 3: Add Your n8n Webhook Secret
This connects the scraper to your n8n workflow securely.

1.  Go to your **GitHub Repository** page.
2.  Click **Settings** (top menu).
3.  In the left sidebar, click **Secrets and variables** -> **Actions**.
4.  Click **New repository secret** (green button).
5.  **Name**: `N8N_WEBHOOK_URL`
6.  **Secret**: Paste your n8n Webhook URL:
    `https://kayika.app.n8n.cloud/webhook/visa-data`
7.  Click **Add secret**.

## Step 4: Test It
1.  Go to the **Actions** tab in your repository.
2.  You should see "Daily Visa Scraper" on the left.
3.  Click it -> Click **Run workflow** -> **Run workflow**.

✅ **Done!**
- GitHub will now run this script **every day automatically**.
- The script will send the data to your n8n cloud webhook.
