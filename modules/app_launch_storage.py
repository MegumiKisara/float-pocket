import json
import os
import uuid

from modules.config_module import DATA_DIR

APPS_FILE = os.path.join(DATA_DIR, "apps.json")

_DEFAULT_CATEGORY_ID = "default"


class AppLaunchStorage:
    def __init__(self):
        self._categories = []
        self._apps = []
        self._load()

    def reload(self):
        self._load()

    def _load(self):
        if os.path.exists(APPS_FILE):
            try:
                with open(APPS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._categories = data.get("categories", [])
                    self._apps = data.get("apps", [])
            except Exception:
                self._categories = []
                self._apps = []
        self._ensure_default_category()

    def _save(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(APPS_FILE, "w", encoding="utf-8") as f:
            json.dump({"categories": self._categories, "apps": self._apps}, f, ensure_ascii=False, indent=2)

    def _ensure_default_category(self):
        if not any(c["id"] == _DEFAULT_CATEGORY_ID for c in self._categories):
            self._categories.insert(0, {"id": _DEFAULT_CATEGORY_ID, "name": "默认未分类", "order": 0})
            self._save()

    # ── categories ───────────────────────────────────────────

    def get_categories(self):
        return list(self._categories)

    def add_category(self, name: str):
        cat = {"id": uuid.uuid4().hex[:12], "name": name.strip(), "order": len(self._categories)}
        self._categories.append(cat)
        self._save()
        return cat

    def rename_category(self, cat_id: str, new_name: str):
        for cat in self._categories:
            if cat["id"] == cat_id:
                cat["name"] = new_name.strip()
                self._save()
                return True
        return False

    def delete_category(self, cat_id: str):
        if cat_id == _DEFAULT_CATEGORY_ID:
            return False
        # Move apps in this category to default
        for app in self._apps:
            if app.get("category_id") == cat_id:
                app["category_id"] = _DEFAULT_CATEGORY_ID
        self._categories = [c for c in self._categories if c["id"] != cat_id]
        self._save()
        return True

    def has_apps_in_category(self, cat_id: str) -> bool:
        return any(app.get("category_id") == cat_id for app in self._apps)

    # ── apps ─────────────────────────────────────────────────

    def get_apps(self):
        return list(self._apps)

    def get_apps_by_category(self):
        result = {}
        for cat in self._categories:
            result[cat["id"]] = {"category": cat, "apps": []}
        for app in self._apps:
            cid = app.get("category_id", _DEFAULT_CATEGORY_ID)
            if cid in result:
                result[cid]["apps"].append(app)
            else:
                result.setdefault(_DEFAULT_CATEGORY_ID, {"category": self._get_default_cat(), "apps": []})
                result[_DEFAULT_CATEGORY_ID]["apps"].append(app)
        return result

    def add_app(self, name: str, path: str, category_id: str = None) -> dict:
        app = {
            "id": uuid.uuid4().hex[:12],
            "name": name.strip(),
            "path": path.strip(),
            "icon_path": "",
            "category_id": category_id or _DEFAULT_CATEGORY_ID,
            "order": len(self._apps),
        }
        self._apps.append(app)
        self._save()
        return app

    def update_app(self, app_id: str, **kwargs):
        for app in self._apps:
            if app["id"] == app_id:
                app.update(kwargs)
                self._save()
                return app
        return None

    def delete_app(self, app_id: str):
        self._apps = [a for a in self._apps if a["id"] != app_id]
        self._save()

    def _get_default_cat(self):
        for c in self._categories:
            if c["id"] == _DEFAULT_CATEGORY_ID:
                return c
        return {"id": _DEFAULT_CATEGORY_ID, "name": "默认未分类", "order": 0}
