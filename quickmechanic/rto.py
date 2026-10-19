"""
RTO File Parser for Assetto Corsa gear ratio files.

RTO files contain lists of selectable gear ratios.
Two formats are supported:

1. Standard: VALUE|VALUE (decimal value repeated on both sides)
       4.90|4.90
       4.63|4.63

2. Fraction label: LABEL|VALUE (ring//pinion teeth label, decimal value on the right)
       80//31|3.88
       10//44|4.37

In format 2 the label (e.g. ring//pinion teeth counts) is ignored; only the
decimal value after the last '|' is used.
"""

import os
from typing import List, Optional


class RTOParser:
    """Parser for Assetto Corsa .rto (ratio) files"""
    
    def __init__(self, file_path: str):
        """
        Initialize RTO parser
        
        Args:
            file_path: Path to the .rto file
        """
        self.file_path = file_path
        self.ratios: List[float] = []
        
        if os.path.exists(file_path):
            self.load()
    
    def load(self):
        """Load ratios from .rto file"""
        self.ratios = []
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    
                    # Skip empty lines
                    if not line:
                        continue
                    
                    # Skip comments (lines starting with ; or #)
                    if line.startswith(';') or line.startswith('#'):
                        continue
                    
                    # Parse VALUE|VALUE or LABEL|VALUE format
                    if '|' in line:
                        parts = line.split('|')
                        if len(parts) >= 2:
                            # Try the first part first (standard format: VALUE|VALUE).
                            # Fall back to the last part for label formats like "80//31|3.88".
                            raw = parts[0].strip()
                            try:
                                value = float(raw)
                            except ValueError:
                                try:
                                    value = float(parts[-1].strip())
                                except ValueError:
                                    print(f"Warning: Could not parse ratio value: {line}")
                                    continue
                            self.ratios.append(value)
        except Exception as e:
            print(f"Error loading RTO file {self.file_path}: {e}")
    
    def save(self, backup: bool = True):
        """
        Save ratios to .rto file
        
        Args:
            backup: Create backup before saving
        """
        if backup and os.path.exists(self.file_path):
            backup_path = self.file_path + '.bak'
            try:
                import shutil
                shutil.copy2(self.file_path, backup_path)
            except Exception as e:
                print(f"Error creating backup: {e}")
        
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                for ratio in self.ratios:
                    # Format with 2 decimal places, write VALUE|VALUE
                    f.write(f"{ratio:.2f}|{ratio:.2f}\n")
        except Exception as e:
            print(f"Error saving RTO file {self.file_path}: {e}")
            raise
    
    def get_ratios(self) -> List[float]:
        """
        Get list of ratios
        
        Returns:
            List of ratio values
        """
        return self.ratios.copy()
    
    def set_ratios(self, ratios: List[float]):
        """
        Set list of ratios
        
        Args:
            ratios: List of ratio values
        """
        self.ratios = ratios.copy()
    
    def add_ratio(self, ratio: float):
        """
        Add a ratio to the list
        
        Args:
            ratio: Ratio value to add
        """
        self.ratios.append(ratio)
    
    def remove_ratio(self, index: int):
        """
        Remove a ratio at the specified index
        
        Args:
            index: Index of ratio to remove
        """
        if 0 <= index < len(self.ratios):
            del self.ratios[index]
    
    def update_ratio(self, index: int, ratio: float):
        """
        Update a ratio at the specified index
        
        Args:
            index: Index of ratio to update
            ratio: New ratio value
        """
        if 0 <= index < len(self.ratios):
            self.ratios[index] = ratio
    
    def sort_ratios(self, reverse: bool = True):
        """
        Sort ratios (descending by default for gear ratios)
        
        Args:
            reverse: True for descending order (default), False for ascending
        """
        self.ratios.sort(reverse=reverse)
