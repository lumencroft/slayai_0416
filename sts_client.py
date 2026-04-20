import requests
from requests.exceptions import RequestException

class STSClient:
    def __init__(self, url="http://localhost:15526/api/v1/singleplayer"):
        self.url = url
        self.session = requests.Session()

    def get_state(self):
        try:
            response = self.session.get(self.url, params={"format": "json"}, timeout=3)
            response.raise_for_status()
            return response.json()
        except RequestException:
            return None

    def send_action(self, action_payload):
        if not action_payload: return False
        try:
            response = self.session.post(self.url, json=action_payload, timeout=3)
            response.raise_for_status()
            return True
        except RequestException as e:
            print(f"⚠️ [Network Error] 액션 전송 실패: {e}")
            return False