import requests
import toml
import threading
import json
import time
import os
from urllib.parse import urlparse
from typing import Dict, Any
from typing import Optional

output_path = "onebot_plugins.json"
result_data: Dict[str, Any] = {"num": 0, "name": []}
lock = threading.Lock()

# 尝试恢复已有数据
def load_existing_data():
    global result_data
    if os.path.exists(output_path):
        try:
            with open(output_path, 'r', encoding='utf-8') as f:
                result_data = json.load(f)
        except Exception as e:
            print(f"Failed to load existing result file: {e}")

load_existing_data()




def get_pyproject_toml_url(homepage: str) -> Optional[str]:
    parsed = urlparse(homepage)
    if 'github.com' not in parsed.netloc:
        return None

    parts = parsed.path.strip('/').split('/')
    if len(parts) < 2:
        return None

    user, repo = parts[:2]
    for branch in ("main", "master"):
        raw_url = f"https://raw.githubusercontent.com/{user}/{repo}/{branch}/pyproject.toml"
        if requests.head(raw_url).status_code == 200:
            return raw_url
    return None

def check_onebot_dependency(pyproject_url: str) -> bool:
    try:
        response = requests.get(pyproject_url, timeout=10)
        response.raise_for_status()
        data = toml.loads(response.text)

        poetry_deps = data.get('tool', {}).get('poetry', {}).get('dependencies', {})
        if isinstance(poetry_deps, dict) and 'nonebot-adapter-onebot' in poetry_deps:
            return True

        project_deps = data.get('project', {}).get('dependencies', [])
        for dep in project_deps:
            if isinstance(dep, str) and dep.startswith('nonebot-adapter-onebot'):
                return True

        return False
    except Exception as e:
        print(f"Error fetching or parsing pyproject.toml: {e}")
        return False

def fetch_all_plugins() -> list:
    url = "https://registry.nonebot.dev/plugins.json"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Failed to fetch plugins list: {e}")
        return []

def save_result_periodically():
    while True:
        time.sleep(2)
        with lock:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result_data, f, ensure_ascii=False, indent=2)

def main():
    plugins = fetch_all_plugins()

    thread = threading.Thread(target=save_result_periodically, daemon=True)
    thread.start()

    for plugin in plugins:
        homepage = plugin.get("homepage")
        name = plugin.get("name")

        # 如果已存在，跳过
        with lock:
            result_data["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
            if name in result_data["name"]:
                print(f"{name}: Already processed, skipping")
                continue

        if not homepage:
            print(f"{name}: No homepage URL")
            continue

        pyproject_url = get_pyproject_toml_url(homepage)
        if not pyproject_url:
            print(f"{name}: Invalid or unsupported GitHub URL")
            continue

        has_onebot = check_onebot_dependency(pyproject_url)
        print(f"{name}: Depends on nonebot-adapter-onebot -> {has_onebot}")

        if has_onebot:
            with lock:
                result_data["num"] += 1
                result_data["name"].append(name)

if __name__ == "__main__":
    main()
    time.sleep(5)
