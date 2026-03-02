# Free Hosting Guide: GitHub Actions

You can host this scraper completely **FREE** using **GitHub Actions**.
GitHub provides 2,000 free automation minutes per month, which is perfect for running this script once a day.

## How it works
1.  You push your code to a GitHub repository.
2.  GitHub's servers wake up automatically (on schedule).
3.  They run your Python script.
4.  The script sends the data to your n8n Webhook.
5.  The server shuts down.

---

## Setup Steps

### 1. Create a GitHub Repository
1.  Go to [github.com](https://github.com) and create a **new repository**.
2.  Name it something like `visa-scraper`.
3.  Keep it **Private** (recommended) or Public.

### 2. Push Your Code
Verify you have the `.github/workflows/daily_scrape.yml` file I just created. Then run these commands in your project folder:

```bash
git init
git add .
git commit -m "Initial commit of scraper"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/visa-scraper.git
git push -u origin main
```
*(Replace `YOUR_USERNAME` with your actual GitHub username)*

### 3. Add Your n8n Webhook
To keep your webhook URL safe, we add it as a "Secret".

1.  Go to your GitHub Repository page.
2.  Click **Settings** (top right tab).
3.  On the left, scroll down to **Secrets and variables** > **Actions**.
4.  Click **New repository secret**.
5.  **Name**: `N8N_WEBHOOK_URL`
6.  **Value**: Paste your full n8n Webhook URL (e.g., `https://kayika.app.n8n.cloud/webhook/...`).
7.  Click **Add secret**.

### 4. Test It
1.  Go to the **Actions** tab in your repository.
2.  Click **Daily Visa Scraper** on the left.
3.  Click **Run workflow** (button on the right).
4.  Watch it run! It should turn green and send data to n8n.

---

## 📅 Schedule
By default, I set it to run every day at **00:00 UTC**.
To change this, edit `.github/workflows/daily_scrape.yml`:
```yaml
on:
  schedule:
    - cron: '0 9 * * *'  # Runs at 9:00 UTC
```
