import requests
import json

BASE = "http://127.0.0.1:8000/api/v1"


def test_role(account, password):
    r = requests.post(f"{BASE}/auth/login", json={"account": account, "password": password})
    data = r.json()["data"]
    token = data["access_token"]
    user = data.get("user", {})

    menu_res = requests.get(
        f"{BASE}/auth/menus", headers={"Authorization": "Bearer " + token}
    )
    menus = menu_res.json()["data"]

    role_names = [r["name"] for r in user.get("roles", [])]
    print(f'=== {account} ({user.get("real_name", "?")}) ===')
    print(f"  角色: {role_names}")
    for m in menus:
        if m.get("children"):
            child_names = [c["name"] for c in m["children"]]
            print(f"    {m['name']}: {child_names}")
        else:
            print(f"    {m['name']}")
    print()


if __name__ == "__main__":
    test_role("admin", "admin123")
    test_role("teacher01", "123456Ab")
    test_role("teacher02", "123456Ab")
    test_role("teacher04", "123456Ab")
    test_role("teacher07", "123456Ab")
    test_role("teacher12", "123456Ab")
    test_role("student01", "123456Ab")
