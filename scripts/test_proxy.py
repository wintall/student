import requests, json

# 1. 直接请求后端
print("=== 直接请求后端 ===")
r = requests.post('http://127.0.0.1:8000/api/v1/auth/login', json={'account': 'admin', 'password': 'admin123'})
print(f"直接登录状态: {r.status_code}")
data = r.json()
token = data['data']['access_token']
print(f"用户名: {data['data']['user']['real_name']}")

# 2. 通过前端代理请求 (端口 5173 和 5174)
for port in [5173, 5174]:
    print(f"\n=== 通过前端 127.0.0.1:{port} 代理请求 ===")
    try:
        r2 = requests.post(f'http://127.0.0.1:{port}/api/v1/auth/login',
                          json={'account': 'admin', 'password': 'admin123'},
                          timeout=5)
        print(f"代理登录状态: {r2.status_code}")
        if r2.status_code == 200:
            print(f"返回: {json.dumps(r2.json()['data'].get('user', {}).get('real_name'), ensure_ascii=False)}")
            # 测试获取菜单
            token2 = r2.json()['data']['access_token']
            r3 = requests.get(f'http://127.0.0.1:{port}/api/v1/auth/menus',
                             headers={'Authorization': f'Bearer {token2}'},
                             timeout=5)
            print(f"菜单状态: {r3.status_code}, 菜单数: {len(r3.json()['data'])}")
        else:
            print(f"错误响应: {r2.text[:200]}")
    except Exception as e:
        print(f"异常: {e}")
