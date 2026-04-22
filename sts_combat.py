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
        # 1. 절대 슬롯 추적기 (유령 방지)
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
        # 2. 큐 관리 (실행 및 시간 역행 시 추적기 초기화)
        # ====================================================================
        if self.action_queue:
            next_act = self.action_queue[0]
            
            if next_act.get("action") == "restart_combat":
                self.current_turn_idx = 0 
                # 🚨 [버그 픽스] 시간 역행 시 몬스터 추적기도 무조건 초기화! (유령 몬스터 4번 5번 증식 방지)
                self.monster_slots = [] 
                self.current_slots = []
                self.action_queue.clear()
                return next_act

            if next_act.get("action") == "play_card":
                if "target" in next_act:
                    try:
                        tgt_idx = int(next_act["target"]) - 1
                        if tgt_idx >= len(self.monster_slots) or self.monster_slots[tgt_idx].get("hp", 0) <= 0:
                            print(f"👻 [스마트 취소] 타겟 사망. 헛손질 방지.")
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

        # 🚨 [요청 반영] 현재 AI가 인식하고 있는 몬스터 슬롯 매핑 상황 관측 출력
        print("\n👀 [절대 슬롯 관측기] 게임 내부 타겟팅 맵핑 상태:")
        for rel_idx, abs_slot in enumerate(self.current_slots):
            print(f"   ▶ 화면의 {rel_idx}번 적 ({enemies[rel_idx].get('name')}) -> 🎯 시스템 실제 타겟: {abs_slot + 1}번")
        print("-" * 60)

        # ====================================================================
        # 3. Macro DFS & 자살 방지 / 칼같은 가지치기
        # ====================================================================
        current_energy = int(p.get("energy", 3))
        hand = p.get("hand", [])
        player_status = p.get("status", [])
        current_hp_loss = self.start_hp - int(p.get("hp", 0))
        
        results = generate_all_actions(current_energy, hand, enemies, player_status)
        alive_enemies = sum(1 for e in enemies if e.get("hp", 0) > 0)
        
        if not results:
            if self.is_searching:
                return self._trigger_backtrack(raw_state)
            else:
                self.action_queue = [{"action": "end_turn"}]
                self.current_turn_idx += 1
                return self.get_action(raw_state)

        if self.is_searching:
            if self.current_turn_idx < len(self.target_path):
                choice_idx = self.target_path[self.current_turn_idx]
                if choice_idx >= len(results):
                    return self._trigger_backtrack(raw_state)
                
                predicted_loss = current_hp_loss + results[choice_idx]["loss"]
                # 🚨 [자살/오버로스 방지] 기록 갱신 실패거나 플레이어가 죽는다면 턴종료 안하고 즉시 역행!
                if predicted_loss >= self.best_loss or predicted_loss >= self.start_hp:
                    print(f"✂️ [과거 가지치기] 이 경로(누적피해:{predicted_loss})는 기록 갱신 실패 혹은 사망각입니다. 역행합니다.")
                    return self._trigger_backtrack(raw_state)
            
            else:
                is_lethal = results[0].get("kills", 0) >= alive_enemies
                
                if is_lethal:
                    lethal_loss = current_hp_loss + results[0].get("loss", 0)
                    if lethal_loss < self.best_loss:
                        self.best_loss = lethal_loss
                        self.best_path = self.target_path + [0]
                        print(f"🌟 [최적 경로 갱신] 킬각 발견! 최소 피해량: {self.best_loss}")
                        if self.best_loss <= 0:
                            print("✨ [퍼펙트 클리어] 피해 0 달성! 평행세계 탐색을 조기 종료합니다.")
                            self.to_explore.clear()
                    return self._trigger_backtrack(raw_state)
                
                valid_choices = []
                for i in range(len(results)):
                    predicted_loss = current_hp_loss + results[i].get("loss", 0)
                    # 🚨 [생존 필터링] 최고 기록보다 좋고 & 죽지 않는 길만 개척함!
                    if predicted_loss < self.best_loss and predicted_loss < self.start_hp:
                        valid_choices.append(i)

                if not valid_choices:
                    print(f"✂️ [미래 가지치기] 남은 선택지의 미래가 모두 죽음이거나 기록 갱신 실패입니다. 폐기합니다.")
                    return self._trigger_backtrack(raw_state)

                for i in reversed(valid_choices[1:]):
                    self.to_explore.append(self.target_path + [i])
                
                choice_idx = valid_choices[0]
                self.target_path.append(choice_idx)
                print(f"🔍 [DFS 진행] {self.current_turn_idx + 1}턴 | 분기 {choice_idx}번 진입 (남은 분기: {len(self.to_explore)}개)")

        else:
            if self.current_turn_idx < len(self.best_path):
                choice_idx = self.best_path[self.current_turn_idx]
                choice_idx = min(choice_idx, len(results) - 1)
            else:
                choice_idx = 0
            
            if results[choice_idx].get("kills", 0) >= alive_enemies:
                print("💀 [최종 처형] 최적화된 타임라인으로 적을 마무리합니다!")
                self.combat_finished = True

        # ====================================================================
        # 4. 콤보 장전
        # ====================================================================
        best_combo = results[choice_idx]["combo"]
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
            print(f"⏪ [시간 역행] 다른 타임라인({self.target_path}) 탐색을 위해 재시작합니다.")
        else:
            print(f"\n✅ [탐색 완료] 🥇 최종 경로: {self.best_path} | 피해: {self.best_loss}")
            self.is_searching = False
            if not self.best_path:
                self.best_path = [0]
            self.target_path = self.best_path
            self.action_queue = [{"action": "restart_combat"}]
        return self.get_action(raw_state)