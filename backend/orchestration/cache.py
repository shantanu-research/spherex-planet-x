"""
SPHEREx Planet X Challenge - Two-Tier Cache System
In-memory LRU metadata cache + persistent JSON/binary disk cache.
"""

import os
import json
import hashlib
from typing import Any, Optional

CACHE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "cache"))
os.makedirs(CACHE_DIR, exist_ok=True)

class TwoTierCache:
    def __init__(self, max_memory_entries: int = 256):
        self._memory_cache = {}
        self._access_order = []
        self._max_memory = max_memory_entries

    def _make_key(self, prefix: str, **kwargs) -> str:
        serialized = json.dumps(kwargs, sort_keys=True)
        h = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]
        return f"{prefix}_{h}"

    def get(self, key: str) -> Optional[Any]:
        # Tier 1: In-memory
        if key in self._memory_cache:
            self._access_order.remove(key)
            self._access_order.append(key)
            return self._memory_cache[key]
            
        # Tier 2: Disk cache
        disk_path = os.path.join(CACHE_DIR, f"{key}.json")
        if os.path.exists(disk_path):
            try:
                with open(disk_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.set(key, data, write_disk=False)
                return data
            except Exception:
                return None
        return None

    def set(self, key: str, value: Any, write_disk: bool = True):
        # Evict LRU from memory if full
        if len(self._memory_cache) >= self._max_memory and key not in self._memory_cache:
            lru_key = self._access_order.pop(0)
            self._memory_cache.pop(lru_key, None)
            
        self._memory_cache[key] = value
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)
        
        # Write to disk
        if write_disk:
            disk_path = os.path.join(CACHE_DIR, f"{key}.json")
            try:
                with open(disk_path, "w", encoding="utf-8") as f:
                    json.dump(value, f)
            except Exception:
                pass

cache_instance = TwoTierCache()
