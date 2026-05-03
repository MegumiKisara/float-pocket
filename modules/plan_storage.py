import json
import os
import uuid
from datetime import datetime

from modules.config_module import DATA_DIR

PLANS_FILE = os.path.join(DATA_DIR, "plans.json")


class PlanStorage:
    def __init__(self):
        self._tasks = []
        self._load()

    def _load(self):
        if os.path.exists(PLANS_FILE):
            try:
                with open(PLANS_FILE, "r", encoding="utf-8") as f:
                    self._tasks = json.load(f)
            except Exception:
                self._tasks = []

    def _save(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(PLANS_FILE, "w", encoding="utf-8") as f:
            json.dump(self._tasks, f, ensure_ascii=False, indent=2)

    def get_all(self):
        return list(self._tasks)

    def add(self, title: str):
        task = {
            "id": uuid.uuid4().hex[:12],
            "title": title.strip(),
            "completed": False,
            "created_at": datetime.now().isoformat(),
            "order": len(self._tasks),
        }
        self._tasks.append(task)
        self._save()
        return task

    def update(self, task_id: str, **kwargs):
        for task in self._tasks:
            if task["id"] == task_id:
                task.update(kwargs)
                self._save()
                return task
        return None

    def delete(self, task_id: str):
        self._tasks = [t for t in self._tasks if t["id"] != task_id]
        self._save()

    def clear_completed(self):
        self._tasks = [t for t in self._tasks if not t["completed"]]
        self._save()

    def clear_all(self):
        self._tasks = []
        self._save()
