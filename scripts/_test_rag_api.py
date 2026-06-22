import sys, requests, json
sys.path.insert(0, '.')
# 先登录
login_r = requests.post('http://localhost:8001/api/v1/auth/login', json={'account': 'student40', 'password': '123456'}, timeout=120)
token = login_r.json()['data']['access_token']
print('token:', token[:50] + '...')

# 测试 ask
r = requests.post('http://localhost:8001/api/v1/rag/ask', json={'question': '孙悟空三打白骨精是哪一回？', 'top_k': 5}, headers={'Authorization': 'Bearer ' + token}, timeout=180)
print('HTTP:', r.status_code)
data = r.json()
print('code:', data.get('code'))
print('data keys:', list(data.get('data', {}).keys()) if isinstance(data.get('data'), dict) else repr(data.get('data'))[:100])
if data.get('data'):
    print('\nanswer:', data['data'].get('answer', '(none)')[:300])
    sources = data['data'].get('sources', [])
    print(f'sources: {len(sources)} 段')
    for s in sources:
        print(f'  - 《{s.get("book_name")}》第{s.get("chapter_no")}回 {s.get("chapter_title")} score={s.get("score"):.3f}')

