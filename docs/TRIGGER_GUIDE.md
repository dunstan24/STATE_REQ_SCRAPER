# How to Trigger the Scraper via Webhook

Since you are using **n8n Cloud**, it cannot "reach into" your computer to run the script directly. 

However, you can run a **Local Listener**. This acts like a doorbell: when it gets a signal (via a URL), it runs the script for you.

## Step 1: Start the Listener
1.  Open your terminal/command prompt in the project folder.
2.  Run this command:
    ```bash
    python local_listener.py
    ```
3.  You will see: `Listening on port: 3000`. **Keep this window open.**

## Step 2: Test it Locally
1.  Open your browser.
2.  Go to: `http://localhost:3000/trigger`
3.  You should see `{"status": "success"...}`.
4.  Check your terminal: you will see it started the scraper.

---

## Step 3: Trigger from the Internet (Optional)
If you want to trigger this from **Cloud n8n** (e.g., from a button in the cloud dashboard), you need to make your local listener accessible to the internet.

1.  **Download ngrok** (free tool): [https://ngrok.com/download](https://ngrok.com/download)
2.  **Run ngrok**:
    ```bash
    ngrok http 3000
    ```
3.  **Copy the Forwarding URL** (e.g., `https://a1b2-c3d4.ngrok-free.app`).
4.  **Use this URL in n8n**:
    - Add an **HTTP Request** node in your Cloud n8n workflow.
    - Set URL to: `https://YOUR-NGROK-URL/trigger`
    - Now, when that n8n node runs, it hits your computer -> runs the scraper -> scraper pushes data back to n8n!

## Summary of Flow
1. **You** (or n8n Cloud) → hits `http://localhost:3000/trigger`
2. **Local Listener** → receives request → runs `run_daily.bat`
3. **run_daily.bat** → runs Python Scraper
4. **Python Scraper** → extracts data → PUSHES data to `n8n Webhook`
