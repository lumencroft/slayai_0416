from sts_client import STSClient

def check_status():
    client = STSClient()
    state = client.get_state()
    
    if not state:
        print("❌ 게임 상태를 가져올 수 없습니다. 게임이 켜져 있는지 확인하세요.")
        return

    print("\n" + "="*60)
    print("🔍 [현재 상태 이상 및 전투 정보 확인]")
    print("="*60)

    # 1. 플레이어 상태 확인
    player = state.get("player", {})
    p_status = player.get("status", [])
    print(f"\n👤 [플레이어] {player.get('character', 'Unknown')} (HP: {player.get('hp')}/{player.get('max_hp')})")
    
    if p_status:
        for s in p_status:
            print(f"  🔻 ID: {s.get('id')}")
            print(f"     이름: {s.get('name')} (수치: {s.get('amount')})")
            print(f"     설명: {s.get('description')}")
    else:
        print("  ✅ 현재 부여된 상태 이상이 없습니다.")

    # 2. 적 상태 확인
    battle = state.get("battle", {})
    enemies = battle.get("enemies", [])
    print("\n👾 [적 정보]")
    
    if enemies:
        for i, e in enumerate(enemies):
            print(f"\n  [{i}번 적] {e.get('name')}")
            print(f"  - HP: {e.get('hp')}/{e.get('max_hp')}")
            print(f"  - Block(방어도): {e.get('block')}")
            
            e_status = e.get("status", [])
            if e_status:
                for s in e_status:
                    print(f"    🔻 ID: {s.get('id')}")
                    print(f"       이름: {s.get('name')} (수치: {s.get('amount')})")
                    print(f"       설명: {s.get('description')}")
            else:
                print("    ✅ 현재 부여된 상태 이상이 없습니다.")
    else:
        print("  - 현재 전투 중인 적이 없습니다.")
        
    print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    check_status()