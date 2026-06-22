import requests, json

print("=== 通过前端 localhost:5173 代理请求 ===")
try:
    r = requests.post('http://localhost:5173/api/v1/auth/login',
                     json={'account': 'admin', 'password': 'admin123'},
                     timeout=10)
    print(f"代理登录状态: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"响应 code: {data.get('code')}")
        print(f"用户: {data.get('data', {}).get('user', {}).get('real_name')}")
        token = data['data']['access_token']
        r2 = requests.get('http://localhost:5173/api/v1/auth/menus',
                         headers={'Authorization': f'Bearer {token}'},
                         timeout=10)
        print(f"菜单状态: {r2.status_code}")
        if r2.status_code == 200:
            menus = r2.json()['data']
            print(f"菜单数: {len(menus)}")
            for m in menus:
                print(f"  - {m.get('name')} (path: {m.get('path')}, children: {len(m.get('children', []))})")
    else:
        print(f"错误: {r.text[:500]}")
except Exception as e:
    print(f"异常: {e}")
