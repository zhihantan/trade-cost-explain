"""Create or update the Genie space from src/genie/trade_cost_explain.geniespace.json.

    python src/genie/push_space.py create        → prints the new space id
    python src/genie/push_space.py update <id>   → pushes the current definition to an existing space
"""
import json
import sys
import time
from pathlib import Path

from databricks.sdk import WorkspaceClient

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_space import DESCRIPTION, TITLE  # noqa: E402

PROFILE, WAREHOUSE, PARENT = "fe-vm-zh-serverless", "5f36ded0f9befdd1", "/Workspace/Shared/trade-cost-explain"


def call(w, method, path, body):
    for attempt in range(4):
        try:
            return w.api_client.do(method, path, body=body)
        except Exception as e:  # transient VPN-egress IP ACL blocks
            if "IP ACL" in str(e) and attempt < 3:
                time.sleep(30)
                continue
            raise


def main():
    w = WorkspaceClient(profile=PROFILE)
    ss = json.dumps(json.loads((Path(__file__).resolve().parent / "trade_cost_explain.geniespace.json").read_text(encoding="utf-8")),
                    ensure_ascii=False)
    if sys.argv[1] == "create":
        r = call(w, "POST", "/api/2.0/genie/spaces", {"warehouse_id": WAREHOUSE, "title": TITLE, "description": DESCRIPTION,
                                                       "parent_path": PARENT, "serialized_space": ss})
    else:
        r = call(w, "PATCH", f"/api/2.0/genie/spaces/{sys.argv[2]}", {"title": TITLE, "description": DESCRIPTION,
                                                                       "warehouse_id": WAREHOUSE, "serialized_space": ss})
    print(json.dumps({k: r.get(k) for k in ("space_id", "title", "warehouse_id")}))


if __name__ == "__main__":
    main()
