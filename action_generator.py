import re
from sts_cards import CARD_DB

def generate_all_actions(energy, hand, enemies):
    combos = []
    enemy_count = len(enemies) if enemies else 1 
    
    enemy_data = {}
    for i in range(enemy_count):
        if enemies and i < len(enemies):
            e = enemies[i]
            hp = e.get("hp", 999)
            inc_dmg = 0
            
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
                        
            enemy_data[i] = {"hp": hp, "inc_dmg": inc_dmg}
        else:
            enemy_data[i] = {"hp": 999, "inc_dmg": 0}
    
    def dfs(e_left, cur_hand, seq):
        combos.append(seq + [{"action": "end_turn"}])
        seen = set()
        
        for i, c in enumerate(cur_hand):
            name = c.get("name")
            raw_c = c.get("cost", CARD_DB.get(name, {}).get("cost", 0))
            if f"{name}_{raw_c}" in seen: continue
            seen.add(f"{name}_{raw_c}")
            
            cost = int(raw_c) if str(raw_c).isdigit() else (e_left if str(raw_c).upper() == "X" else 999)
            if cost <= e_left:
                nxt_h = cur_hand[:i] + cur_hand[i+1:]
                
                has_target = CARD_DB.get(name, {}).get("has_target", False)
                targets = range(enemy_count) if has_target else [None]
                
                for t in targets:
                    act = {"action": "play_card", "card_index": c.get("index"), "card_name": name}
                    if t is not None:
                        act["target"] = t
                    dfs(e_left - cost, nxt_h, seq + [act])

    dfs(energy, hand, [])
    
    stats = {}
    for combo in combos:
        blk = 0
        dmg_dict = {}
        vuln_dict = {}
        temp_vuln = {}
        
        cur_hp = {k: v["hp"] for k, v in enemy_data.items()}

        for act in combo:
            if act["action"] == "play_card":
                db = CARD_DB.get(act["card_name"], {})
                t = act.get("target", -1) 
                
                blk += db.get("block", 0)
                
                if db.get("damage", 0) > 0 and t != -1:
                    multiplier = 1.5 if temp_vuln.get(t, 0) > 0 else 1.0
                    actual_dmg = int(db.get("damage", 0) * multiplier)
                    dmg_dict[t] = dmg_dict.get(t, 0) + actual_dmg
                    
                    if t in cur_hp:
                        cur_hp[t] -= actual_dmg
                    
                v = db.get("vulnerable", 0)
                if v > 0 and t != -1:
                    temp_vuln[t] = temp_vuln.get(t, 0) + v
                    vuln_dict[t] = vuln_dict.get(t, 0) + v
        
        surviving_inc_dmg = sum(enemy_data[i]["inc_dmg"] for i, hp in cur_hp.items() if hp > 0)
        
        hp_loss = max(0, surviving_inc_dmg - blk)
        
        kills = tuple(sorted(i for i, hp in cur_hp.items() if hp <= 0))
        
        c_str = ' ➔ '.join([
            c.get("card_name", "Unknown") + (f"(적{c['target']})" if c.get("target") is not None else "") 
            if c["action"] == "play_card" else "턴 종료" 
            for c in combo
        ])
        
        st = (blk, hp_loss, kills, tuple(sorted(dmg_dict.items())), tuple(sorted(vuln_dict.items())))
        if st not in stats:
            stats[st] = {"combo": combo, "str": c_str, "b": blk, "loss": hp_loss, "kills": kills, "d": dmg_dict, "v": vuln_dict}

    def is_dominated(current, other):
        if other["loss"] > current["loss"]: return False
        if other["b"] < current["b"]: return False
        
        if not set(current["kills"]).issubset(set(other["kills"])): return False
        
        all_d_keys = set(other["d"].keys()) | set(current["d"].keys())
        for k in all_d_keys:
            if other["d"].get(k, 0) < current["d"].get(k, 0): return False
            
        all_v_keys = set(other["v"].keys()) | set(current["v"].keys())
        for k in all_v_keys:
            if other["v"].get(k, 0) < current["v"].get(k, 0): return False
            
        if other["loss"] < current["loss"]: return True
        if other["b"] > current["b"]: return True
        if set(other["kills"]) > set(current["kills"]): return True
        for k in all_d_keys:
            if other["d"].get(k, 0) > current["d"].get(k, 0): return True
        for k in all_v_keys:
            if other["v"].get(k, 0) > current["v"].get(k, 0): return True
            
        return False

    res = [c for i, c in enumerate(stats.values()) if not any(i != j and is_dominated(c, o) for j, o in enumerate(stats.values()))]

    def format_dict(d):
        return ", ".join([f"적{k}:{v}" for k, v in d.items() if v > 0]) or "0"

    # for i, r in enumerate(res):
    #     kill_str = ", ".join([f"적{k}" for k in r['kills']]) if r['kills'] else "없음"
    #     print(f"[{i + 1:02d}] 💔피해:{r['loss']:02d} | 💀처치:{kill_str} | 🛡️방어:{r['b']:02d} | ⚔️딜({format_dict(r['d'])}) | 💢취약({format_dict(r['v'])})  ||  {r['str']}")
        
    return [r["combo"] for r in res]