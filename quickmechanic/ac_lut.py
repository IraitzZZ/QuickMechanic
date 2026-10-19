"""
LUT (Lookup Table) File Parser for Assetto Corsa
Handles .lut files containing X|Y value pairs
"""

import os
from typing import List, Tuple, Optional


class LUTCurve:
    """Represents a lookup table curve with X|Y pairs"""
    
    def __init__(self, file_path: Optional[str] = None):
        """
        Initialize LUT curve
        
        Args:
            file_path: Path to .lut file (optional)
        """
        self.file_path = file_path
        self.points: List[Tuple[float, float]] = []
        
        if file_path and os.path.exists(file_path):
            self.load()
    
    def load(self):
        """Load LUT file"""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            self.points = []
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#') or line.startswith(';'):
                    continue
                
                # Strip inline comments (; or #)
                for comment_char in (';', '#'):
                    comment_idx = line.find(comment_char)
                    if comment_idx >= 0:
                        line = line[:comment_idx].strip()
                if not line:
                    continue

                # Parse X|Y format
                if '|' in line:
                    parts = line.split('|')
                    if len(parts) == 2:
                        try:
                            x = float(parts[0].strip())
                            y = float(parts[1].strip())
                            self.points.append((x, y))
                        except ValueError:
                            print(f"Warning: Invalid line in LUT file: {line}")
        
        except Exception as e:
            print(f"Error loading LUT file {self.file_path}: {e}")
            raise
    
    def save(self, file_path: Optional[str] = None, backup=True):
        """
        Save LUT file
        
        Args:
            file_path: Path to save to (uses self.file_path if None)
            backup: Create backup before saving
        """
        save_path = file_path or self.file_path
        if not save_path:
            raise ValueError("No file path specified")
        
        if backup and os.path.exists(save_path):
            backup_path = save_path + '.bak'
            try:
                import shutil
                shutil.copy2(save_path, backup_path)
            except Exception as e:
                print(f"Error creating backup: {e}")
        
        try:
            with open(save_path, 'w', encoding='utf-8') as f:
                for x, y in self.points:
                    f.write(f"{x}|{y}\n")
        except Exception as e:
            print(f"Error saving LUT file {save_path}: {e}")
            raise
    
    def add_point(self, x: float, y: float):
        """
        Add a point to the curve
        
        Args:
            x: X value
            y: Y value
        """
        self.points.append((x, y))
        self.sort_points()
    
    def remove_point(self, index: int):
        """
        Remove a point from the curve
        
        Args:
            index: Index of point to remove
        """
        if 0 <= index < len(self.points):
            self.points.pop(index)
    
    def update_point(self, index: int, x: float, y: float):
        """
        Update a point in the curve
        
        Args:
            index: Index of point to update
            x: New X value
            y: New Y value
        """
        if 0 <= index < len(self.points):
            self.points[index] = (x, y)
            self.sort_points()
    
    def sort_points(self):
        """Sort points by X value"""
        self.points.sort(key=lambda p: p[0])
    
    def get_points(self) -> List[Tuple[float, float]]:
        """Get all points"""
        return self.points.copy()
    
    def interpolate(self, x: float) -> float:
        """
        Interpolate Y value for given X
        
        Args:
            x: X value
            
        Returns:
            Interpolated Y value
        """
        if not self.points:
            return 0.0
        
        # If x is before first point, return first Y
        if x <= self.points[0][0]:
            return self.points[0][1]
        
        # If x is after last point, return last Y
        if x >= self.points[-1][0]:
            return self.points[-1][1]
        
        # Find surrounding points and interpolate
        for i in range(len(self.points) - 1):
            x1, y1 = self.points[i]
            x2, y2 = self.points[i + 1]
            
            if x1 <= x <= x2:
                # Linear interpolation
                t = (x - x1) / (x2 - x1)
                return y1 + t * (y2 - y1)
        
        return 0.0
    
    def clear(self):
        """Clear all points"""
        self.points = []
    
    def __len__(self):
        """Return number of points"""
        return len(self.points)
    
    def __repr__(self):
        """String representation"""
        return f"LUTCurve(points={len(self.points)})"
