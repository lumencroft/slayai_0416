from sts_cards import CARD_DB
from action_generator import generate_all_actions  

class STSCombatAI:
    def __init__(self): 
        self.action_queue = [] 
        self.waiting_for_restart = False 

    def play_card(self, c_idx, target=None):
        payload = {"action": "play_card", "card_index": c_idx}
        if target is not None: payload["target"] = target
        return payload

    def end_turn(self): 
        return {"action": "end_turn"}
        
    def restart_combat(self): 
        return {"action": "restart_combat"}

    def print_hand(self, raw_state):
        for c in raw_state.get("player", {}).get("hand", []):
            n = c.get("name")
            db = CARD_DB.get(n, {})
            print(f"Index: {c.get('index')} | Name: {n} | Cost: {c.get('cost', db.get('cost', 0))} | Type: {db.get('type', 'unknown')} | Damage: {db.get('damage', 0)} | Block: {db.get('block', 0)}")

    def get_action(self, raw_state):
        if self.waiting_for_restart:
            print("\n전투 리스타트")
            self.waiting_for_restart = False
            return self.restart_combat()

        battle_info = raw_state.get("battle", {})
        if not battle_info.get("is_play_phase", False):
            return {"action": "proceed"}

        if self.action_queue:
            next_act = self.action_queue.pop(0)
            print(f"\n🚀 [테스트 모드] 콤보 이어서 실행 중... (남은 행동: {len(self.action_queue)}개) -> {next_act}")
            
            if not self.action_queue:
                self.waiting_for_restart = True
                
            if next_act["action"] == "play_card":
                return self.play_card(next_act["card_index"], next_act.get("target"))
            elif next_act["action"] == "end_turn":
                return self.end_turn()

        self.print_hand(raw_state)
        
        p = raw_state.get("player", {})
        current_energy = int(p.get("energy", 3))
        hand = p.get("hand", [])
        enemies = battle_info.get("enemies", [])
        
        final_combinations = generate_all_actions(current_energy, hand, enemies)
        
        if final_combinations:
            best_combo = final_combinations[0]
            print(f"\n🎯 [테스트 모드] 총 {len(best_combo)}개의 행동을 연속으로 실행")
            
            self.action_queue = best_combo.copy()
            first_act = self.action_queue.pop(0)
            print(f"🚀 [테스트 모드] 콤보 시작! -> {first_act}")
            
            if not self.action_queue:
                self.waiting_for_restart = True
                
            if first_act["action"] == "play_card":
                return self.play_card(first_act["card_index"], first_act.get("target"))
            elif first_act["action"] == "end_turn":
                return self.end_turn()

        return {"action": "proceed"}