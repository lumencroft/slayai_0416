import requests
import time
from sts_combat import STSCombatAI
from sts_choose import STSChooseAI

API_URL = "http://localhost:15526/api/v1/singleplayer"

def main():
    combat_ai = STSCombatAI()
    choose_ai = STSChooseAI()
    
    while True:
        response = requests.get(API_URL, params={"format": "json"}, timeout=3)
        response.raise_for_status()
        raw_state = response.json()
        state_type = raw_state.get("state_type", "")

        if state_type in ["monster", "elite", "boss"]:
            action_payload = combat_ai.get_action(raw_state)
        elif state_type in ["map", "event", "rest", "shop", "reward", "chest", "choice"]:
            action_payload = choose_ai.get_action(raw_state)
        else:
            action_payload = {"action": "proceed"}

        if action_payload:
            requests.post(API_URL, json=action_payload, timeout=3)
        
        time.sleep(0.1)

if __name__ == "__main__":
    main()