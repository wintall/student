import sys, requests, json
sys.path.insert(0, '.')
r = requests.post('http://localhost:8001/api/v1/auth/login', json={'account': 'student40', 'password': '123456'}, timeout=60)
data = r.json()
print(json.dumps(data, ensure_ascii=False, indent=2)[:800])
if data.get('code') == 0:
    token = data['data']['access_token']
    print('\n✅ 登录成功, token:', token[:60] + '...')
    # 测试 RAG 接口
    r2 = requests.post('http://localhost:8001/api/v1/rag/search', json={'question': '孙悟空三打白骨精是哪一回？', 'top_k': 5}, headers={'Authorization': 'Bearer ' + token}, timeout=120)
    print('\nRAG 搜索:')
    print(json.dumps(r2.json(), ensure_ascii=False, indent=2)[:1000])
else:
    print('失败')
