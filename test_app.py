import requests

BASE_URL = "http://127.0.0.1:5000"

def test_home_status():
    response = requests.get(BASE_URL + "/")
    assert response.status_code == 200
    print("Teste de Status Home: PASSOU")

def test_login_page_exists():
    response = requests.get(BASE_URL + "/login")
    assert "Login" in response.text
    print("Teste de Conteúdo Login: PASSOU")

if __name__ == "__main__":
    test_home_status()
    test_login_page_exists()