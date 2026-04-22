import time

class StateObserver:
    def __init__(self):
        pass

    def is_state_stable(self, state):
        """액션을 수행하기 전, 게임이 조작 가능한 안정 상태인지 확인합니다."""
        if not state:
            return False
        state_type = state.get("state_type", "")
        if state_type in ["monster", "elite", "boss"]:
            battle = state.get("battle", {})
            return battle.get("turn") == "player" and battle.get("is_play_phase", False)
        return True

    def compare_and_print_diff(self, before, after, elapsed_ms, ticks):
        """이전 상태와 현재 상태를 비교하고 걸린 시간을 콘솔에 전문적으로 출력합니다."""
        # print("\n" + "="*60)
        # print(f"📊 [상태 변화 디버그 리포트] ⏱️ {elapsed_ms:.2f}ms 소요 (API {ticks}회 호출)")
        # print("-" * 60)
        
        # 1. 플레이어 상태 변화 체크 (HP, 에너지, 방어도)
        b_p = before.get("player", {})
        a_p = after.get("player", {})
        
        # if b_p.get("energy") != a_p.get("energy"):
        #     print(f"⚡ 에너지: {b_p.get('energy')} -> {a_p.get('energy')}")
        # if b_p.get("hp") != a_p.get("hp"):
        #     print(f"❤️ 플레이어 HP: {b_p.get('hp')} -> {a_p.get('hp')}")
        # if b_p.get("block") != a_p.get("block"):
        #     print(f"🛡️ 플레이어 방어도: {b_p.get('block')} -> {a_p.get('block')}")

        # 2. 패(Hand) 변화 체크 및 인덱스 확인
        # b_hand = b_p.get("hand", [])
        # a_hand = a_p.get("hand", [])
        # if len(b_hand) != len(a_hand) or b_hand != a_hand:
        #     b_names = [c.get("name") for c in b_hand]
        #     a_names = [c.get("name") for c in a_hand]
            # print(f"🃏 패 변화: {len(b_hand)}장 -> {len(a_hand)}장")
            # print(f"   [이전]: {b_names}")
            # print(f"   [현재]: {a_names}")

        # 3. 적(Enemies) 상태 변화 완벽 추적 (HP, 죽음, 인덱스 밀림, 의도 사라짐)
        b_enemies = before.get("battle", {}).get("enemies", [])
        a_enemies = after.get("battle", {}).get("enemies", [])
        
        # print(f"👾 적 상태 디테일 (이전 {len(b_enemies)}마리 -> 현재 {len(a_enemies)}마리):")
        
        # 죽거나 밀린 몬스터를 추적하기 위한 로직
        a_matched = [] # 이미 매칭된 현재 적의 인덱스
        
        for b_idx, b_e in enumerate(b_enemies):
            name = b_e.get("name")
            b_hp = b_e.get("hp")
            
            # 현재 상태에서 이 몬스터가 어디로 갔는지 찾습니다.
            found_a_idx = -1
            for a_idx, a_e in enumerate(a_enemies):
                if a_idx not in a_matched and a_e.get("name") == name and a_e.get("max_hp") == b_e.get("max_hp"):
                    found_a_idx = a_idx
                    a_matched.append(a_idx)
                    break
            
            # if found_a_idx != -1:
                # 몬스터가 살아있음! 변화점 체크
                # a_e = a_enemies[found_a_idx]
                # if b_hp != a_e.get("hp"):
                    # print(f"   🩸 HP 변화 [{name}]: {b_hp} -> {a_e.get('hp')}")
                # if b_e.get("block", 0) != a_e.get("block", 0):
                    # print(f"   🛡️ 방어도 변화 [{name}]: {b_e.get('block', 0)} -> {a_e.get('block', 0)}")
                # if b_idx != found_a_idx:
                    # print(f"   ↔️ 인덱스 당겨짐 [{name}]: 기존 {b_idx}번 타겟 -> 현재 {found_a_idx}번 타겟으로 이동!")
            # else:
                # 현재 배열에 없음 = 사망하여 소멸함
                # print(f"   💀 사망 및 배열 소멸: {name} (이전 HP: {b_hp}, 기존 {b_idx}번 타겟)")
                # print(f"   ❌ 의도(Intent) 영구 제거됨: {name}")
                # pass
        print("=" * 60 + "\n")


    def wait_for_action_result(self, client, act_type, before_state, max_ticks=150):
        """액션 전송 후, 타임아웃 전까지 지속적으로 폴링하며 모든 애니메이션과 논리 연산이 끝날 때까지 대기합니다."""
        timeout_ticks = 0
        start_time = time.perf_counter() 
        
        b_p = before_state.get("player", {})
        initial_energy = b_p.get("energy")
        initial_hand = b_p.get("hand", [])
        
        # 상태 안정화를 체크하기 위한 디바운스(Debounce) 변수
        stable_count = 0
        last_state_str = ""

        while True:
            after_state = client.get_state()
            if not after_state:
                time.sleep(0.01) # 무의미한 API 폭격 방지
                continue

            timeout_ticks += 1
            a_p = after_state.get("player", {})
            a_battle = after_state.get("battle", {})
            
            # 1. 1차 관문: 내 명령이 게임에 "접수"라도 되었는가?
            # (에너지가 깎였거나 패가 줄어들었으면 게임이 동작을 시작한 것)
            has_started = False
            if act_type == "play_card":
                if initial_energy != a_p.get("energy") or initial_hand != a_p.get("hand"):
                    has_started = True
            else:
                has_started = True # end_turn 등은 즉시 통과

            if act_type == "play_card" and not has_started:
                if timeout_ticks > max_ticks:
                    break
                time.sleep(0.01)
                continue

            # 2. 2차 관문: 모든 먼지가 가라앉았는가? (애니메이션, 데미지, 배열 이동 등)
            # 게임이 조작 가능한 상태(is_play_phase = True)인지 확인
            is_playable = a_battle.get("is_play_phase", False)
            
            # 현재 핵심 데이터들의 직렬화 문자열 (이게 변하지 않아야 함)
            current_state_str = str(a_p.get("hp")) + str(a_p.get("energy")) + str(a_p.get("hand")) + str(a_battle.get("enemies"))

            if is_playable:
                if current_state_str == last_state_str:
                    stable_count += 1
                else:
                    stable_count = 0
                    last_state_str = current_state_str

                # 핵심: "조작 가능 상태"에서 "3틱(약 30ms) 연속으로 아무런 데이터 변화가 없을 때" 비로소 안정화되었다고 판정!
                if stable_count >= 3:
                    end_time = time.perf_counter()
                    elapsed_ms = (end_time - start_time) * 1000
                    print(f"✅ [성공] '{act_type}' 실행 및 게임 상태 완벽 동기화 완료")
                    self.compare_and_print_diff(before_state, after_state, elapsed_ms, timeout_ticks)
                    return True
            else:
                # 애니메이션이 진행 중이라 조작 불가 상태라면 안정화 카운트 리셋
                stable_count = 0
                last_state_str = ""

            if timeout_ticks > max_ticks:
                break
                
            time.sleep(0.01) # API 부하를 줄이기 위해 10ms 대기

        # 타임아웃 발생 시
        end_time = time.perf_counter()
        elapsed_ms = (end_time - start_time) * 1000
        print(f"⚠️ [경고] {max_ticks}틱 대기 초과 (⏱️ {elapsed_ms:.2f}ms 경과). 액션이 무시되었거나 애니메이션이 비정상적으로 깁니다.")
        return False