import json
import os

# 默认配置
DEFAULT_CONFIG = {
    "auto_sync_lifecycle": True,
    "auto_generate_output": True,
    "backup_original": True,
    "skip_existing": True
}

CONFIG_FILE = "config.json"

def load_config():
    """加载配置"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
    except:
        pass
    return DEFAULT_CONFIG.copy()

def save_config(config):
    """保存配置"""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)