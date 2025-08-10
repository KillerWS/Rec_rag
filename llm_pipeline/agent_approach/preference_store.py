# pref_store.py
from typing import Dict, Any

class PreferenceStore:
    _instance = None          # -------- 单例保障 --------
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance.data = {}
        return cls._instance

    # --------------------------------------------------
    def update(self, slots: Dict[str, Any], mode: str = "overwrite"):
        if mode == "overwrite":
            self.data.update(slots)
        elif mode == "add":
            for k, v in slots.items():
                if k not in self.data:
                    self.data[k] = v
        elif mode == "remove":
            for k in slots:
                self.data.pop(k, None)

    def get(self) -> Dict[str, Any]:
        return self.data

    def reset(self):
        self.data.clear()
