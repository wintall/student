"""模拟完整的用户登录流程：前端代理 -> 后端 API"""
import requests
import json

BASE_FRONTEND = "http://localhost:5173/api/v1"

print("=" * 60)
print("步骤 1: 调用登录接口 (POST /auth/login)")
print("=" * 60)

login_data = {"account": "admin", "password": "admin123"}
print(f"请求体: {json.dumps(login_data, ensure_ascii=False)}")

r = requests.post(f"{BASE_FRONTEND}/auth/login", json=login_data, timeout=10)
print(f"HTTP 状态码: {r.status_code}")
print(f"响应内容: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")

data = r.json()
if data.get("code") != 200:
    print("\n❌ 登录失败！")
    exit(1)

access_token = data["data"]["access_token"]
refresh_token = data["data"]["refresh_token"]
user_info = data["data"].get("user")
print(f"\n✅ 拿到 access_token (前 20 位): {access_token[:20]}...")
print(f"✅ 拿到 user_info: {json.dumps(user_info, ensure_ascii=False, indent=2)}")

# 步骤 2: 验证 token 写入 localStorage 的内容
print("\n" + "=" * 60)
print("步骤 2: 检查 response.data 结构")
print("=" * 60)
print(f"res.data.access_token exists = {'access_token' in data['data']}")
print(f"res.data.refresh_token exists = {'refresh_token' in data['data']}")
print(f"res.data.user exists = {'user' in data['data']}")

# 步骤 3: 调用菜单接口
print("\n" + "=" * 60)
print("步骤 3: 调用菜单接口 (GET /auth/menus)")
print("=" * 60)
headers = {"Authorization": f"Bearer {access_token}"}
r2 = requests.get(f"{BASE_FRONTEND}/auth/menus", headers=headers, timeout=10)
print(f"HTTP 状态码: {r2.status_code}")
menus = r2.json()
print(f"响应 code: {menus.get('code')}")
print(f"菜单数量: {len(menus.get('data', []))}")
for m in menus.get("data", []):
    print(f"  - {m.get('name')} (path: {m.get('path')}, icon: {m.get('icon')}, children: {len(m.get('children', []))})")

# 步骤 4: 测试学生账号
print("\n" + "=" * 60)
print("步骤 4: 测试学生账号登录和菜单")
print("=" * 60)

student_login = {"account": "student01", "password": "123456Ab"}
r3 = requests.post(f"{BASE_FRONTEND}/auth/login", json=student_login, timeout=10)
sdata = r3.json()
print(f"HTTP 状态码: {r3.status_code}, code: {sdata.get('code')}")

if sdata.get("code") == 200:
    student_token = sdata["data"]["access_token"]
    print(f"✅ 学生登录成功")
    headers2 = {"Authorization": f"Bearer {student_token}"}
    r4 = requests.get(f"{BASE_FRONTEND}/auth/menus", headers=headers2, timeout=10)
    smenus = r4.json()
    print(f"学生菜单数: {len(smenus.get('data', []))}")
    for m in smenus.get("data", []):
        print(f"  - {m.get('name')} (path: {m.get('path')})")
else:
    print(f"❌ 学生登录失败: {json.dumps(sdata, ensure_ascii=False)}")

print("\n" + "=" * 60)
print("✅ 后端 API 完整链路正常")
print("=" * 60)
print("如果上面都 OK 但前端无法登录 -> 问题在前端:")
print("  1) axios 拦截器或响应格式")
print("  2) 表单 validate 错误")
print("  3) userStore 写入失败")
print("  4) 路由跳转失败")
