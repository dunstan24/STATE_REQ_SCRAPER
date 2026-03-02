import http.server
import socketserver
import subprocess
import os
import sys

# Configuration
PORT = 3000
SCRIPT_TO_RUN = "run_daily.bat"

class WebhookHandler(http.server.SimpleHTTPRequestHandler):
    """
    A simple server that listens for a trigger to run the scraper.
    """
    
    def log_message(self, format, *args):
        # Override to print to console
        sys.stderr.write("%s - - [%s] %s\n" %
                         (self.client_address[0],
                          self.log_date_time_string(),
                          format % args))

    def do_GET(self):
        self.handle_request()

    def do_POST(self):
        self.handle_request()

    def handle_request(self):
        # We accept any request to "/trigger" or just matches the root if you prefer
        # But let's be specific: /trigger
        
        if self.path == '/trigger' or self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            response = b'{"status": "success", "message": "Scraper started in background"}'
            self.wfile.write(response)
            
            print("Received trigger! Starting scraper...")
            
            # Check if batch file exists
            if os.path.exists(SCRIPT_TO_RUN):
                # Run the batch file in a separate process so the server doesn't hang
                subprocess.Popen([SCRIPT_TO_RUN], shell=True)
                print(f"Executed: {SCRIPT_TO_RUN}")
            else:
                print(f"Error: {SCRIPT_TO_RUN} not found!")
                
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"status": "error", "message": "Route not found. Use /trigger"}')

def run_server():
    # Allow address reuse prevents "Address already in use" errors during quick restarts
    socketserver.TCPServer.allow_reuse_address = True
    
    with socketserver.TCPServer(("", PORT), WebhookHandler) as httpd:
        print("="*50)
        print(f"LOCAL WEBHOOK LISTENER RUNNING")
        print("="*50)
        print(f"Listening on port: {PORT}")
        print(f"Trigger URL:       http://localhost:{PORT}/trigger")
        print("="*50)
        print("Keep this window OPEN to receive triggers.")
        print("To stop: Press Ctrl+C")
        print("-" * 50)
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server...")
            httpd.shutdown()

if __name__ == "__main__":
    run_server()
