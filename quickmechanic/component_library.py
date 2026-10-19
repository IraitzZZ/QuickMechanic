"""
Component Library Manager for pre-built car components
"""

import json
import os
from typing import List, Dict, Optional, Any


class ComponentLibrary:
    """Manages library of pre-built car components"""
    
    COMPONENT_TYPES = [
        'engine',
        'suspension',
        'differential',
        'drivetrain',
        'aero',
        'gears',
        'tyres',
        'rto_final',
        'rto_ratios',
    ]
    
    def __init__(self, library_path: str = 'src/components/library.json'):
        """
        Initialize component library
        
        Args:
            library_path: Path to library JSON file
        """
        self.library_path = library_path
        self.components: Dict[str, List[Dict]] = {
            comp_type: [] for comp_type in self.COMPONENT_TYPES
        }
        
        # Create directory if needed
        os.makedirs(os.path.dirname(library_path), exist_ok=True)
        
        if os.path.exists(library_path):
            self.load()
        else:
            self._create_default_library()
            self.save()
    
    def load(self):
        """Load component library from file"""
        try:
            with open(self.library_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.components = data.get('components', self.components)
        except Exception as e:
            print(f"Error loading component library: {e}")
            self._create_default_library()
    
    def save(self):
        """Save component library to file"""
        try:
            data = {
                'version': '1.0',
                'components': self.components
            }
            with open(self.library_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error saving component library: {e}")
    
    def _create_default_library(self):
        """Create default component library with realistic presets"""
        # Engine components
        self.components['engine'] = [
            {
                'id': 'engine_na_street',
                'name': 'Street NA Engine',
                'description': 'Naturally aspirated street engine, 6000-8000 RPM',
                'tags': ['NA', 'street', 'low-power'],
                'data': {
                    'MINIMUM': 1000,
                    'MAXIMUM': 7000,
                    'LIMITER': 7500,
                    'INERTIA': 0.20,
                }
            },
            {
                'id': 'engine_na_race',
                'name': 'Race NA Engine',
                'description': 'High-revving naturally aspirated race engine, 9000+ RPM',
                'tags': ['NA', 'race', 'high-rpm'],
                'data': {
                    'MINIMUM': 2000,
                    'MAXIMUM': 9000,
                    'LIMITER': 9500,
                    'INERTIA': 0.12,
                }
            },
            {
                'id': 'engine_turbo_street',
                'name': 'Street Turbo Engine',
                'description': 'Turbocharged street engine with moderate boost',
                'tags': ['turbo', 'street', 'boost'],
                'data': {
                    'MINIMUM': 1000,
                    'MAXIMUM': 7000,
                    'LIMITER': 7500,
                    'INERTIA': 0.18,
                    'TURBO_MAX_BOOST': 1.0,
                    'TURBO_WASTEGATE': 0.8,
                }
            },
            {
                'id': 'engine_turbo_race',
                'name': 'Race Turbo Engine',
                'description': 'High-boost turbocharged race engine',
                'tags': ['turbo', 'race', 'high-boost'],
                'data': {
                    'MINIMUM': 1500,
                    'MAXIMUM': 8000,
                    'LIMITER': 8500,
                    'INERTIA': 0.15,
                    'TURBO_MAX_BOOST': 2.0,
                    'TURBO_WASTEGATE': 1.8,
                }
            }
        ]
        
        # Suspension components
        self.components['suspension'] = [
            {
                'id': 'suspension_street_soft',
                'name': 'Street Suspension (Soft)',
                'description': 'Comfortable street suspension with soft springs',
                'tags': ['street', 'soft', 'comfort'],
                'data': {
                    'FRONT_SPRING_RATE': 25000,
                    'REAR_SPRING_RATE': 28000,
                    'FRONT_DAMPER_FAST_BUMP': 2000,
                    'FRONT_DAMPER_FAST_REBOUND': 3500,
                    'FRONT_DAMPER_SLOW_BUMP': 1500,
                    'FRONT_DAMPER_SLOW_REBOUND': 3000,
                    'REAR_DAMPER_FAST_BUMP': 2200,
                    'REAR_DAMPER_FAST_REBOUND': 4000,
                    'REAR_DAMPER_SLOW_BUMP': 1800,
                    'REAR_DAMPER_SLOW_REBOUND': 3500,
                }
            },
            {
                'id': 'suspension_sport',
                'name': 'Sport Suspension',
                'description': 'Balanced sport suspension for street and track',
                'tags': ['sport', 'balanced', 'street-track'],
                'data': {
                    'FRONT_SPRING_RATE': 50000,
                    'REAR_SPRING_RATE': 55000,
                    'FRONT_DAMPER_FAST_BUMP': 3500,
                    'FRONT_DAMPER_FAST_REBOUND': 5500,
                    'FRONT_DAMPER_SLOW_BUMP': 2500,
                    'FRONT_DAMPER_SLOW_REBOUND': 4500,
                    'REAR_DAMPER_FAST_BUMP': 4000,
                    'REAR_DAMPER_FAST_REBOUND': 6000,
                    'REAR_DAMPER_SLOW_BUMP': 3000,
                    'REAR_DAMPER_SLOW_REBOUND': 5000,
                }
            },
            {
                'id': 'suspension_race_stiff',
                'name': 'Race Suspension (Stiff)',
                'description': 'Stiff race suspension for maximum grip',
                'tags': ['race', 'stiff', 'track'],
                'data': {
                    'FRONT_SPRING_RATE': 80000,
                    'REAR_SPRING_RATE': 85000,
                    'FRONT_DAMPER_FAST_BUMP': 5000,
                    'FRONT_DAMPER_FAST_REBOUND': 7500,
                    'FRONT_DAMPER_SLOW_BUMP': 3500,
                    'FRONT_DAMPER_SLOW_REBOUND': 6500,
                    'REAR_DAMPER_FAST_BUMP': 5500,
                    'REAR_DAMPER_FAST_REBOUND': 8000,
                    'REAR_DAMPER_SLOW_BUMP': 4000,
                    'REAR_DAMPER_SLOW_REBOUND': 7000,
                }
            }
        ]
        
        # Differential components
        self.components['differential'] = [
            {
                'id': 'diff_open',
                'name': 'Open Differential',
                'description': 'Standard open differential for street use',
                'tags': ['open', 'street', 'basic'],
                'data': {
                    'TYPE': 'OPEN',
                }
            },
            {
                'id': 'diff_lsd_street',
                'name': 'Street LSD',
                'description': 'Limited slip differential for street/sport use',
                'tags': ['lsd', 'street', 'sport'],
                'data': {
                    'TYPE': 'LSD',
                    'POWER': 0.30,
                    'COAST': 0.15,
                    'PRELOAD': 50,
                }
            },
            {
                'id': 'diff_lsd_race',
                'name': 'Race LSD',
                'description': 'Aggressive limited slip for racing',
                'tags': ['lsd', 'race', 'aggressive'],
                'data': {
                    'TYPE': 'LSD',
                    'POWER': 0.65,
                    'COAST': 0.35,
                    'PRELOAD': 100,
                }
            },
            {
                'id': 'diff_spool',
                'name': 'Spool (Locked)',
                'description': 'Fully locked differential for drag racing',
                'tags': ['spool', 'locked', 'drag'],
                'data': {
                    'TYPE': 'SPOOL',
                }
            }
        ]
        
        # Aerodynamics components
        self.components['aero'] = [
            {
                'id': 'aero_street',
                'name': 'Street Aero',
                'description': 'Minimal aerodynamics for street cars',
                'tags': ['street', 'low-downforce'],
                'data': {
                    'FRONT_LIFTCOEFF': -0.05,
                    'FRONT_CL_GAIN': 0.001,
                    'REAR_LIFTCOEFF': -0.10,
                    'REAR_CL_GAIN': 0.002,
                    'DRAG_COEFF': 0.30,
                }
            },
            {
                'id': 'aero_sport',
                'name': 'Sport Aero',
                'description': 'Moderate downforce for sport cars',
                'tags': ['sport', 'medium-downforce'],
                'data': {
                    'FRONT_LIFTCOEFF': -0.15,
                    'FRONT_CL_GAIN': 0.0025,
                    'REAR_LIFTCOEFF': -0.35,
                    'REAR_CL_GAIN': 0.004,
                    'DRAG_COEFF': 0.32,
                }
            },
            {
                'id': 'aero_race',
                'name': 'Race Aero',
                'description': 'High downforce for race cars',
                'tags': ['race', 'high-downforce'],
                'data': {
                    'FRONT_LIFTCOEFF': -0.30,
                    'FRONT_CL_GAIN': 0.005,
                    'REAR_LIFTCOEFF': -0.60,
                    'REAR_CL_GAIN': 0.008,
                    'DRAG_COEFF': 0.40,
                }
            }
        ]
        
        # Gear ratios presets
        self.components['gears'] = [
            {
                'id': 'gears_street_5speed',
                'name': 'Street 5-Speed',
                'description': 'Standard 5-speed manual gearbox for street cars',
                'tags': ['street', '5-speed', 'manual'],
                'data': {
                    'COUNT': 5,
                    'GEAR_R': -3.40,
                    'GEAR_1': 3.250,
                    'GEAR_2': 1.950,
                    'GEAR_3': 1.350,
                    'GEAR_4': 1.030,
                    'GEAR_5': 0.820,
                    'FINAL': 4.10,
                }
            },
            {
                'id': 'gears_sport_6speed',
                'name': 'Sport 6-Speed',
                'description': 'Sport 6-speed gearbox with closer ratios',
                'tags': ['sport', '6-speed', 'manual'],
                'data': {
                    'COUNT': 6,
                    'GEAR_R': -3.38,
                    'GEAR_1': 3.780,
                    'GEAR_2': 2.050,
                    'GEAR_3': 1.320,
                    'GEAR_4': 0.970,
                    'GEAR_5': 0.760,
                    'GEAR_6': 0.625,
                    'FINAL': 4.65,
                }
            },
            {
                'id': 'gears_race_6speed',
                'name': 'Race 6-Speed',
                'description': 'Racing sequential gearbox with short ratios',
                'tags': ['race', '6-speed', 'sequential'],
                'data': {
                    'COUNT': 6,
                    'GEAR_R': -2.90,
                    'GEAR_1': 2.650,
                    'GEAR_2': 1.780,
                    'GEAR_3': 1.360,
                    'GEAR_4': 1.090,
                    'GEAR_5': 0.920,
                    'GEAR_6': 0.790,
                    'FINAL': 3.90,
                }
            },
            {
                'id': 'gears_drift_6speed',
                'name': 'Drift 6-Speed',
                'description': 'Drift-oriented gearbox with tall first gear',
                'tags': ['drift', '6-speed', 'manual'],
                'data': {
                    'COUNT': 6,
                    'GEAR_R': -3.10,
                    'GEAR_1': 3.580,
                    'GEAR_2': 2.360,
                    'GEAR_3': 1.685,
                    'GEAR_4': 1.312,
                    'GEAR_5': 1.030,
                    'GEAR_6': 0.820,
                    'FINAL': 3.70,
                }
            }
        ]
        
        # Tyres presets
        self.components['tyres'] = [
            {
                'id': 'tyres_street',
                'name': 'Street Tyres',
                'description': 'Standard street tyres for daily driving',
                'tags': ['street', 'comfort', 'all-season'],
                'data': {
                    'NAME': 'Street',
                    'SHORT_NAME': 'ST',
                    'WIDTH': 0.225,
                    'RADIUS': 0.325,
                    'RIM_RADIUS': 0.2286,
                    'DX0': 1.30,
                    'DY0': 1.30,
                    'PRESSURE_IDEAL': 30,
                }
            },
            {
                'id': 'tyres_sport',
                'name': 'Sport Tyres',
                'description': 'High-performance sport tyres for spirited driving',
                'tags': ['sport', 'performance', 'summer'],
                'data': {
                    'NAME': 'Sport',
                    'SHORT_NAME': 'SP',
                    'WIDTH': 0.245,
                    'RADIUS': 0.330,
                    'RIM_RADIUS': 0.2413,
                    'DX0': 1.45,
                    'DY0': 1.40,
                    'PRESSURE_IDEAL': 32,
                }
            },
            {
                'id': 'tyres_semislick',
                'name': 'Semi-Slick Tyres',
                'description': 'Track-focused semi-slick tyres',
                'tags': ['track', 'semi-slick', 'race'],
                'data': {
                    'NAME': 'Semi-Slick',
                    'SHORT_NAME': 'SS',
                    'WIDTH': 0.265,
                    'RADIUS': 0.345,
                    'RIM_RADIUS': 0.254,
                    'DX0': 1.60,
                    'DY0': 1.55,
                    'PRESSURE_IDEAL': 35,
                }
            },
            {
                'id': 'tyres_slick_soft',
                'name': 'Soft Slick Tyres',
                'description': 'Racing slicks - soft compound for maximum grip',
                'tags': ['race', 'slick', 'soft'],
                'data': {
                    'NAME': 'Soft Slick',
                    'SHORT_NAME': 'SS',
                    'WIDTH': 0.305,
                    'RADIUS': 0.330,
                    'RIM_RADIUS': 0.254,
                    'DX0': 1.75,
                    'DY0': 1.70,
                    'PRESSURE_IDEAL': 27,
                }
            },
            {
                'id': 'tyres_slick_medium',
                'name': 'Medium Slick Tyres',
                'description': 'Racing slicks - medium compound for balanced performance',
                'tags': ['race', 'slick', 'medium'],
                'data': {
                    'NAME': 'Medium Slick',
                    'SHORT_NAME': 'MS',
                    'WIDTH': 0.305,
                    'RADIUS': 0.330,
                    'RIM_RADIUS': 0.254,
                    'DX0': 1.65,
                    'DY0': 1.62,
                    'PRESSURE_IDEAL': 28,
                }
            },
            {
                'id': 'tyres_slick_hard',
                'name': 'Hard Slick Tyres',
                'description': 'Racing slicks - hard compound for long-stint durability',
                'tags': ['race', 'slick', 'hard'],
                'data': {
                    'NAME': 'Hard Slick',
                    'SHORT_NAME': 'HS',
                    'WIDTH': 0.305,
                    'RADIUS': 0.330,
                    'RIM_RADIUS': 0.254,
                    'DX0': 1.55,
                    'DY0': 1.52,
                    'PRESSURE_IDEAL': 29,
                }
            }
        ]
        
        # RTO Final Drive Ratios presets
        self.components['rto_final'] = [
            {
                'id': 'rto_final_street',
                'name': 'Street Final Ratios',
                'description': 'Common final drive ratios for street cars',
                'tags': ['street', 'common'],
                'ratios': [4.90, 4.63, 4.35, 4.08, 3.89, 3.70]
            },
            {
                'id': 'rto_final_sport',
                'name': 'Sport Final Ratios',
                'description': 'Sport-oriented final drive ratios',
                'tags': ['sport', 'performance'],
                'ratios': [5.12, 4.75, 4.44, 4.10, 3.90]
            },
            {
                'id': 'rto_final_drift',
                'name': 'Drift Final Ratios',
                'description': 'Final drive ratios for drifting (lower for angle)',
                'tags': ['drift', 'low-ratio'],
                'ratios': [3.90, 3.70, 3.50, 3.30, 3.15]
            }
        ]
        
        # RTO Alternative Gear Sets presets
        self.components['rto_ratios'] = [
            {
                'id': 'rto_ratios_street',
                'name': 'Street Gear Ratios',
                'description': 'Alternative street gear ratios',
                'tags': ['street', 'comfort'],
                'ratios': [3.250, 1.950, 1.350, 1.030, 0.820]
            },
            {
                'id': 'rto_ratios_sport',
                'name': 'Sport Gear Ratios',
                'description': 'Closer sport ratios for track use',
                'tags': ['sport', 'close-ratio'],
                'ratios': [3.780, 2.050, 1.320, 0.970, 0.760, 0.625]
            },
            {
                'id': 'rto_ratios_race',
                'name': 'Race Gear Ratios',
                'description': 'Sequential race gearbox ratios',
                'tags': ['race', 'sequential'],
                'ratios': [2.650, 1.780, 1.360, 1.090, 0.920, 0.790]
            }
        ]
    
    def get_components(self, component_type: str) -> List[Dict]:
        """
        Get all components of a specific type
        
        Args:
            component_type: Type of component
            
        Returns:
            List of components
        """
        return self.components.get(component_type, [])
    
    def get_component(self, component_type: str, component_id: str) -> Optional[Dict]:
        """
        Get specific component by ID
        
        Args:
            component_type: Type of component
            component_id: Component ID
            
        Returns:
            Component dictionary or None
        """
        for component in self.components.get(component_type, []):
            if component.get('id') == component_id:
                return component
        return None
    
    def add_component(self, component_type: str, component: Dict) -> bool:
        """
        Add a new component to library
        
        Args:
            component_type: Type of component
            component: Component dictionary
            
        Returns:
            True if successful
        """
        if component_type not in self.COMPONENT_TYPES:
            print(f"Invalid component type: {component_type}")
            return False
        
        # Check if ID already exists
        component_id = component.get('id')
        if self.get_component(component_type, component_id):
            print(f"Component with ID {component_id} already exists")
            return False
        
        self.components[component_type].append(component)
        self.save()
        return True
    
    def update_component(self, component_type: str, component_id: str, component: Dict) -> bool:
        """
        Update existing component
        
        Args:
            component_type: Type of component
            component_id: Component ID
            component: Updated component dictionary
            
        Returns:
            True if successful
        """
        components = self.components.get(component_type, [])
        for i, comp in enumerate(components):
            if comp.get('id') == component_id:
                components[i] = component
                self.save()
                return True
        return False
    
    def delete_component(self, component_type: str, component_id: str) -> bool:
        """
        Delete component from library
        
        Args:
            component_type: Type of component
            component_id: Component ID
            
        Returns:
            True if successful
        """
        components = self.components.get(component_type, [])
        for i, comp in enumerate(components):
            if comp.get('id') == component_id:
                components.pop(i)
                self.save()
                return True
        return False
    
    def search_components(self, component_type: str, query: str) -> List[Dict]:
        """
        Search components by name or tags
        
        Args:
            component_type: Type of component
            query: Search query
            
        Returns:
            List of matching components
        """
        query = query.lower()
        results = []
        
        for component in self.components.get(component_type, []):
            name = component.get('name', '').lower()
            tags = ' '.join(component.get('tags', [])).lower()
            description = component.get('description', '').lower()
            
            if query in name or query in tags or query in description:
                results.append(component)
        
        return results
    
    def export_component(self, component_type: str, component_id: str, export_path: str) -> bool:
        """
        Export a single component to a JSON file
        
        Args:
            component_type: Type of component
            component_id: Component ID to export
            export_path: Path to export file
            
        Returns:
            True if successful
        """
        component = self.get_component(component_type, component_id)
        if not component:
            print(f"Component {component_id} not found")
            return False
        
        try:
            export_data = {
                'version': '1.0',
                'component_type': component_type,
                'component': component
            }
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=4)
            return True
        except Exception as e:
            print(f"Error exporting component: {e}")
            return False
    
    def export_all_components(self, export_path: str) -> bool:
        """
        Export all components to a JSON file
        
        Args:
            export_path: Path to export file
            
        Returns:
            True if successful
        """
        try:
            export_data = {
                'version': '1.0',
                'components': self.components
            }
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=4)
            return True
        except Exception as e:
            print(f"Error exporting components: {e}")
            return False
    
    def import_component(self, import_path: str, overwrite: bool = False) -> bool:
        """
        Import a single component from a JSON file
        
        Args:
            import_path: Path to import file
            overwrite: If True, overwrite existing component with same ID
            
        Returns:
            True if successful
        """
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Check if it's a single component or multiple
            if 'component' in data:
                # Single component
                component_type = data.get('component_type')
                component = data.get('component')
                
                if not component_type or not component:
                    print("Invalid component file format")
                    return False
                
                # Check if component exists
                component_id = component.get('id')
                existing = self.get_component(component_type, component_id)
                
                if existing and overwrite:
                    # Update existing component
                    return self.update_component(component_type, component_id, component)
                elif existing and not overwrite:
                    print(f"Component {component_id} already exists. Use overwrite=True to replace.")
                    return False
                else:
                    # Add new component
                    return self.add_component(component_type, component)
            else:
                print("Invalid component file format")
                return False
                
        except Exception as e:
            print(f"Error importing component: {e}")
            return False
    
    def import_components(self, import_path: str) -> bool:
        """
        Import multiple components from a JSON file
        
        Args:
            import_path: Path to import file
            
        Returns:
            True if successful
        """
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Check if it's a library export
            if 'components' in data:
                imported_components = data.get('components', {})
                
                # Merge components
                for comp_type, comps in imported_components.items():
                    if comp_type in self.COMPONENT_TYPES:
                        for component in comps:
                            # Check if component already exists
                            component_id = component.get('id')
                            if not self.get_component(comp_type, component_id):
                                self.components[comp_type].append(component)
                
                self.save()
                return True
            else:
                print("Invalid component library file format")
                return False
                
        except Exception as e:
            print(f"Error importing components: {e}")
            return False
    
    def filter_by_tags(self, component_type: str, tags: List[str]) -> List[Dict]:
        """
        Filter components by tags
        
        Args:
            component_type: Type of component
            tags: List of tags to filter by
            
        Returns:
            List of matching components
        """
        results = []
        
        for component in self.components.get(component_type, []):
            component_tags = component.get('tags', [])
            # Check if any of the filter tags match
            if any(tag in component_tags for tag in tags):
                results.append(component)
        
        return results
