import requests

def test_nl_db():
    url = "http://localhost:8000/api/v1/nl-db/chat"
    headers = {
        "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZXhwIjoxNzgyMjI5MjYwLCJ0eXBlIjoiYWNjZXNzIn0.Yogyp1XtiKA7nNmrjTVfrojl236H0MvqVe6RZ3xkH2s",
        "Content-Type": "application/json"
    }
    data = {"message": "查询所有学生"}
    
    try:
        response = requests.post(url, headers=headers, json=data)
        print(f"Status code: {response.status_code}")
        with open("test_result_2.txt", "w", encoding="utf-8") as f:
            f.write(response.text)
        print("Result saved to test_result_2.txt")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_nl_db()