"""
UI Manager for handling Assetto Corsa ui_car.json files
"""

import json
import os
from typing import Dict, Any, Optional


class UIManager:
    """Manages UI folder files like ui_car.json for AC cars"""
    
    def __init__(self, car_path: str):
        """
        Initialize UI manager
        
        Args:
            car_path: Path to car folder (e.g., content/cars/car_name)
        """
        self.car_path = car_path
        self.ui_path = os.path.join(car_path, 'ui')
        self.ui_car_json_path = os.path.join(self.ui_path, 'ui_car.json')
        self.ui_data = {}
        
        if os.path.exists(self.ui_car_json_path):
            self.load()
    
    def load(self) -> bool:
        """
        Load ui_car.json file
        
        Returns:
            True if loaded successfully
        """
        if not os.path.exists(self.ui_car_json_path):
            return False
        
        try:
            with open(self.ui_car_json_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.ui_data = json.loads(content, strict=False)
            return True
        except Exception as e:
            print(f"Error loading ui_car.json: {e}")
            return False
    
    def save(self, backup: bool = True) -> bool:
        """
        Save ui_car.json file
        
        Args:
            backup: Create .bak backup before saving
            
        Returns:
            True if saved successfully
        """
        if not self.ui_data:
            return False
        
        try:
            # Create ui folder if it doesn't exist
            os.makedirs(self.ui_path, exist_ok=True)
            
            # Create backup if requested
            if backup and os.path.exists(self.ui_car_json_path):
                backup_path = self.ui_car_json_path + '.bak'
                with open(self.ui_car_json_path, 'r', encoding='utf-8') as f:
                    backup_content = f.read()
                with open(backup_path, 'w', encoding='utf-8') as f:
                    f.write(backup_content)
            
            # Save ui_car.json
            with open(self.ui_car_json_path, 'w', encoding='utf-8') as f:
                json.dump(self.ui_data, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            print(f"Error saving ui_car.json: {e}")
            return False
    
    def get_name(self) -> str:
        """Get car display name"""
        return self.ui_data.get('name', '')
    
    def set_name(self, name: str):
        """Set car display name"""
        self.ui_data['name'] = name
    
    def get_brand(self) -> str:
        """Get car brand"""
        return self.ui_data.get('brand', '')
    
    def set_brand(self, brand: str):
        """Set car brand"""
        self.ui_data['brand'] = brand
    
    def get_description(self) -> str:
        """Get car description"""
        return self.ui_data.get('description', '')
    
    def set_description(self, description: str):
        """Set car description"""
        self.ui_data['description'] = description
    
    def get_class(self) -> str:
        """Get car class (street, race, etc.)"""
        return self.ui_data.get('class', 'street')
    
    def set_class(self, car_class: str):
        """Set car class"""
        self.ui_data['class'] = car_class
    
    def get_country(self) -> str:
        """Get car country"""
        return self.ui_data.get('country', '')
    
    def set_country(self, country: str):
        """Set car country"""
        self.ui_data['country'] = country
    
    def get_tags(self) -> list:
        """Get car tags"""
        return self.ui_data.get('tags', [])
    
    def set_tags(self, tags: list):
        """Set car tags"""
        self.ui_data['tags'] = tags
    
    def get_specs(self) -> Dict[str, str]:
        """Get car specs"""
        return self.ui_data.get('specs', {})
    
    def set_specs(self, specs: Dict[str, str]):
        """Set car specs"""
        self.ui_data['specs'] = specs
    
    def get_year(self) -> int:
        """Get car year"""
        return self.ui_data.get('year', 0)
    
    def set_year(self, year: int):
        """Set car year"""
        self.ui_data['year'] = year
    
    def get_author(self) -> str:
        """Get car author"""
        return self.ui_data.get('author', '')
    
    def set_author(self, author: str):
        """Set car author"""
        self.ui_data['author'] = author
    
    def get_version(self) -> str:
        """Get car version"""
        return self.ui_data.get('version', '')
    
    def set_version(self, version: str):
        """Set car version"""
        self.ui_data['version'] = version
    
    def get_all_data(self) -> Dict[str, Any]:
        """Get all ui_car.json data"""
        return self.ui_data.copy()
    
    def set_all_data(self, data: Dict[str, Any]):
        """Set all ui_car.json data"""
        self.ui_data = data.copy()
    
    def has_ui_car_json(self) -> bool:
        """Check if ui_car.json exists"""
        return os.path.exists(self.ui_car_json_path)
    
    def create_default_ui_car_json(self, car_name: str):
        """
        Create a default ui_car.json file
        
        Args:
            car_name: Car folder name to use as fallback name
        """
        self.ui_data = {
            'name': car_name,
            'brand': '',
            'class': 'street',
            'country': '',
            'description': '',
            'tags': [],
            'specs': {
                'bhp': '',
                'torque': '',
                'weight': '',
                'topspeed': '',
                'acceleration': '',
                'pwratio': ''
            },
            'year': 0,
            'author': '',
            'version': ''
        }
