from sts_client import STSClient
from sts_combat import STSCombatAI
from sts_choose import STSChooseAI

def main():
    client = STSClient()
    combat_ai = STSCombatAI()
    choose_ai = STSChooseAI()

    while True:
        raw_state = client.get_state()
        state_type = raw_state.get("state_type", "")
        
        if state_type in ["monster", "elite", "boss"]:
            battle_info = raw_state.get("battle", {})
            if battle_info.get("turn") != "player" or not battle_info.get("is_play_phase", False):
                continue
            action_payload = combat_ai.get_action(raw_state)
        elif state_type in ["map", "event", "rest", "shop", "reward", "chest", "choice"]:
            action_payload = choose_ai.get_action(raw_state)
        else:
            action_payload = {"action": "proceed"}

        if not action_payload or action_payload.get("action") == "wait":
            continue

        client.send_action(action_payload)
        
        act_type = action_payload.get("action")
        timeout_ticks = 0
        
        while True:
            check_state = client.get_state()
            
            timeout_ticks += 1
            print(f"Waiting for state change... (tick {timeout_ticks})")
            if timeout_ticks > 15:
                combat_ai.action_queue.clear()
                break
            
            if act_type == "play_card":
                old_hand = raw_state.get("player", {}).get("hand", [])
                new_hand = check_state.get("player", {}).get("hand", [])
                old_energy = raw_state.get("player", {}).get("energy", 0)
                new_energy = check_state.get("player", {}).get("energy", 0)
                
                if old_hand != new_hand or old_energy != new_energy:
                    break
            elif act_type == "end_turn":
                if not check_state.get("battle", {}).get("is_play_phase", False):
                    break
            elif act_type == "restart_combat":
                if check_state.get("state_type") in ["monster", "elite", "boss"] and check_state.get("battle", {}).get("is_play_phase", False):
                    break
            else:
                if check_state.get("state_type") != state_type:
                    break
                if check_state.get("screen_type") != raw_state.get("screen_type"):
                    break
        
if __name__ == "__main__":
    main()