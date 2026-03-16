import os
import hashlib
from typing import List, Optional

class ChangeDetector:
    """
    Utility to detect changes in directories using MD5 hashing.
    Used for conditional deployments to speed up CI/CD.
    """
    @staticmethod
    def get_directory_hash(dir_path: str, exclude_patterns: Optional[List[str]] = None) -> str:
        """
        Generates a single MD5 hash for all files in a directory (recursive).
        """
        if not os.path.isdir(dir_path):
            raise ValueError(f"Path is not a directory: {dir_path}")

        hashes = []
        for root, dirs, files in os.walk(dir_path):
            # Sort to ensure consistent order
            files.sort()
            dirs.sort()
            
            for file in files:
                if exclude_patterns and any(p in file for p in exclude_patterns):
                    continue
                
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "rb") as f:
                        file_hash = hashlib.md5(f.read()).hexdigest()
                        hashes.append(file_hash)
                except (IOError, OSError):
                    continue

        return hashlib.md5("".join(hashes).encode()).hexdigest()

    @staticmethod
    def has_changed(dir_path: str, last_hash: Optional[str]) -> tuple[bool, str]:
        """
        Compares current directory hash with a provided last_hash.
        Returns (bool_changed, new_hash).
        """
        current_hash = ChangeDetector.get_directory_hash(dir_path)
        if last_hash is None or current_hash != last_hash:
            return True, current_hash
        return False, current_hash
