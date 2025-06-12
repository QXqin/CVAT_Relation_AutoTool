import json
import os

# 默认规则
DEFAULT_RULES = {
    "bike": "on",
    "car": "on",
    "people": "on",
    "air conditioning": "mounted on",
    "manhole cover": "on",
    "potted plant": "on",
    "traditional window": "mounted on",
    "street light": "on",
    "pole": "on",
    "electric bicycle": "on",
    "debris": "on",
    "traffic cone": "on",
    "billboards": "mounted on",
    "signpost": "on"
}

RULES_FILE = "rules.json"

def load_rules():
    """加载规则配置"""
    try:
        if os.path.exists(RULES_FILE):
            with open(RULES_FILE, "r") as f:
                return json.load(f)
    except:
        pass
    return DEFAULT_RULES.copy()

def save_rules(rules):
    """保存规则配置"""
    with open(RULES_FILE, "w") as f:
        json.dump(rules, f, indent=2)