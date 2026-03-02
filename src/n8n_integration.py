"""
N8N Integration Module
Provides utilities for integrating scraped data with n8n automation
"""

import json
import requests
from typing import List, Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class N8NIntegration:
    """Handle n8n webhook integration"""
    
    def __init__(self, webhook_url: Optional[str] = None):
        """
        Initialize n8n integration
        
        Args:
            webhook_url: n8n webhook URL (optional, can be set later)
        """
        self.webhook_url = webhook_url
    
    def set_webhook_url(self, url: str):
        """Set the n8n webhook URL"""
        self.webhook_url = url
    
    def send_data(self, data: List[Dict], batch_size: int = 100) -> bool:
        """
        Send scraped data to n8n webhook
        
        Args:
            data: List of scraped records
            batch_size: Number of records to send per request
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.webhook_url:
            logger.error("Webhook URL not set")
            return False
        
        try:
            # Send data in batches
            for i in range(0, len(data), batch_size):
                batch = data[i:i + batch_size]
                
                payload = {
                    "timestamp": datetime.now().isoformat(),
                    "batch_number": i // batch_size + 1,
                    "total_batches": (len(data) + batch_size - 1) // batch_size,
                    "records_count": len(batch),
                    "data": batch
                }
                
                response = requests.post(
                    self.webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=30
                )
                
                if response.status_code == 200:
                    logger.info(f"Batch {i // batch_size + 1} sent successfully")
                else:
                    logger.error(f"Failed to send batch {i // batch_size + 1}: {response.status_code}")
                    return False
            
            logger.info(f"All data sent to n8n successfully ({len(data)} records)")
            return True
            
        except Exception as e:
            logger.error(f"Error sending data to n8n: {str(e)}")
            return False
    
    def format_for_n8n(self, data: List[Dict]) -> Dict:
        """
        Format data in n8n-friendly structure
        
        Args:
            data: Raw scraped data
            
        Returns:
            Dict: Formatted data for n8n
        """
        return {
            "metadata": {
                "source": "Australian Immigration SkillSelect",
                "scrape_timestamp": datetime.now().isoformat(),
                "total_records": len(data),
                "data_type": "state_territory_nominations"
            },
            "records": data
        }
    
    def save_for_n8n(self, data: List[Dict], filename: str = "n8n_payload.json"):
        """
        Save data in n8n-ready JSON format
        
        Args:
            data: Scraped data
            filename: Output filename
        """
        try:
            formatted_data = self.format_for_n8n(data)
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(formatted_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Data saved for n8n: {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving data for n8n: {str(e)}")
            return False


def create_n8n_workflow_template():
    """
    Create a template n8n workflow for processing the scraped data
    
    Returns:
        Dict: n8n workflow template
    """
    workflow = {
        "name": "Immigration Data Processor",
        "nodes": [
            {
                "parameters": {
                    "httpMethod": "POST",
                    "path": "immigration-data",
                    "responseMode": "responseNode",
                    "options": {}
                },
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "position": [250, 300]
            },
            {
                "parameters": {
                    "functionCode": "// Process incoming immigration data\nconst data = $input.item.json.data;\nconst processed = [];\n\nfor (const record of data) {\n  processed.push({\n    state: record.state_territory || 'Unknown',\n    nominations: parseInt(record.nominations_issued) || 0,\n    date: record.round_date,\n    timestamp: new Date().toISOString()\n  });\n}\n\nreturn processed.map(item => ({ json: item }));"
                },
                "name": "Process Data",
                "type": "n8n-nodes-base.function",
                "typeVersion": 1,
                "position": [450, 300]
            },
            {
                "parameters": {
                    "operation": "insert",
                    "table": "immigration_nominations",
                    "columns": "state,nominations,date,timestamp"
                },
                "name": "Save to Database",
                "type": "n8n-nodes-base.postgres",
                "typeVersion": 1,
                "position": [650, 300]
            },
            {
                "parameters": {
                    "respondWith": "json",
                    "responseBody": "={{ { \"success\": true, \"records_processed\": $json.length } }}"
                },
                "name": "Respond to Webhook",
                "type": "n8n-nodes-base.respondToWebhook",
                "typeVersion": 1,
                "position": [850, 300]
            }
        ],
        "connections": {
            "Webhook": {
                "main": [[{"node": "Process Data", "type": "main", "index": 0}]]
            },
            "Process Data": {
                "main": [[{"node": "Save to Database", "type": "main", "index": 0}]]
            },
            "Save to Database": {
                "main": [[{"node": "Respond to Webhook", "type": "main", "index": 0}]]
            }
        }
    }
    
    return workflow


if __name__ == "__main__":
    # Example usage
    print("N8N Integration Module")
    print("=" * 50)
    
    # Create workflow template
    workflow = create_n8n_workflow_template()
    
    with open("n8n_workflow_template.json", "w") as f:
        json.dump(workflow, f, indent=2)
    
    print("N8N workflow template created: n8n_workflow_template.json")
