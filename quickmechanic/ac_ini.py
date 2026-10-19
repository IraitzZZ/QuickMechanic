"""
INI File Parser for Assetto Corsa car configuration files
"""

import configparser
import os
from typing import Dict, Any, Optional


class IniParser:
    """Parser for Assetto Corsa .ini configuration files"""
    
    def __init__(self, file_path: str):
        """
        Initialize INI parser
        
        Args:
            file_path: Path to the .ini file
        """
        self.file_path = file_path
        self.config = configparser.ConfigParser(inline_comment_prefixes=(';', '#'))
        self.config.optionxform = str  # Preserve case sensitivity
        self._dirty = False  # True only after set_value() is called
        
        if os.path.exists(file_path):
            self.load()
    
    def load(self):
        """Load INI file"""
        try:
            self.config.read(self.file_path, encoding='utf-8-sig')
        except configparser.ParsingError as e:
            print(f"Error loading INI file {self.file_path}: {e}")
            print(f"Warning: INI file contains parsing errors. The file may have malformed lines.")
            print(f"The editor will open but this tab may not function correctly.")
            # Don't raise - allow the application to continue with empty config
        except Exception as e:
            print(f"Error loading INI file {self.file_path}: {e}")
            raise
    
    def save(self, backup=True):
        """
        Save INI file. Does nothing if no values were changed via set_value().

        Args:
            backup: Create backup before saving
        """
        if not self._dirty:
            return

        if backup and os.path.exists(self.file_path):
            backup_path = self.file_path + '.bak'
            try:
                import shutil
                shutil.copy2(self.file_path, backup_path)
            except Exception as e:
                print(f"Error creating backup: {e}")
        
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                # space_around_delimiters=False writes KEY=VALUE (no spaces).
                # AC requires this exact format; KEY = VALUE causes crashes.
                self.config.write(f, space_around_delimiters=False)
            self._dirty = False
        except Exception as e:
            print(f"Error saving INI file {self.file_path}: {e}")
            raise
    
    def get_value(self, section: str, key: str, default: Any = None) -> Optional[str]:
        """
        Get value from INI file
        
        Args:
            section: Section name
            key: Key name
            default: Default value if not found
            
        Returns:
            Value as string or default
        """
        try:
            value = self.config.get(section, key)
            if value:
                value = value.strip()
                # AC INI files often use inline comments without preceding whitespace
                # (e.g. "LAG_UP=0.9965; some comment"), which configparser's
                # inline_comment_prefixes doesn't handle. Strip them manually.
                for prefix in (';', '#'):
                    idx = value.find(prefix)
                    if idx != -1:
                        value = value[:idx].strip()
            return value if value else value
        except (configparser.NoSectionError, configparser.NoOptionError):
            return default
    
    def set_value(self, section: str, key: str, value: Any):
        """
        Set value in INI file. Marks the parser dirty only if the value
        actually differs from what is currently stored.

        Args:
            section: Section name
            key: Key name
            value: Value to set
        """
        new_str = str(value)
        if not self.config.has_section(section):
            self.config.add_section(section)
            self._dirty = True
        else:
            try:
                current = self.config.get(section, key)
            except configparser.NoOptionError:
                current = None
            if current != new_str:
                # Avoid false-dirty from format differences (e.g. "0.15" vs "0.1500").
                # If both values are numeric, compare them as floats.
                try:
                    if abs(float(current) - float(new_str)) > 1e-9:
                        self._dirty = True
                except (TypeError, ValueError):
                    self._dirty = True
        self.config.set(section, key, new_str)
    
    def get_section(self, section: str) -> Dict[str, str]:
        """
        Get all key-value pairs from a section
        
        Args:
            section: Section name
            
        Returns:
            Dictionary of key-value pairs
        """
        if self.config.has_section(section):
            return dict(self.config.items(section))
        return {}
    
    def get_sections(self):
        """Get all section names"""
        return self.config.sections()
    
    def remove_section(self, section: str) -> bool:
        """Remove a section from the INI file. Returns True if the section existed."""
        removed = self.config.remove_section(section)
        if removed:
            self._dirty = True
        return removed

    def has_section(self, section: str) -> bool:
        """Check if section exists"""
        return self.config.has_section(section)
