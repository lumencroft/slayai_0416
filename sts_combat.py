from sts_cards import CARD_DB
from action_generator import generate_all_actions 

class STSCombatAI:
    def __init__(self): 
        self.action_queue = []
        self.combat_finished = True
        self.reset_combat_state()

    def reset_combat_state(self):
        self.start_hp = -1
        self.best_loss = float('inf')
        self.monster_slots = []
        self.current_slots = []
        self.is_searching = True
        self.to_explore = []
        # 🚨 [최적화 핵심] 이제 인덱스나 문자열이 아니라, '콤보 객체 자체'를 리스트로 기억합니다!
        self.target_path = [] 
        self.best_path = []
        self.current_turn_idx = 0

    def get_action(self, raw_state):
        if self.combat_finished:
            self.reset_combat_state()
            self.combat_finished = False

        battle_info = raw_state.get("battle", {})
        if battle_info.get("turn") != "player" or not battle_info.get("is_play_phase", False):
            return {"action": "wait"}

        enemies = battle_info.get("enemies", [])
        p = raw_state.get("player", {})
        
        if self.start_hp == -1:
            self.start_hp = int(p.get("hp", 999))

        # ====================================================================
        # 1. 절대 슬롯 추적기 (유령 몬스터 방지)
        # ====================================================================
        if not self.monster_slots:
            self.monster_slots = list(enemies)
            self.current_slots = list(range(len(enemies)))
        else:
            new_current_slots = []
            search_start = 0
            for curr_e in enemies:
                matched_slot = -1
                for slot_idx in range(search_start, len(self.monster_slots)):
                    orig_e = self.monster_slots[slot_idx]
                    if orig_e.get("name") == curr_e.get("name") and orig_e.get("max_hp") == curr_e.get("max_hp"):
                        matched_slot = slot_idx
                        self.monster_slots[slot_idx] = curr_e
                        search_start = slot_idx + 1
                        break
                if matched_slot == -1:
                    matched_slot = len(self.monster_slots)
                    self.monster_slots.append(curr_e)
                    search_start = matched_slot + 1
                new_current_slots.append(matched_slot)
            self.current_slots = new_current_slots

        # ====================================================================
        # 2. 큐 관리
        # ====================================================================
        if self.action_queue:
            next_act = self.action_queue[0]
            if next_act.get("action") == "restart_combat":
                self.current_turn_idx = 0 
                self.monster_slots = [] 
                self.current_slots = []
                self.action_queue.clear()
                return next_act

            if next_act.get("action") == "play_card":
                if "target" in next_act:
                    try:
                        tgt_idx = int(next_act["target"]) - 1
                        if tgt_idx >= len(self.monster_slots) or self.monster_slots[tgt_idx].get("hp", 0) <= 0:
                            self.action_queue.clear()
                            return {"action": "wait"}
                    except Exception:
                        pass
                hand = raw_state.get("player", {}).get("hand", [])
                target_name = next_act.get("_card_name")
                found_idx = -1
                for i, c in enumerate(hand):
                    if c.get("name") == target_name and c.get("can_play", True):
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

        # ====================================================================
        # 3. Macro DFS & 고속 실행 (Fast Forward)
        # ====================================================================
        current_hp_loss = self.start_hp - int(p.get("hp", 0))
        alive_enemies = sum(1 for e in enemies if e.get("hp", 0) > 0)

        if self.is_searching:
            # 🚨 [최적화 1] 시간 역행 후, 과거의 발자취를 따라갈 때는 '채점기 연산'을 100% 생략합니다!
            if self.current_turn_idx < len(self.target_path):
                if current_hp_loss >= self.best_loss or current_hp_loss >= self.start_hp:
                    print(f"✂️ [과거 가지치기] 이 경로는 기록 갱신 실패 혹은 사망각입니다. 역행합니다.")
                    return self._trigger_backtrack(raw_state)
                # 채점기 없이 저장된 객체를 그대로 가져옴
                best_combo = self.target_path[self.current_turn_idx]
            
            # 미지의 영역(Frontier)에 도달했을 때만 새로 연산합니다.
            else:
                current_energy = int(p.get("energy", 3))
                hand = p.get("hand", [])
                player_status = p.get("status", [])
                
                results = generate_all_actions(current_energy, hand, enemies, player_status, current_hp_loss, self.best_loss)
                
                if not results:
                    return self._trigger_backtrack(raw_state)

                is_lethal = results[0].get("kills", 0) >= alive_enemies
                
                if is_lethal:
                    lethal_loss = current_hp_loss + results[0].get("loss", 0)
                    if lethal_loss < self.best_loss:
                        self.best_loss = lethal_loss
                        # 🚨 문자열이 아니라 실제 콤보 배열을 저장
                        self.best_path = list(self.target_path) + [results[0]["combo"]]
                        print(f"🌟 [최적 경로 갱신] 킬각 발견! 최소 피해량: {self.best_loss}")
                    
                    # 🚨 [즉결 처형] 0데미지거나 스택이 비어있다면 리스타트 생략하고 즉시 턴을 마칩니다!
                    if self.best_loss <= 0 or not self.to_explore:
                        print("✨ [퍼펙트 클리어 / 외길] 불필요한 리스타트를 생략하고 즉시 처형합니다!")
                        self.is_searching = False
                        self.to_explore.clear()
                        best_combo = results[0]["combo"]
                    else:
                        return self._trigger_backtrack(raw_state)
                else:
                    valid_choices = []
                    for i in range(len(results)):
                        predicted_loss = current_hp_loss + results[i].get("loss", 0)
                        if predicted_loss < self.best_loss and predicted_loss < self.start_hp:
                            valid_choices.append(i)

                    if not valid_choices:
                        return self._trigger_backtrack(raw_state)

                    # 🚨 [외길 진행] 다른 선택지가 없으면 스택에 넣을 필요 없이 바로 직진
                    if len(valid_choices) == 1 and not self.to_explore:
                        print("⚡ [외길 진행] 다른 평행세계가 없으므로 리스타트 없이 직진합니다.")
                        best_combo = results[valid_choices[0]]["combo"]
                        self.target_path.append(best_combo)
                    else:
                        for i in reversed(valid_choices[1:]):
                            self.to_explore.append(list(self.target_path) + [results[i]["combo"]])
                        
                        best_combo = results[valid_choices[0]]["combo"]
                        self.target_path.append(best_combo)
                        print(f"🔍 [DFS 진행] {self.current_turn_idx + 1}턴 | 분기 진입 (남은 스택: {len(self.to_explore)}개)")

        else:
            # 🚨 [최적화 2] 막타(실전) 모드에서는 채점기를 아예 끄고, 저장해둔 1등 콤보만 꺼내서 씁니다!
            if self.current_turn_idx < len(self.best_path):
                best_combo = self.best_path[self.current_turn_idx]
            else:
                best_combo = [{"action": "end_turn"}]
                
            if self.current_turn_idx == len(self.best_path) - 1:
                print("💀 [최종 처형] 최적화된 타임라인으로 적을 마무리합니다!")
                self.combat_finished = True

        # ====================================================================
        # 4. 콤보 장전 및 조준
        # ====================================================================
        self.current_turn_idx += 1 
        
        idx_to_name = {c.get("index", i): c.get("name", "Unknown") for i, c in enumerate(hand)}
        idx_to_card = {c.get("index", i): c for i, c in enumerate(hand)}

        actions = []
        combo_names = []
        for act in best_combo:
            if act["action"] == "play_card":
                card_idx = act["card_index"]
                card_name = idx_to_name.get(card_idx, "Unknown")
                card_data = CARD_DB.get(card_name, {})
                needs_target = idx_to_card.get(card_idx, {}).get("has_target", card_data.get("has_target", False))

                payload = {"action": "play_card", "_card_name": card_name}
                if needs_target and "target" in act:
                    relative_target = act["target"]
                    if relative_target < len(self.current_slots):
                        true_slot = self.current_slots[relative_target]
                        payload["target"] = str(true_slot + 1) 
                    else:
                        payload["target"] = str(relative_target + 1)
                    
                actions.append(payload)
                combo_names.append(card_name)
            else:
                actions.append({"action": "end_turn"})
                combo_names.append("턴 종료")
        
        prefix = "⚔️ [실전]" if not self.is_searching else "🤔 [탐색]"
        print(f"{prefix} 장전 콤보: {' -> '.join(combo_names)}\n")
        
        self.action_queue = actions
        return self.get_action(raw_state)

    def _trigger_backtrack(self, raw_state):
        if self.to_explore:
            self.target_path = self.to_explore.pop()
            self.action_queue = [{"action": "restart_combat"}]
            print(f"⏪ [시간 역행] 다른 평행세계 탐색을 위해 재시작합니다.")
        else:
            print(f"\n✅ [탐색 완료] 🥇 최종 피해: {self.best_loss}")
            self.is_searching = False
            
            # 살길이 없었다면 그냥 넘기기 위한 안전장치
            if not self.best_path:
                self.best_path = [[{"action": "end_turn"}]]
                
            self.target_path = self.best_path
            self.action_queue = [{"action": "restart_combat"}]
        return self.get_action(raw_state)