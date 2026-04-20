from sts_cards import CARD_DB
from action_generator import generate_all_actions 

class STSCombatAI:
    def __init__(self): 
        self.action_queue = []
        self.combat_finished = True
        self.reset_dfs()

    def reset_dfs(self):
        self.is_searching = True
        self.to_explore = []
        self.target_path = []
        self.best_path = []
        self.best_loss = float('inf')
        self.start_hp = -1
        self.current_depth = 0

    def get_action(self, raw_state):
        if self.combat_finished:
            self.reset_dfs()
            self.combat_finished = False

        battle_info = raw_state.get("battle", {})
        if battle_info.get("turn") != "player" or not battle_info.get("is_play_phase", False):
            return {"action": "wait"}

        if self.action_queue:
            next_act = self.action_queue[0]
            
            if next_act.get("action") == "restart_combat":
                self.current_depth = 0
                return self.action_queue.pop(0)

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
        player_status = p.get("status", [])
        enemies = battle_info.get("enemies", [])
        
        if self.current_depth == 0 and self.start_hp == -1:
            self.start_hp = int(p.get("hp", 999))

        results = generate_all_actions(current_energy, hand, enemies, player_status)
        if not results:
            self.current_depth += 1
            return {"action": "end_turn"}

        is_lethal = results[0].get("_is_lethal", False)

        if self.is_searching:
            if self.current_depth < len(self.target_path):
                choice_idx = self.target_path[self.current_depth]
                choice_idx = min(choice_idx, len(results) - 1) 
            else:
                if is_lethal:
                    current_loss = (self.start_hp - int(p.get("hp", 0))) + results[0].get("loss", 0)
                    print(f"💀 [킬각 도달] 탐색 경로: {self.target_path + [0]} | 누적 피해: {current_loss}")

                    if current_loss < self.best_loss:
                        self.best_loss = current_loss
                        self.best_path = self.target_path + [0]
                        print(f"🌟 [최적 경로 갱신] 현재까지 최소 피해량: {self.best_loss}")

                        if self.best_loss <= 0:
                            print(f"✨ [퍼펙트 클리어] 피해량 0 달성! 불필요한 평행세계 탐색을 즉시 종료합니다.")
                            self.to_explore.clear()

                    if self.to_explore:
                        self.target_path = self.to_explore.pop()
                        self.action_queue = [{"action": "restart_combat"}]
                        return self.get_action(raw_state)
                    else:
                        print("\n" + "="*60)
                        print(f"✅ [모든 평행세계 탐색 완료] 완벽한 승리 공식을 찾았습니다.")
                        print(f"🥇 최적 타임라인: {self.best_path} | 🩸 예상 최종 피해: {self.best_loss}")
                        print("="*60 + "\n")
                        self.is_searching = False
                        self.target_path = self.best_path
                        self.action_queue = [{"action": "restart_combat"}]
                        return self.get_action(raw_state)
                else:
                    hp_drop = self.start_hp - int(p.get("hp", 0))
                    valid_choices = []
                    
                    for i in range(len(results)):
                        predicted_loss = hp_drop + results[i].get("loss", 0)
                        if predicted_loss < self.best_loss:
                            valid_choices.append(i)
                    
                    if not valid_choices:
                        current_predict = hp_drop + results[0].get("loss", 0)
                        print(f"✂️ [가지치기] 예상 누적 피해({current_predict})가 최소 기록({self.best_loss}) 이상이므로 이 타임라인을 폐기합니다.")
                        
                        if self.to_explore:
                            self.target_path = self.to_explore.pop()
                            self.action_queue = [{"action": "restart_combat"}]
                            return self.get_action(raw_state)
                        else:
                            print("\n" + "="*60)
                            print(f"✅ [모든 평행세계 탐색 완료] 완벽한 승리 공식을 찾았습니다.")
                            print(f"🥇 최적 타임라인: {self.best_path} | 🩸 예상 최종 피해: {self.best_loss}")
                            print("="*60 + "\n")
                            self.is_searching = False
                            self.target_path = self.best_path
                            self.action_queue = [{"action": "restart_combat"}]
                            return self.get_action(raw_state)

                    for i in reversed(valid_choices[1:]):
                        self.to_explore.append(self.target_path + [i])
                    
                    choice_idx = valid_choices[0]
                    self.target_path.append(choice_idx)
                    print(f"🔍 [DFS 멀티버스 탐색] {self.current_depth + 1}턴 | 분기 {choice_idx}번 진입 (남은 평행세계: {len(self.to_explore)}개)")
        else:
            if self.current_depth < len(self.best_path):
                choice_idx = self.best_path[self.current_depth]
                choice_idx = min(choice_idx, len(results) - 1)
            else:
                choice_idx = 0
            
            if is_lethal:
                print("💀 [최종 처형] 최적화된 타임라인으로 적을 마무리합니다!")
                self.combat_finished = True

        res = results[choice_idx]
        combo = res["combo"]
        self.current_depth += 1
        
        idx_to_name = {c.get("index", i): c.get("name", "Unknown") for i, c in enumerate(hand)}
        idx_to_card = {c.get("index", i): c for i, c in enumerate(hand)}

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
        
        prefix = "⚔️ [실행 중]" if not self.is_searching else "🤔 [탐색 시뮬레이션]"
        print(f"{prefix} 콤보: {' -> '.join(combo_names)}")
        self.action_queue = actions

        return self.get_action(raw_state)