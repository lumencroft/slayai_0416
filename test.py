from sts_client import STSClient
from action_generator import generate_all_actions  # 앞서 만든 함수가 있는 파일명

def test_live_combos():
    print("🔌 Slay the Spire 라이브 게임에 연결을 시도합니다...")
    
    # 1. 라이브 게임 클라이언트 연결
    client = STSClient()
    raw_state = client.get_state()
    
    # 2. 예외 처리: 게임이 꺼져있거나 통신 모드가 안 켜진 경우
    if not raw_state:
        print("❌ [오류] 게임 상태를 가져올 수 없습니다. 게임과 Communication Mod가 실행 중인지 확인하세요.")
        return

    # 3. 예외 처리: 현재 전투 중이 아닌 경우
    state_type = raw_state.get("state_type", "")
    if state_type not in ["monster", "elite", "boss"]:
        print(f"⚠️ [대기] 현재 전투 중이 아닙니다. (현재 화면: {state_type})")
        print("몬스터와 전투 중인 상태에서 다시 실행해 주세요.")
        return

    # 4. 예외 처리: 내 턴이 아니거나 애니메이션 진행 중인 경우
    battle_info = raw_state.get("battle", {})
    if battle_info.get("turn") != "player" or not battle_info.get("is_play_phase", False):
        print("⚠️ [대기] 지금은 카드를 낼 수 있는 타이밍이 아닙니다. (적의 턴이거나 애니메이션 재생 중)")
        return

    print("\n✅ [연결 성공] 현재 전황 데이터를 성공적으로 불러왔습니다!\n")

    # 5. 게임에서 실시간 데이터 추출
    player = raw_state.get("player", {})
    energy = player.get("energy", 0)
    hand = player.get("hand", [])
    player_status = player.get("status", [])
    enemies = battle_info.get("enemies", [])

    # (선택 사항) 현재 상태 요약 출력
    print("="*60)
    print("🔍 [라이브 데이터 요약]")
    print(f"⚡ 에너지: {energy} / 🃏 손패: {[c.get('name') for c in hand]}")
    if enemies:
        print(f"👾 살아있는 적:")
        for e in enemies:
            if e.get("hp", 0) > 0:
                print(f"   - {e.get('name')} (HP: {e.get('hp')}/{e.get('max_hp')})")
    print("="*60)

    # 6. 실시간 데이터를 AI 엔진(콤보 생성기)에 주입하여 실행
    print("\n🧠 AI 콤보 탐색 및 채점을 시작합니다...\n")
    generate_all_actions(energy, hand, enemies, player_status)

if __name__ == "__main__":
    test_live_combos()