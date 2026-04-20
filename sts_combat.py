from sts_cards import CARD_DB
from action_generator import generate_all_actions 

class STSCombatAI:
    def __init__(self): 
        self.action_queue = []

    def get_action(self, raw_state):
        battle_info = raw_state.get("battle", {})
        if battle_info.get("turn") != "player" or not battle_info.get("is_play_phase", False):
            return {"action": "wait"}

        if self.action_queue:
            next_act = self.action_queue[0]
            if next_act.get("action") == "play_card":
                hand = raw_state.get("player", {}).get("hand", [])
                target_name = next_act.get("_card_name")
                
                found_idx = -1
                for i, c in enumerate(hand):
                    if c.get("name") == target_name and c.get("can_play", False):
                        found_idx = i
                        break
                
                if found_idx == -1:
                    self.action_queue.clear()
                    return {"action": "wait"}
                    
                out_payload = {"action": "play_card", "card_index": found_idx}
                if "target" in next_act:
                    out_payload["target"] = next_act["target"]
                
                self.action_queue.pop(0)
                return out_payload
            else:
                return self.action_queue.pop(0)

        p = raw_state.get("player", {})
        current_energy = int(p.get("energy", 3))
        hand = p.get("hand", [])
        enemies = battle_info.get("enemies", [])
        
        results = generate_all_actions(current_energy, hand, enemies)
        if not results:
            return {"action": "end_turn"}

        print("\n" + "="*60)
        print("🧠 [AI 시뮬레이션 결과 - 우선순위 Top 5]")
        for i, res in enumerate(results[:5]):
            c_names = [act.get("card_name", "턴 종료") if act["action"] == "play_card" else "턴 종료" for act in res["combo"]]
            print(f"\n[{i+1}순위] {' -> '.join(c_names)}")
            print(f"  🔥 적의 의도 데미지   : {res.get('incoming', 0)}")
            print(f"  🛡️ 플레이어 총 방어도 : {res.get('blk', 0)}")
            print(f"  🩸 예상 피해(HP 감소) : {res.get('loss', 0)}")
            print(f"  🎯 적에게 부여한 취약 : {res.get('vuln', 0)}")
            print(f"  ⚔️ 적에게 가한 총 피해 : {res.get('dmg', 0)}")
            if res.get("kills", 0) > 0:
                print(f"  💀 적 처치 수         : {res.get('kills', 0)}")
        print("="*60 + "\n")

        res = results[0]
        combo = res["combo"]
        
        idx_to_name = {c.get("index", i): c.get("name", "Unknown") for i, c in enumerate(hand)}
        idx_to_card = {c.get("index", i): c for i, c in enumerate(hand)}

        if res.get("_is_lethal"):
            print("\n" + "!"*70)
            print("💀 [킬각 감지] 막타 직전 리스타트 실행")
            
            cards_only = [act for act in combo if act["action"] == "play_card"]
            actions = []
            for act in cards_only[:-1]:
                card_idx = act["card_index"]
                card_name = idx_to_name.get(card_idx, "Unknown")
                card_data = CARD_DB.get(card_name, {})
                
                needs_target = idx_to_card.get(card_idx, {}).get("has_target", card_data.get("has_target", False))
                
                payload = {"action": "play_card", "_card_name": card_name}
                if needs_target and "target" in act:
                    payload["target"] = str(act["target"] + 1)
                    
                actions.append(payload)
            
            actions.append({"action": "restart_combat"})
            self.action_queue = actions
            
            combo_names = [idx_to_name.get(act["card_index"], "Unknown") for act in cards_only]
            print(f"🎯 실행: {' -> '.join(combo_names[:-1])} -> RESTART")
            print("!"*70 + "\n")
        else:
            actions = []
            combo_names = []
            for act in combo:
                if act["action"] == "play_card":
                    card_idx = act["card_index"]
                    card_name = idx_to_name.get(card_idx, "Unknown")
                    card_data = CARD_DB.get(card_name, {})
                    
                    needs_target = idx_to_card.get(card_idx, {}).get("has_target", card_data.get("has_target", False))

                    payload = {"action": "play_card", "_card_name": card_name}
                    if needs_target and "target" in act:
                        payload["target"] = str(act["target"] + 1)
                        
                    actions.append(payload)
                    combo_names.append(card_name)
                else:
                    actions.append({"action": "end_turn"})
                    combo_names.append("턴 종료")
            
            print(f"⚔️ 1순위 콤보 채택 및 실행: {' -> '.join(combo_names)}")
            self.action_queue = actions

        return self.get_action(raw_state)