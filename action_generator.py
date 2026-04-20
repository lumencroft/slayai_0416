import re
from sts_cards import CARD_DB
from sts_status import STATUS_DB


def generate_all_actions(energy, hand, enemies, player_status=None):
    combos = []
    enemy_count = len(enemies) if enemies else 1 
    
    enemy_data = {}
    alive_targets = []
    
    for i in range(enemy_count):
        if enemies and i < len(enemies):
            e = enemies[i]
            hp = e.get("hp", 999)
            if hp <= 0:
                enemy_data[i] = {"hp": 0, "inc_dmg": 0, "init_vuln": 0, "name": e.get("name", "")}
                continue
                
            alive_targets.append(i)
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
                        
            enemy_data[i] = {"hp": hp, "inc_dmg": inc_dmg, "init_vuln": init_vuln, "name": e.get("name", "")}
        else:
            enemy_data[i] = {"hp": 999, "inc_dmg": 0, "init_vuln": 0, "name": "Unknown"}

    alive_enemies = len(alive_targets)
    
    p_strength = 0
    p_dex = 0
    p_initial_debuffs = {}
    
    if player_status:
        for s in player_status:
            s_id = str(s.get("id", "")).upper()
            amt = int(s.get("amount", 0))
            
            if "STRENGTH" in s_id: 
                p_strength += amt
            elif "DEXTERITY" in s_id: 
                p_dex += amt
            else:
                for db_key, db_val in STATUS_DB.items():
                    if db_key in s_id:
                        p_initial_debuffs[db_key] = db_val

    def dfs(e_left, cur_hand, seq):
        combos.append(seq + [{"action": "end_turn"}])
        
        seen = set()
        for i, c in enumerate(cur_hand):
            if not c.get("can_play", True):
                continue
                
            name = c.get("name")
            raw_c = c.get("cost", CARD_DB.get(name, {}).get("cost", 0))
            cost = int(raw_c) if str(raw_c).isdigit() else (e_left if str(raw_c).upper() == "X" else 0)
            
            if cost > e_left:
                continue

            card_sig = f"{name}_{cost}"
            if card_sig in seen: 
                continue
            seen.add(card_sig)
            
            nxt_h = cur_hand[:i] + cur_hand[i+1:]
            
            t_type = c.get("target_type", CARD_DB.get(name, {}).get("target_type", "None"))
            if t_type in ["Enemy", "AnyEnemy"]:
                targets = alive_targets
            else:
                targets = [None]
            
            card_damage = c.get("damage", CARD_DB.get(name, {}).get("damage", 0))
            card_block = c.get("block", CARD_DB.get(name, {}).get("block", 0))
            card_vuln = CARD_DB.get(name, {}).get("vulnerable", 0)
            is_aoe = t_type in ["AllEnemies", "ALL_ENEMY"]
            
            for t in targets:
                act = {
                    "action": "play_card", 
                    "card_index": c.get("index"), 
                    "card_name": name, 
                    "dmg": card_damage, 
                    "blk": card_block, 
                    "vuln": card_vuln,
                    "is_aoe": is_aoe
                }
                if t is not None: 
                    act["target"] = t
                    
                dfs(e_left - cost, nxt_h, seq + [act])

    dfs(energy, hand, [])
    
    stats = []
    for combo in combos:
        blk = 0
        cur_hp = {k: v["hp"] for k, v in enemy_data.items() if v["hp"] > 0}
        temp_vuln = {k: v["init_vuln"] for k, v in enemy_data.items() if v["hp"] > 0}
        total_dmg_dealt = 0
        total_vuln_applied = 0
        
        active_debuffs = {k: v for k, v in p_initial_debuffs.items()}
        
        for act in combo:
            if act["action"] == "play_card":
                base_blk = act.get("blk", 0)
                base_dmg = act.get("dmg", 0)
                v = act.get("vuln", 0)
                t = act.get("target", -1)
                is_aoe = act.get("is_aoe", False)
                
                if base_blk > 0:
                    calc_blk = max(0, base_blk + p_dex)
                    for db_val in active_debuffs.values():
                        if db_val.get("type") == "blk_mult":
                            calc_blk = int(calc_blk * db_val["mult"])
                    blk += calc_blk

                if base_dmg > 0:
                    calc_dmg = max(0, base_dmg + p_strength)
                    for db_val in active_debuffs.values():
                        if db_val.get("type") == "dmg_mult":
                            calc_dmg = int(calc_dmg * db_val["mult"])
                else:
                    calc_dmg = 0
                
                if calc_dmg > 0 or v > 0:
                    targets_to_hit = list(cur_hp.keys()) if is_aoe else ([t] if t in cur_hp else [])
                    
                    for tgt in targets_to_hit:
                        if calc_dmg > 0:
                            multiplier = 1.5 if temp_vuln.get(tgt, 0) > 0 else 1.0
                            actual_dmg = int(calc_dmg * multiplier)
                            cur_hp[tgt] -= actual_dmg
                            total_dmg_dealt += actual_dmg
                            
                            if cur_hp[tgt] <= 0:
                                dead_name = enemy_data[tgt]["name"]
                                keys_to_remove = [k for k, val in active_debuffs.items() if val.get("tied_to") == dead_name]
                                for k in keys_to_remove:
                                    del active_debuffs[k]
                        
                        if v > 0:
                            temp_vuln[tgt] += v
                            total_vuln_applied += v
        
        surviving_inc_dmg = sum(enemy_data[i]["inc_dmg"] for i, hp in cur_hp.items() if hp > 0)
        hp_loss = max(0, surviving_inc_dmg - blk)
        kills = sum(1 for i, hp in cur_hp.items() if hp <= 0)
        
        stats.append({
            "combo": combo, 
            "loss": hp_loss, 
            "kills": kills, 
            "dmg": total_dmg_dealt, 
            "blk": blk,
            "vuln": total_vuln_applied,
            "incoming": surviving_inc_dmg,
            "len": len(combo)
        })

    unique_stats = []
    seen_sigs = set()
    for s in stats:
        cards_played = tuple(sorted([f"{act.get('card_name')}_{act.get('target', -1)}" for act in s["combo"] if act.get("action") == "play_card"]))
        sig = (s["loss"], s["kills"], s["dmg"], s["blk"], s["vuln"], cards_played)
        
        if sig not in seen_sigs:
            seen_sigs.add(sig)
            unique_stats.append(s)

    stats = unique_stats

    if alive_enemies > 0:
        lethal_combos = [c for c in stats if c["kills"] >= alive_enemies]
        if lethal_combos:
            lethal_combos.sort(key=lambda x: (x["len"], -x["blk"]))
            best_lethal = lethal_combos[0]
            best_lethal["_is_lethal"] = True
            return [best_lethal]
    
    stats.sort(key=lambda x: (
        x["loss"],
        -x["kills"],
        -x["vuln"],
        -x["dmg"],
        -x["blk"],
        x["len"]
    ))
    
    pareto_frontier = []
    for s in stats:
        dominated = False
        for f in pareto_frontier:
            if (f["loss"] <= s["loss"] and 
                f["kills"] >= s["kills"] and 
                f["vuln"] >= s["vuln"] and
                f["dmg"] >= s["dmg"]):
                dominated = True
                break
        if not dominated:
            pareto_frontier.append(s)
    
    return pareto_frontier