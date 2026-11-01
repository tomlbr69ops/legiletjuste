#!/usr/bin/env python3
"""Régénère la liste des gilets d'index.html à partir de products.json.

Usage :  python build.py
         python build.py --date "2 novembre 2026"   (force la date affichée)
"""
import json, re, sys, datetime, pathlib

ROOT = pathlib.Path(__file__).parent
TYPES = {"fixe", "versions", "amovible"}
USES = {"marche", "course", "renfo"}
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
        "août", "septembre", "octobre", "novembre", "décembre"]


def check(data):
    errs, seen = [], set()
    for i, p in enumerate(data["products"], 1):
        n = f"Produit {i} ({p.get('name', '?')})"
        if not re.fullmatch(r"[A-Z0-9]{10}", p.get("asin", "")):
            errs.append(n + " : ASIN invalide (10 caractères)")
        if p.get("asin") in seen:
            errs.append(n + " : ASIN en double")
        seen.add(p.get("asin"))
        for k in ("name", "who", "warn"):
            if not p.get(k):
                errs.append(f"{n} : champ « {k} » vide")
        mn, mx = p.get("min"), p.get("max")
        if not all(isinstance(v, (int, float)) for v in (mn, mx)) or mn > mx:
            errs.append(n + " : min et max doivent être des nombres (min <= max)")
        if p.get("type") not in TYPES:
            errs.append(n + " : type doit être " + " / ".join(sorted(TYPES)))
        if not p.get("use") or not set(p["use"]) <= USES:
            errs.append(n + " : use doit contenir " + " / ".join(sorted(USES)))
        if not p.get("feats"):
            errs.append(n + " : feats vide")
        if p.get("img") and not (ROOT / p["img"]).exists():
            print("Avertissement :", n, ": image introuvable ->", p["img"])
    for x in data["picks"]:
        if x["asin"] not in seen:
            errs.append("Sélection : ASIN inconnu " + x["asin"])
    return errs


def inject(name, items, html):
    pat = re.compile(r"const " + name + r"=\[.*?\n\];", re.S)
    if not pat.search(html):
        sys.exit("Impossible de trouver 'const " + name + "=[' dans index.html")
    body = ",\n".join(" " + json.dumps(x, ensure_ascii=False) for x in items)
    new = ("const " + name + "=[\n" + body + "\n];").replace("</", "<\\/")
    return pat.sub(lambda m: new, html, count=1)


def main():
    data = json.loads((ROOT / "products.json").read_text(encoding="utf-8"))
    errs = check(data)
    if errs:
        print("\n".join("ERREUR : " + e for e in errs))
        sys.exit(1)
    if "--date" in sys.argv:
        date = sys.argv[sys.argv.index("--date") + 1]
    else:
        d = datetime.date.today()
        date = f"{d.day}{'er' if d.day == 1 else ''} {MOIS[d.month - 1]} {d.year}"
    path = ROOT / "index.html"
    html = path.read_text(encoding="utf-8")
    html = inject("PRODUCTS", data["products"], html)
    html = inject("PICKS", data["picks"], html)
    n = len(data["products"])
    html = re.sub(r"Dernière mise à jour : [^<]*?\.", "Dernière mise à jour : " + date + ".", html)
    html = re.sub(r"(on te montre )\d+( modèles)", rf"\g<1>{n}\g<2>", html)
    html = re.sub(r"(compare )\d+( modèles)", rf"\g<1>{n}\g<2>", html)
    path.write_text(html, encoding="utf-8")
    print(f"OK : {n} produits, {len(data['picks'])} choix, mise à jour du {date}.")


main()
