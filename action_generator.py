import re
from sts_cards import CARD_DB
from sts_status import STATUS_DB

# ==========================================
# Step 1: 유효한 행동 시퀀스(평행세계) 추출기
# ==========================================
def generate_action_sequences(energy, hand, enemies, player_status=None):
    p_strength = 0
    if player_status:
        for s in player_status:
            if "STRENGTH" in str(s.get("id", "")).upper():
                p_strength += int(s.get("amount", 0))

    enemy_states = {}
    for i, e in enumerate(enemies):
        hp = e.get("hp", 999)
        if hp <= 0:
            continue
        vuln = 0
        for s in e.get("status", []):
            if "VULNERABLE" in str(s.get("id", "")).upper():
                vuln = int(s.get("amount", 0))
                break
        enemy_states[i] = {"hp": hp, "vuln": vuln, "name": e.get("name", "")}

    all_combos = []

    def dfs(e_left, cur_hand, cur_e_states, seq):
        all_combos.append(seq + [{"action": "end_turn"}])
        seen_card_names = set()
        
        for i, card in enumerate(cur_hand):
            if not card.get("can_play", True):
                continue
                
            name = card.get("name")
            if name in seen_card_names:
                continue
            seen_card_names.add(name)
            
            card_data = CARD_DB.get(name, {})
            cost_val = card.get("cost", card_data.get("cost", 0))
            cost = int(cost_val) if str(cost_val).isdigit() else (e_left if str(cost_val).upper() == "X" else 0)
            
            if cost > e_left:
                continue
            
            t_type = card.get("target_type", card_data.get("target_type", "None"))
            base_dmg = card.get("damage", card_data.get("damage", 0))
            base_vuln = card_data.get("vulnerable", 0)
            is_aoe = t_type in ["AllEnemies", "ALL_ENEMY"]
            
            alive_targets = [idx for idx, state in cur_e_states.items() if state["hp"] > 0]
            
            if t_type in ["Enemy", "AnyEnemy"]:
                if not alive_targets:
                    continue
                targets = alive_targets
            else:
                targets = [None]
            
            nxt_hand = cur_hand[:i] + cur_hand[i+1:]
            
            for t in targets:
                nxt_e_states = {k: {"hp": v["hp"], "vuln": v["vuln"], "name": v["name"]} for k, v in cur_e_states.items()}
                
                if base_dmg > 0 or base_vuln > 0:
                    hit_list = alive_targets if is_aoe else ([t] if t is not None else [])
                    calc_dmg = max(0, base_dmg + p_strength) if base_dmg > 0 else 0
                    
                    for tgt_idx in hit_list:
                        if calc_dmg > 0:
                            multiplier = 1.5 if nxt_e_states[tgt_idx]["vuln"] > 0 else 1.0
                            nxt_e_states[tgt_idx]["hp"] -= int(calc_dmg * multiplier)
                        if base_vuln > 0:
                            nxt_e_states[tgt_idx]["vuln"] += base_vuln
                
                act = {"action": "play_card", "card_index": card.get("index"), "card_name": name}
                if t is not None:
                    act["target"] = t
                    
                dfs(e_left - cost, nxt_hand, nxt_e_states, seq + [act])

    dfs(energy, hand, enemy_states, [])
    return all_combos


# ==========================================
# Step 2: 평행세계 결과 채점기 (Evaluator)
# ==========================================
def evaluate_action_sequences(combos, player_status, enemies):
    p_strength = 0
    p_dex = 0
    p_initial_debuffs = {}
    
    if player_status:
        for s in player_status:
            s_id = str(s.get("id", "")).upper()
            amt = int(s.get("amount", 0))
            if "STRENGTH" in s_id: p_strength += amt
            elif "DEXTERITY" in s_id: p_dex += amt
            else:
                for db_key, db_val in STATUS_DB.items():
                    if db_key in s_id: p_initial_debuffs[db_key] = db_val

    base_enemy_data = {}
    for i, e in enumerate(enemies):
        if e.get("hp", 999) <= 0:
            continue
        inc_dmg = 0
        init_vuln = 0
        
        for s in e.get("status", []):
            if "VULNERABLE" in str(s.get("id", "")).upper():
                init_vuln = int(s.get("amount", 0))
                break

        for intent in e.get("intents", []):
            if "Attack" in intent.get("type", ""):
                label = str(intent.get("label", "0")).lower()
                if "x" in label:
                    parts = label.split("x")
                    try: inc_dmg += int(parts[0]) * int(parts[1])
                    except: pass
                else:
                    nums = re.findall(r'\d+', label)
                    if nums: inc_dmg += int(nums[0])
                    
        base_enemy_data[i] = {"name": e.get("name", ""), "hp": e.get("hp", 999), "inc_dmg": inc_dmg, "init_vuln": init_vuln}

    stats = []

    for combo in combos:
        blk = 0
        total_dmg_dealt = 0
        
        cur_hp = {k: v["hp"] for k, v in base_enemy_data.items()}
        temp_vuln = {k: v["init_vuln"] for k, v in base_enemy_data.items()}
        active_debuffs = {k: v for k, v in p_initial_debuffs.items()}
        
        for act in combo:
            if act["action"] == "play_card":
                card_name = act.get("card_name")
                card_data = CARD_DB.get(card_name, {})
                base_blk = card_data.get("block", 0)
                base_dmg = card_data.get("damage", 0)
                v = card_data.get("vulnerable", 0)
                t = act.get("target", -1)
                is_aoe = card_data.get("target_type") in ["AllEnemies", "ALL_ENEMY"]
                
                if base_blk > 0:
                    calc_blk = max(0, base_blk + p_dex)
                    for db_val in active_debuffs.values():
                        if db_val.get("type") == "blk_mult": calc_blk = int(calc_blk * db_val["mult"])
                    blk += calc_blk

                if base_dmg > 0:
                    calc_dmg = max(0, base_dmg + p_strength)
                    for db_val in active_debuffs.values():
                        if db_val.get("type") == "dmg_mult": calc_dmg = int(calc_dmg * db_val["mult"])
                else:
                    calc_dmg = 0
                
                if calc_dmg > 0 or v > 0:
                    targets_to_hit = list(cur_hp.keys()) if is_aoe else ([t] if t in cur_hp else [])
                    for tgt in targets_to_hit:
                        if cur_hp[tgt] <= 0: continue
                        
                        if calc_dmg > 0:
                            multiplier = 1.5 if temp_vuln.get(tgt, 0) > 0 else 1.0
                            actual_dmg = int(calc_dmg * multiplier)
                            
                            # 🚨 [수정 1] 오버킬 방지: 적의 남은 체력까지만 딜량으로 인정
                            effective_dmg = min(cur_hp[tgt], actual_dmg)
                            total_dmg_dealt += effective_dmg
                            
                            cur_hp[tgt] -= actual_dmg
                            
                            if cur_hp[tgt] <= 0:
                                dead_name = base_enemy_data[tgt]["name"]
                                keys_to_remove = [k for k, val in active_debuffs.items() if val.get("tied_to") == dead_name]
                                for k in keys_to_remove: del active_debuffs[k]
                        
                        if v > 0:
                            temp_vuln[tgt] += v
        
        # ... (Step 2 기존 코드) ...
        surviving_inc_dmg = sum(base_enemy_data[i]["inc_dmg"] for i, hp in cur_hp.items() if hp > 0)
        hp_loss = max(0, surviving_inc_dmg - blk)
        kills = sum(1 for i, hp in cur_hp.items() if hp <= 0)
        useful_vuln = sum(v for i, v in temp_vuln.items() if cur_hp[i] > 0)
        
        # 🚨 [수정된 부분] 오버킬로 인해 마이너스가 된 체력은 0으로 통일하여 비교 오류를 방지합니다.
        final_hps = tuple(max(0, cur_hp.get(i, 0)) for i in range(len(base_enemy_data)))
        
        stats.append({
            "combo": combo, 
            "loss": hp_loss, 
            "kills": kills, 
            "dmg": total_dmg_dealt, 
            "blk": blk,
            "vuln": useful_vuln,
            "incoming": surviving_inc_dmg,
            "len": len(combo),
            "final_hps": final_hps
        })

    return stats
# ==========================================
# Step 3: 하위 호환 콤보 제거 (파레토 최적화)
# ==========================================
# 🚨 [핵심] 인덱스가 꼬이지 않도록, best_loss 필터링을 제거하고 파레토 최적화만 수행합니다.
def filter_optimal_actions(stats):
    unique_stats = {}
    for s in stats:
        sig = (s["loss"], s["kills"], s["dmg"], s["vuln"], s["final_hps"])
        if sig not in unique_stats or s["len"] < unique_stats[sig]["len"]:
            unique_stats[sig] = s
            
    filtered_stats = list(unique_stats.values())
    pareto_frontier = []

    for s in filtered_stats:
        dominated = False
        for other in filtered_stats:
            if s == other:
                continue
                
            hp_dominated = all(other_hp <= s_hp for other_hp, s_hp in zip(other["final_hps"], s["final_hps"]))
            if (other["loss"] <= s["loss"] and other["vuln"] >= s["vuln"] and hp_dominated):
                hp_strictly_better = any(other_hp < s_hp for other_hp, s_hp in zip(other["final_hps"], s["final_hps"]))
                if (other["loss"] < s["loss"] or other["vuln"] > s["vuln"] or hp_strictly_better or other["len"] < s["len"]): 
                    dominated = True
                    break
        if not dominated:
            pareto_frontier.append(s)

    pareto_frontier.sort(key=lambda x: (x["loss"], -x["kills"], -x["dmg"], -x["vuln"], x["len"]))
    return pareto_frontier


# ==========================================
# Main: 전체 과정 실행 및 결과 출력
# ==========================================
def generate_all_actions(energy, hand, enemies, player_status=None):
    raw_combos = generate_action_sequences(energy, hand, enemies, player_status)
    evaluated_stats = evaluate_action_sequences(raw_combos, player_status, enemies)
    optimal_stats = filter_optimal_actions(evaluated_stats)
    
    print("\n" + "="*80)
    print(f"📊 [AI 턴 최종 시뮬레이션 성적표] (총 {len(evaluated_stats)}개 중 정예 {len(optimal_stats)}개 생존)")
    print("="*80)
    
    for i, s in enumerate(optimal_stats):
        combo_str = " -> ".join([
            f"{act.get('card_name')}(타겟:{act.get('target', '없음')})" if act.get('action') == 'play_card' else "턴 종료" 
            for act in s['combo']
        ])
        rank_mark = "🏆 [최우수]" if i == 0 else f"[{i+1}번 후보]"
        print(f"{rank_mark} 🩸예상피해: {s['loss']:2d} | 💀킬: {s['kills']} | ⚔️딜: {s['dmg']:2d} | 🛡️방어: {s['blk']:2d} | 🎯취약: {s['vuln']}")
        print(f"   ▶ 경로: {combo_str}")
        print("-" * 80)
        
    return optimal_stats