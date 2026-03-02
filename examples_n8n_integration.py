"""
Example: Custom n8n Integration Script
Shows different ways to connect your scraper to n8n
"""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from visa_allocation_scraper import VisaAllocationScraper
from n8n_integration import N8NIntegration
import config


# ============================================================
# CONFIGURATION - Update these values
# ============================================================

# Your n8n webhook URL
# Cloud: https://your-instance.app.n8n.cloud/webhook/visa-data
# Local: http://localhost:5678/webhook/visa-data
N8N_WEBHOOK_URL = "http://localhost:5678/webhook/visa-data"

# Optional: API key for authentication
N8N_API_KEY = None  # Set to your API key if using authentication

# Batch size for sending data (default: 100)
BATCH_SIZE = 100


# ============================================================
# EXAMPLE 1: Basic Integration
# ============================================================

def example_basic():
    """Basic example - scrape and send to n8n"""
    print("=" * 70)
    print("EXAMPLE 1: Basic Integration")
    print("=" * 70)
    
    # Run scraper
    scraper = VisaAllocationScraper()
    allocation_data = scraper.run()
    
    if allocation_data:
        # Format data
        records = scraper.format_for_excel(allocation_data)
        
        # Send to n8n
        n8n = N8NIntegration(N8N_WEBHOOK_URL)
        success = n8n.send_data(records, batch_size=BATCH_SIZE)
        
        if success:
            print("\n✅ Data sent to n8n successfully!")
        else:
            print("\n❌ Failed to send data to n8n")
    else:
        print("\n❌ No data scraped")


# ============================================================
# EXAMPLE 2: With Error Handling
# ============================================================

def example_with_error_handling():
    """Example with comprehensive error handling"""
    print("=" * 70)
    print("EXAMPLE 2: With Error Handling")
    print("=" * 70)
    
    try:
        # Run scraper
        scraper = VisaAllocationScraper()
        allocation_data = scraper.run()
        
        if not allocation_data:
            raise Exception("No data was scraped")
        
        # Format data
        records = scraper.format_for_excel(allocation_data)
        
        if not records:
            raise Exception("No records to send")
        
        print(f"\n📊 Scraped {len(records)} records")
        
        # Send to n8n
        n8n = N8NIntegration(N8N_WEBHOOK_URL)
        success = n8n.send_data(records, batch_size=BATCH_SIZE)
        
        if not success:
            raise Exception("Failed to send data to n8n")
        
        print("\n✅ Success! Data sent to n8n")
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        return False


# ============================================================
# EXAMPLE 3: Save Locally AND Send to n8n
# ============================================================

def example_save_and_send():
    """Save data locally and also send to n8n"""
    print("=" * 70)
    print("EXAMPLE 3: Save Locally AND Send to n8n")
    print("=" * 70)
    
    # Run scraper (automatically saves to output/)
    scraper = VisaAllocationScraper()
    allocation_data = scraper.run()
    
    if allocation_data:
        # Format data
        records = scraper.format_for_excel(allocation_data)
        
        # Also save in n8n-ready format
        n8n = N8NIntegration(N8N_WEBHOOK_URL)
        n8n.save_for_n8n(records, filename="output/n8n_payload.json")
        
        # Send to n8n
        success = n8n.send_data(records, batch_size=BATCH_SIZE)
        
        print("\n📁 Files saved in output/")
        print(f"🔗 n8n integration: {'✅ Success' if success else '❌ Failed'}")


# ============================================================
# EXAMPLE 4: Custom Data Filtering
# ============================================================

def example_custom_filtering():
    """Send only specific data to n8n (e.g., only Visa 190)"""
    print("=" * 70)
    print("EXAMPLE 4: Custom Data Filtering")
    print("=" * 70)
    
    # Run scraper
    scraper = VisaAllocationScraper()
    allocation_data = scraper.run()
    
    if allocation_data:
        # Format all data
        all_records = scraper.format_for_excel(allocation_data)
        
        # Filter only Visa 190
        visa_190_records = [
            record for record in all_records 
            if record.get('visa_subclass') == '190'
        ]
        
        print(f"\n📊 Total records: {len(all_records)}")
        print(f"📊 Visa 190 records: {len(visa_190_records)}")
        
        # Send only Visa 190 to n8n
        n8n = N8NIntegration(N8N_WEBHOOK_URL)
        success = n8n.send_data(visa_190_records, batch_size=BATCH_SIZE)
        
        if success:
            print("\n✅ Visa 190 data sent to n8n!")


# ============================================================
# EXAMPLE 5: Multiple Webhooks
# ============================================================

def example_multiple_webhooks():
    """Send different data to different n8n webhooks"""
    print("=" * 70)
    print("EXAMPLE 5: Multiple Webhooks")
    print("=" * 70)
    
    # Different webhook URLs for different visa types
    webhook_190 = "http://localhost:5678/webhook/visa-190"
    webhook_491 = "http://localhost:5678/webhook/visa-491"
    
    # Run scraper
    scraper = VisaAllocationScraper()
    allocation_data = scraper.run()
    
    if allocation_data:
        # Format all data
        all_records = scraper.format_for_excel(allocation_data)
        
        # Split by visa type
        visa_190_records = [r for r in all_records if r.get('visa_subclass') == '190']
        visa_491_records = [r for r in all_records if r.get('visa_subclass') == '491']
        
        # Send to different webhooks
        n8n_190 = N8NIntegration(webhook_190)
        n8n_491 = N8NIntegration(webhook_491)
        
        success_190 = n8n_190.send_data(visa_190_records)
        success_491 = n8n_491.send_data(visa_491_records)
        
        print(f"\n📊 Visa 190: {len(visa_190_records)} records → {'✅' if success_190 else '❌'}")
        print(f"📊 Visa 491: {len(visa_491_records)} records → {'✅' if success_491 else '❌'}")


# ============================================================
# EXAMPLE 6: Conditional Sending
# ============================================================

def example_conditional_sending():
    """Send to n8n only if certain conditions are met"""
    print("=" * 70)
    print("EXAMPLE 6: Conditional Sending")
    print("=" * 70)
    
    # Run scraper
    scraper = VisaAllocationScraper()
    allocation_data = scraper.run()
    
    if allocation_data:
        # Format data
        records = scraper.format_for_excel(allocation_data)
        
        # Calculate total allocations
        total_allocations = sum(r.get('allocations', 0) for r in records)
        
        print(f"\n📊 Total allocations: {total_allocations}")
        
        # Only send if total is above threshold
        THRESHOLD = 4000
        
        if total_allocations >= THRESHOLD:
            print(f"✅ Total >= {THRESHOLD}, sending to n8n...")
            n8n = N8NIntegration(N8N_WEBHOOK_URL)
            n8n.send_data(records)
        else:
            print(f"⚠️  Total < {THRESHOLD}, not sending to n8n")


# ============================================================
# MAIN - Choose which example to run
# ============================================================

def main():
    """Main entry point"""
    print("\n" + "=" * 70)
    print("N8N INTEGRATION EXAMPLES")
    print("=" * 70)
    print("\nChoose an example to run:")
    print("[1] Basic Integration")
    print("[2] With Error Handling")
    print("[3] Save Locally AND Send to n8n")
    print("[4] Custom Data Filtering (Visa 190 only)")
    print("[5] Multiple Webhooks")
    print("[6] Conditional Sending")
    print("[0] Exit")
    print()
    
    choice = input("Enter choice (0-6): ").strip()
    print()
    
    examples = {
        '1': example_basic,
        '2': example_with_error_handling,
        '3': example_save_and_send,
        '4': example_custom_filtering,
        '5': example_multiple_webhooks,
        '6': example_conditional_sending,
    }
    
    if choice in examples:
        examples[choice]()
    elif choice == '0':
        print("Goodbye!")
    else:
        print("Invalid choice!")


if __name__ == "__main__":
    main()
