"""
Stage Tuning System for AC cars - One-click performance upgrades
Handles different logic for NA (Naturally Aspirated) and Turbo cars
"""

import os
from typing import Dict, Any, Optional
from .ac_ini import IniParser
from .ac_lut import LUTCurve


class StageTuner:
    """Handles stage-based tuning for AC cars (Stage 1/2/3)"""
    
    def __init__(self, car_data_path: str):
        """
        Initialize stage tuner
        
        Args:
            car_data_path: Path to car data folder
        """
        self.car_data_path = car_data_path
        self.engine_ini = None
        self.car_ini = None
        self.aero_ini = None
        self.drivetrain_ini = None
        
        self._load_ini_files()
        self.is_turbo = self._detect_turbo()
    
    def _load_ini_files(self):
        """Load relevant INI files"""
        ini_files = {
            'engine_ini': 'engine.ini',
            'car_ini': 'car.ini',
            'aero_ini': 'aero.ini',
            'drivetrain_ini': 'drivetrain.ini',
        }
        
        for attr, filename in ini_files.items():
            path = os.path.join(self.car_data_path, filename)
            if os.path.exists(path):
                try:
                    setattr(self, attr, IniParser(path))
                except Exception as e:
                    print(f"Failed to load {filename}: {e}")
    
    def _detect_turbo(self) -> bool:
        """
        Detect if car is turbocharged
        
        Returns:
            True if car has turbo sections in engine.ini
        """
        if not self.engine_ini:
            return False
        
        return self.engine_ini.has_section('TURBO_0')
    
    def get_current_stage(self) -> int:
        """
        Get current stage level (0 = stock, 1/2/3 = tuned)
        Based on markers in engine.ini
        
        Returns:
            Current stage (0-3)
        """
        if not self.engine_ini:
            return 0
        
        # Check for stage marker in engine.ini header comment
        stage_marker = self.engine_ini.get_value('HEADER', 'STAGE_LEVEL', default='0')
        try:
            return int(stage_marker)
        except ValueError:
            return 0
    
    def apply_stage_1(self) -> bool:
        """
        Apply Stage 1 tuning
        
        NA cars: More aggressive mapping (increase power curve by 8%)
        Turbo cars: Increase boost by 15%
        
        Returns:
            True if successful
        """
        try:
            if self.is_turbo:
                return self._apply_stage_1_turbo()
            else:
                return self._apply_stage_1_na()
        except Exception as e:
            print(f"Error applying Stage 1: {e}")
            return False
    
    def apply_stage_2(self) -> bool:
        """
        Apply Stage 2 tuning
        
        NA cars: Add turbo system (convert to turbo)
        Turbo cars: Increase boost by 30%
        
        Returns:
            True if successful
        """
        try:
            if self.is_turbo:
                return self._apply_stage_2_turbo()
            else:
                return self._apply_stage_2_na()
        except Exception as e:
            print(f"Error applying Stage 2: {e}")
            return False
    
    def apply_stage_3(self) -> bool:
        """
        Apply Stage 3 tuning
        
        NA cars: Turbo + mechanical modifications (increase power, reduce weight, improve aero)
        Turbo cars: More boost + mechanical + aero improvements
        
        Returns:
            True if successful
        """
        try:
            if self.is_turbo:
                return self._apply_stage_3_turbo()
            else:
                return self._apply_stage_3_na()
        except Exception as e:
            print(f"Error applying Stage 3: {e}")
            return False
    
    def _apply_stage_1_na(self) -> bool:
        """Stage 1 for NA: Increase power curve by 8%"""
        if not self.engine_ini:
            return False
        
        # Increase power curve
        power_lut_path = os.path.join(self.car_data_path, 'power.lut')
        if os.path.exists(power_lut_path):
            curve = LUTCurve(power_lut_path)
            for i in range(len(curve.points)):
                rpm, torque = curve.points[i]
                curve.points[i] = (rpm, torque * 1.08)
            curve.save(backup=True)
        
        # Mark stage
        self.engine_ini.set_value('HEADER', 'STAGE_LEVEL', '1')
        self.engine_ini.save(backup=True)
        
        return True
    
    def _apply_stage_1_turbo(self) -> bool:
        """Stage 1 for Turbo: Increase boost by 15%"""
        if not self.engine_ini or not self.engine_ini.has_section('TURBO_0'):
            return False
        
        # Increase max boost for all turbo units
        i = 0
        while self.engine_ini.has_section(f'TURBO_{i}'):
            current_boost = float(self.engine_ini.get_value(f'TURBO_{i}', 'MAX_BOOST', default='0'))
            new_boost = current_boost * 1.15
            self.engine_ini.set_value(f'TURBO_{i}', 'MAX_BOOST', str(new_boost))
            i += 1
        
        # Mark stage
        self.engine_ini.set_value('HEADER', 'STAGE_LEVEL', '1')
        self.engine_ini.save(backup=True)
        
        return True
    
    def _apply_stage_2_na(self) -> bool:
        """Stage 2 for NA: Add turbo system"""
        if not self.engine_ini:
            return False
        
        # Add turbo section if it doesn't exist
        if not self.engine_ini.has_section('TURBO_0'):
            # Create basic turbo configuration
            self.engine_ini.set_value('TURBO_0', 'LAG_DN', '0.92')
            self.engine_ini.set_value('TURBO_0', 'LAG_UP', '0.97')
            self.engine_ini.set_value('TURBO_0', 'MAX_BOOST', '0.35')
            self.engine_ini.set_value('TURBO_0', 'WASTEGATE', '0.50')
            self.engine_ini.set_value('TURBO_0', 'DISPLAY_MAX_BOOST', '1.0')
            self.engine_ini.set_value('TURBO_0', 'REFERENCE_RPM', '3000')
        
        # Increase power curve slightly (5% to account for turbo)
        power_lut_path = os.path.join(self.car_data_path, 'power.lut')
        if os.path.exists(power_lut_path):
            curve = LUTCurve(power_lut_path)
            for i in range(len(curve.points)):
                rpm, torque = curve.points[i]
                curve.points[i] = (rpm, torque * 1.05)
            curve.save(backup=True)
        
        # Mark stage
        self.engine_ini.set_value('HEADER', 'STAGE_LEVEL', '2')
        self.engine_ini.save(backup=True)
        
        return True
    
    def _apply_stage_2_turbo(self) -> bool:
        """Stage 2 for Turbo: Increase boost by 30%"""
        if not self.engine_ini or not self.engine_ini.has_section('TURBO_0'):
            return False
        
        # Increase max boost more aggressively
        i = 0
        while self.engine_ini.has_section(f'TURBO_{i}'):
            current_boost = float(self.engine_ini.get_value(f'TURBO_{i}', 'MAX_BOOST', default='0'))
            new_boost = current_boost * 1.30
            self.engine_ini.set_value(f'TURBO_{i}', 'MAX_BOOST', str(new_boost))
            i += 1
        
        # Mark stage
        self.engine_ini.set_value('HEADER', 'STAGE_LEVEL', '2')
        self.engine_ini.save(backup=True)
        
        return True
    
    def _apply_stage_3_na(self) -> bool:
        """Stage 3 for NA: Turbo + mechanical + aero modifications"""
        if not self.engine_ini:
            return False
        
        # Ensure turbo exists (from stage 2)
        if not self.engine_ini.has_section('TURBO_0'):
            self.engine_ini.set_value('TURBO_0', 'LAG_DN', '0.92')
            self.engine_ini.set_value('TURBO_0', 'LAG_UP', '0.97')
            self.engine_ini.set_value('TURBO_0', 'MAX_BOOST', '0.35')
            self.engine_ini.set_value('TURBO_0', 'WASTEGATE', '0.50')
            self.engine_ini.set_value('TURBO_0', 'DISPLAY_MAX_BOOST', '1.0')
            self.engine_ini.set_value('TURBO_0', 'REFERENCE_RPM', '3000')
        
        # Increase turbo boost further
        i = 0
        while self.engine_ini.has_section(f'TURBO_{i}'):
            current_boost = float(self.engine_ini.get_value(f'TURBO_{i}', 'MAX_BOOST', default='0'))
            new_boost = current_boost * 1.20
            self.engine_ini.set_value(f'TURBO_{i}', 'MAX_BOOST', str(new_boost))
            i += 1
        
        # Mechanical: Reduce engine inertia (faster revving)
        current_inertia = float(self.engine_ini.get_value('ENGINE_DATA', 'INERTIA', default='0.20'))
        self.engine_ini.set_value('ENGINE_DATA', 'INERTIA', str(current_inertia * 0.85))
        
        # Reduce weight by 5%
        if self.car_ini:
            current_mass = float(self.car_ini.get_value('BASIC', 'TOTALMASS', default='1400'))
            self.car_ini.set_value('BASIC', 'TOTALMASS', str(current_mass * 0.95))
            self.car_ini.save(backup=True)
        
        # Improve aerodynamics (reduce drag by 10%)
        if self.aero_ini:
            current_cd = float(self.aero_ini.get_value('HEADER', 'CD', default='0.35'))
            self.aero_ini.set_value('HEADER', 'CD', str(current_cd * 0.90))
            self.aero_ini.save(backup=True)
        
        # Increase power curve
        power_lut_path = os.path.join(self.car_data_path, 'power.lut')
        if os.path.exists(power_lut_path):
            curve = LUTCurve(power_lut_path)
            for i in range(len(curve.points)):
                rpm, torque = curve.points[i]
                curve.points[i] = (rpm, torque * 1.12)
            curve.save(backup=True)
        
        # Mark stage
        self.engine_ini.set_value('HEADER', 'STAGE_LEVEL', '3')
        self.engine_ini.save(backup=True)
        
        return True
    
    def _apply_stage_3_turbo(self) -> bool:
        """Stage 3 for Turbo: More boost + mechanical + aero"""
        if not self.engine_ini or not self.engine_ini.has_section('TURBO_0'):
            return False
        
        # Increase boost significantly
        i = 0
        while self.engine_ini.has_section(f'TURBO_{i}'):
            current_boost = float(self.engine_ini.get_value(f'TURBO_{i}', 'MAX_BOOST', default='0'))
            new_boost = current_boost * 1.50
            self.engine_ini.set_value(f'TURBO_{i}', 'MAX_BOOST', str(new_boost))
            i += 1
        
        # Mechanical: Reduce engine inertia
        current_inertia = float(self.engine_ini.get_value('ENGINE_DATA', 'INERTIA', default='0.20'))
        self.engine_ini.set_value('ENGINE_DATA', 'INERTIA', str(current_inertia * 0.85))
        
        # Increase RPM limit
        current_limiter = int(float(self.engine_ini.get_value('ENGINE_DATA', 'LIMITER', default='7000')))
        self.engine_ini.set_value('ENGINE_DATA', 'LIMITER', str(current_limiter + 500))
        
        # Reduce weight by 5%
        if self.car_ini:
            current_mass = float(self.car_ini.get_value('BASIC', 'TOTALMASS', default='1400'))
            self.car_ini.set_value('BASIC', 'TOTALMASS', str(current_mass * 0.95))
            self.car_ini.save(backup=True)
        
        # Improve aerodynamics
        if self.aero_ini:
            current_cd = float(self.aero_ini.get_value('HEADER', 'CD', default='0.35'))
            self.aero_ini.set_value('HEADER', 'CD', str(current_cd * 0.85))
            
            # Increase downforce if wings exist
            i = 0
            while self.aero_ini.has_section(f'WING_{i}'):
                current_cl = float(self.aero_ini.get_value(f'WING_{i}', 'CL', default='0.5'))
                self.aero_ini.set_value(f'WING_{i}', 'CL', str(current_cl * 1.15))
                i += 1
            
            self.aero_ini.save(backup=True)
        
        # Improve differential (better power handling)
        if self.drivetrain_ini and self.drivetrain_ini.has_section('DIFFERENTIAL'):
            current_power = float(self.drivetrain_ini.get_value('DIFFERENTIAL', 'POWER', default='0.10'))
            self.drivetrain_ini.set_value('DIFFERENTIAL', 'POWER', str(min(current_power * 1.20, 1.0)))
            self.drivetrain_ini.save(backup=True)
        
        # Increase power curve
        power_lut_path = os.path.join(self.car_data_path, 'power.lut')
        if os.path.exists(power_lut_path):
            curve = LUTCurve(power_lut_path)
            for i in range(len(curve.points)):
                rpm, torque = curve.points[i]
                curve.points[i] = (rpm, torque * 1.10)
            curve.save(backup=True)
        
        # Mark stage
        self.engine_ini.set_value('HEADER', 'STAGE_LEVEL', '3')
        self.engine_ini.save(backup=True)
        
        return True
    
    def get_stage_description(self, stage: int) -> Dict[str, str]:
        """
        Get description of what a stage does
        
        Args:
            stage: Stage number (1/2/3)
            
        Returns:
            Dictionary with title and description
        """
        if self.is_turbo:
            descriptions = {
                1: {
                    'title': 'Stage 1 - ECU Remap',
                    'description': '• Increase turbo boost by 15%\n• Safe power increase for daily driving'
                },
                2: {
                    'title': 'Stage 2 - Turbo Upgrade',
                    'description': '• Increase turbo boost by 30%\n• More aggressive tuning'
                },
                3: {
                    'title': 'Stage 3 - Full Build',
                    'description': '• Increase turbo boost by 50%\n• Increase RPM limit by 500\n• Reduce weight by 5%\n• Improve aerodynamics (drag -15%, downforce +15%)\n• Upgrade differential for better power handling\n• Increase power curve by 10%'
                }
            }
        else:
            descriptions = {
                1: {
                    'title': 'Stage 1 - ECU Remap',
                    'description': '• More aggressive engine mapping\n• Increase power curve by 8%\n• Optimized for NA performance'
                },
                2: {
                    'title': 'Stage 2 - Turbo Conversion',
                    'description': '• Add turbo system (0.35 bar boost)\n• Increase base power by 5%\n• Convert to turbocharged engine'
                },
                3: {
                    'title': 'Stage 3 - Full Turbo Build',
                    'description': '• Enhanced turbo boost (+20% over Stage 2)\n• Increase power curve by 12%\n• Reduce weight by 5%\n• Improve aerodynamics (drag -10%)\n• Reduce engine inertia by 15%'
                }
            }
        
        return descriptions.get(stage, {'title': 'Unknown Stage', 'description': ''})
    
    def reset_to_stock(self) -> bool:
        """
        Reset stage level to stock (remove stage marker)
        Note: Does not revert modifications, only clears the stage marker
        
        Returns:
            True if successful
        """
        if not self.engine_ini:
            return False
        
        try:
            if self.engine_ini.has_section('HEADER'):
                self.engine_ini.set_value('HEADER', 'STAGE_LEVEL', '0')
                self.engine_ini.save(backup=True)
            return True
        except Exception as e:
            print(f"Error resetting stage: {e}")
            return False
