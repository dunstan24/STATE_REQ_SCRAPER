"""
Data Analysis and Reporting Module
Analyze scraped immigration data and generate reports
"""

import pandas as pd
import json
from datetime import datetime
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class DataAnalyzer:
    """Analyze immigration nomination data"""
    
    def __init__(self, data: Optional[List[Dict]] = None):
        """
        Initialize analyzer
        
        Args:
            data: List of scraped records
        """
        self.data = data
        self.df = None
        
        if data:
            self.df = pd.DataFrame(data)
    
    def load_from_file(self, filename: str):
        """Load data from file"""
        try:
            if filename.endswith('.csv'):
                self.df = pd.read_csv(filename)
            elif filename.endswith('.json'):
                self.df = pd.read_json(filename)
            elif filename.endswith('.xlsx'):
                self.df = pd.read_excel(filename)
            
            self.data = self.df.to_dict('records')
            logger.info(f"Loaded {len(self.df)} records from {filename}")
            
        except Exception as e:
            logger.error(f"Error loading file: {str(e)}")
    
    def get_summary_statistics(self) -> Dict:
        """Generate summary statistics"""
        if self.df is None or self.df.empty:
            return {}
        
        summary = {
            "total_records": len(self.df),
            "extraction_date": datetime.now().isoformat(),
            "columns": list(self.df.columns),
            "data_types": self.df.dtypes.astype(str).to_dict()
        }
        
        # Try to identify numeric columns for statistics
        numeric_cols = self.df.select_dtypes(include=['int64', 'float64']).columns
        
        if len(numeric_cols) > 0:
            summary["numeric_summary"] = self.df[numeric_cols].describe().to_dict()
        
        return summary
    
    def group_by_state(self) -> pd.DataFrame:
        """Group data by state/territory"""
        if self.df is None:
            return pd.DataFrame()
        
        # Try to find state/territory column
        state_cols = [col for col in self.df.columns if 'state' in col.lower() or 'territory' in col.lower()]
        
        if not state_cols:
            logger.warning("No state/territory column found")
            return pd.DataFrame()
        
        state_col = state_cols[0]
        
        # Group by state
        grouped = self.df.groupby(state_col).size().reset_index(name='count')
        
        return grouped
    
    def generate_report(self, output_file: str = "analysis_report.txt"):
        """Generate text report"""
        if self.df is None:
            logger.error("No data to analyze")
            return
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("=" * 70 + "\n")
                f.write("IMMIGRATION DATA ANALYSIS REPORT\n")
                f.write("=" * 70 + "\n\n")
                
                f.write(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total Records: {len(self.df)}\n\n")
                
                f.write("-" * 70 + "\n")
                f.write("COLUMN INFORMATION\n")
                f.write("-" * 70 + "\n")
                
                for col in self.df.columns:
                    f.write(f"\n{col}:\n")
                    f.write(f"  - Data Type: {self.df[col].dtype}\n")
                    f.write(f"  - Non-null Count: {self.df[col].count()}\n")
                    f.write(f"  - Null Count: {self.df[col].isnull().sum()}\n")
                    
                    if self.df[col].dtype == 'object':
                        unique_count = self.df[col].nunique()
                        f.write(f"  - Unique Values: {unique_count}\n")
                        
                        if unique_count <= 20:
                            f.write(f"  - Values: {', '.join(map(str, self.df[col].unique()))}\n")
                
                f.write("\n" + "=" * 70 + "\n")
                f.write("END OF REPORT\n")
                f.write("=" * 70 + "\n")
            
            logger.info(f"Report generated: {output_file}")
            
        except Exception as e:
            logger.error(f"Error generating report: {str(e)}")
    
    def export_summary(self, output_file: str = "summary.json"):
        """Export summary as JSON"""
        summary = self.get_summary_statistics()
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Summary exported: {output_file}")
            
        except Exception as e:
            logger.error(f"Error exporting summary: {str(e)}")


def compare_data_files(file1: str, file2: str):
    """Compare two data files"""
    try:
        df1 = pd.read_csv(file1) if file1.endswith('.csv') else pd.read_json(file1)
        df2 = pd.read_csv(file2) if file2.endswith('.csv') else pd.read_json(file2)
        
        print(f"\nFile 1: {file1}")
        print(f"  Records: {len(df1)}")
        print(f"  Columns: {list(df1.columns)}")
        
        print(f"\nFile 2: {file2}")
        print(f"  Records: {len(df2)}")
        print(f"  Columns: {list(df2.columns)}")
        
        # Find differences
        common_cols = set(df1.columns) & set(df2.columns)
        
        if common_cols:
            print(f"\nCommon columns: {common_cols}")
        
        print(f"\nRecord count difference: {len(df1) - len(df2)}")
        
    except Exception as e:
        logger.error(f"Error comparing files: {str(e)}")


if __name__ == "__main__":
    print("Data Analysis Module")
    print("This module provides tools for analyzing scraped immigration data")
