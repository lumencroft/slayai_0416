import time
from sts_client import STSClient

def probe_target():
    client = STSClient()
    
    # 1. 현재 상태를 가져와서 테스트 기준점을 잡습니다.
    initial_state = client.get_state()
    if not initial_state:
        print("❌ 게임 상태를 가져올 수 없습니다. 게임이 켜져 있는지 확인하세요.")
        return

    player_info = initial_state.get("player", {})
    initial_energy = player_info.get("energy", 3)
    initial_hand_count = len(player_info.get("hand", []))
    
    enemies = initial_state.get("battle", {}).get("enemies", [])
    if not enemies:
        print("❌ 적이 없습니다. 전투 중에 실행해주세요.")
        return
        
    first_enemy = enemies[0]
    combat_id = first_enemy.get("combat_id", 1)
    entity_id = first_enemy.get("entity_id", "")

    # 2. 테스트할 페이로드 목록 (모든 타겟팅 가능성 염두)
    tests = [
        ("TEST 1 (target을 문자열 '0'으로)", {"action": "play_card", "card_index": 0, "target": "0"}),
        ("TEST 2 (target을 문자열 '1'로)", {"action": "play_card", "card_index": 0, "target": "1"}),
        ("TEST 3 (combat_id 정수 사용)", {"action": "play_card", "card_index": 0, "target": combat_id}),
        ("TEST 4 (entity_id 문자열 사용)", {"action": "play_card", "card_index": 0, "target": entity_id}),
        ("TEST 5 (target_id 키 사용)", {"action": "play_card", "card_index": 0, "target_id": 0}),
        ("TEST 6 (target_index 키 사용)", {"action": "play_card", "card_index": 0, "target_index": 0}),
        ("TEST 7 (target을 통째로 생략)", {"action": "play_card", "card_index": 0}),
    ]
    
    print(f"🔍 API 타겟팅 규격 정밀 테스트 시작...")
    print(f"기존 에너지: {initial_energy}, 기존 손패 수: {initial_hand_count}\n")
    
    for name, payload in tests:
        print(f"🚀 [{name}] 전송 중: {payload}")
        
        # 액션 전송
        client.send_action(payload)
        
        # 1.5초 동안 0.2초 간격으로 상태 변화를 감지합니다.
        success = False
        for _ in range(7):
            time.sleep(0.2)
            check_state = client.get_state()
            if not check_state:
                continue
                
            current_energy = check_state.get("player", {}).get("energy", initial_energy)
            current_hand_count = len(check_state.get("player", {}).get("hand", []))
            
            # 에너지가 줄었거나 손패가 줄었다면 카드가 '실제로' 사용된 것!
            if current_energy < initial_energy or current_hand_count < initial_hand_count:
                success = True
                break
                
        if success:
            print(f"\n✅ 성공! 카드가 실제로 사용되었습니다.")
            print(f"👉 정답 페이로드: {payload}")
            return
        else:
            print(f"❌ 실패 (상태 변화 없음 또는 500 에러)\n")

if __name__ == "__main__":
    probe_target()