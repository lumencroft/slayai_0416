from sts_client import STSClient
from sts_combat import STSCombatAI
from sts_choose import STSChooseAI
from state_observer import StateObserver  # 새로 추가된 옵저버 임포트

def main():
    client = STSClient()
    combat_ai = STSCombatAI()
    choose_ai = STSChooseAI()
    observer = StateObserver()  # 옵저버 초기화

    while True:
        raw_state = client.get_state()
        
        # 1. 조작 가능한 안정화된 상태인지 확인 (애니메이션 진행 중이 아닌지)
        if not observer.is_state_stable(raw_state):
            continue
            
        state_type = raw_state.get("state_type", "")
        
        if state_type in ["monster", "elite", "boss"]:
            action_payload = combat_ai.get_action(raw_state)
            if action_payload and action_payload.get("action") != "wait":
                print(f"▶️ [명령 생성] {action_payload}")
        elif state_type in ["map", "event", "rest", "shop", "reward", "chest", "choice"]:
            action_payload = choose_ai.get_action(raw_state)
        else:
            action_payload = {"action": "proceed"}

        if not action_payload or action_payload.get("action") == "wait":
            continue

        # 2. 액션 전송
        client.send_action(action_payload)
        
        # 3. 전송한 액션이 게임에 완전히 반영되었는지 추적
        act_type = action_payload.get("action")
        success = observer.wait_for_action_result(client, act_type, raw_state, max_ticks=15)
        
        # 타임아웃 발생 시 무한 루프에 빠지는 것을 방지하기 위해 큐를 초기화
        if not success:
            combat_ai.action_queue.clear()

if __name__ == "__main__":
    main()