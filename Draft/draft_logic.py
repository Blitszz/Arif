from typing import Dict, List, Any

ROLES = ["EXP Lane", "Jungler", "Mid Lane", "Gold Lane", "Roamer"]

def _norm(name: str) -> str: return name.strip().lower()

def calculate_draft(hero_data: Dict[str, Dict[str, Any]], ally_picks: List[str], enemy_picks: List[str], ally_bans: List[str], enemy_bans: List[str]):
    ally_n = [_norm(h) for h in ally_picks]
    enemy_n = [_norm(h) for h in enemy_picks]
    used = set(ally_n + enemy_n + [_norm(h) for h in ally_bans + enemy_bans])
    
    scored_heroes = []
    for hero, data in hero_data.items():
        if _norm(hero) in used: continue
        score = float(data.get("base_win_rate", 50.0))
        
        # Analisis Counter Musuh
        for en in enemy_picks:
            if _norm(en) in [_norm(c) for c in data.get("counters", [])]: score += 40.0
            if _norm(en) in [_norm(w) for w in data.get("countered_by", [])]: score -= 45.0
            
        # Analisis Sinergi Kawan
        for al in ally_picks:
            if _norm(al) in [_norm(s) for s in data.get("synergies", [])]: score += 20.0
            
        scored_heroes.append({"name": hero, "score": score, "roles": data.get("roles", []), "data": data})

    scored_heroes.sort(key=lambda x: x["score"], reverse=True)

    lineup = {}
    assigned = set()
    
    # Smart Role Mapping
    for role in ROLES:
        best = next((h["name"].upper() for h in scored_heroes 
                    if role in h["roles"] and _norm(h["name"]) not in assigned), "----")
        lineup[role] = best
        if best != "----": assigned.add(_norm(best))

    # Advisor & Focus
    adv = []
    for ep in enemy_picks:
        c = [h["name"].upper() for h in scored_heroes if _norm(ep) in [_norm(ct) for ct in h['data'].get('counters', [])] and _norm(h["name"]) not in assigned][:1]
        adv.append(f"{ep.upper()}: {c[0] if c else 'META'}")

    focus = {"name": "WAITING...", "reason": "-"}
    if enemy_picks:
        target = enemy_picks[-1]
        best_c = next((h for h in scored_heroes if _norm(target) in [_norm(ct) for ct in h['data'].get('counters', [])]), None)
        if best_c:
            focus = {"name": best_c["name"].upper(), "reason": f"Hero ini hard counter untuk {target.upper()}."}

    return {"focus": focus, "vectors": lineup, "enemy_advice": adv[:5], "probability": 50.0}