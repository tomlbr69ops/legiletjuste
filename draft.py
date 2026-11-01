#!/usr/bin/env python3
"""Rédige un brouillon de fiche gilet avec un modèle local (Ollama) et l'ajoute à products.json.

Usage :  python draft.py fiche.txt          (la fiche Amazon est dans un fichier texte)
         python draft.py                    (tu colles la fiche, puis une ligne FIN)
         python draft.py fiche.txt --model llama3.1:8b
"""
import json, re, sys, pathlib, shutil, urllib.request, urllib.error

ROOT = pathlib.Path(__file__).parent
PRODUCTS = ROOT / "products.json"
URL = "http://localhost:11434/api/chat"
TYPES = {"1": "fixe", "2": "versions", "3": "amovible"}
USES = {"marche", "course", "renfo"}

SYSTEM = """Tu rédiges des fiches pour un site français qui compare des gilets lestés.
Tu reçois le texte d'une fiche produit. Réponds UNIQUEMENT par un objet JSON avec ces clés :
- "who" : une phrase courte (90 caractères maximum) qui dit pour qui ou pour quel usage est le gilet.
- "warn" : une phrase courte sur UN point à vérifier avant d'acheter (taille, poids fixe, réglage, entretien...). Il doit découler du texte fourni.
- "feats" : liste de 3 ou 4 points forts courts, tirés du texte.
Règles : français, ton simple et factuel. Utilise uniquement des informations présentes dans le texte. N'invente aucun chiffre, aucune matière, aucune performance. Reformule avec tes mots, ne recopie pas de phrases. Pas de superlatifs. Aucune promesse de santé ou de perte de poids."""


def ask_model(model, text):
    body = json.dumps({
        "model": model, "stream": False, "format": "json", "options": {"temperature": 0.2},
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": "Texte de la fiche :\n" + text[:6000]}]}).encode()
    req = urllib.request.Request(URL, body, {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            out = json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"Ollama a répondu une erreur ({e.code}). Le modèle « {model} » est-il téléchargé ? Tape : ollama pull {model}")
    except urllib.error.URLError:
        sys.exit("Ollama ne répond pas. Lance l'application Ollama, puis réessaie.")
    try:
        d = json.loads(out["message"]["content"])
        who = str(d["who"]).strip()
        warn = str(d["warn"]).strip()
        feats = [str(f).strip() for f in d["feats"] if str(f).strip()][:4]
    except (KeyError, ValueError, TypeError):
        return None
    return (who, warn, feats) if who and warn and len(feats) >= 2 else None


def suspect(items, source):
    ok = {x.replace(",", ".") for x in re.findall(r"\d+(?:[.,]\d+)?", source)}
    return [n for t in items for n in re.findall(r"\d+(?:[.,]\d+)?", t) if n.replace(",", ".") not in ok]


def num(q):
    while True:
        try:
            v = float(input(q).replace(",", ".").strip())
            return int(v) if v == int(v) else v
        except ValueError:
            print("Entre un nombre, par exemple 4,5")


def main():
    args = sys.argv[1:]
    model = "hf.co/HauhauCS/Gemma-4-E4B-Uncensored-HauhauCS-Aggressive:Q4_K_M"
    if "--model" in args:
        i = args.index("--model")
        model = args[i + 1]
        del args[i:i + 2]
    data = json.loads(PRODUCTS.read_text(encoding="utf-8"))
    known = {p["asin"] for p in data["products"]}

    asin = input("ASIN (10 caractères, dans l'adresse Amazon après /dp/) : ").strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{10}", asin) or asin in known:
        sys.exit("ASIN invalide ou déjà présent dans products.json.")
    name = input("Nom affiché (ex. Sportneer 0,9 à 8 kg) : ").strip()
    mn, mx = num("Poids minimum en kg : "), num("Poids maximum en kg : ")
    t = ""
    while t not in TYPES:
        t = input("Type : 1 = poids fixe, 2 = plusieurs versions au choix, 3 = lests amovibles : ").strip()
    use = [u.strip() for u in input("Usages parmi marche, course, renfo (séparés par une virgule) : ").split(",")]
    if not use or not set(use) <= USES:
        sys.exit("Usages possibles : marche, course, renfo.")
    img = input("Nom du fichier photo dans images/ (vide s'il n'y en a pas) : ").strip()

    if args:
        text = pathlib.Path(args[0]).read_text(encoding="utf-8")
    else:
        print("Colle la fiche Amazon, puis écris FIN sur une ligne seule :")
        lines = []
        while (l := input()).strip() != "FIN":
            lines.append(l)
        text = "\n".join(lines)
    if len(text.strip()) < 80:
        sys.exit("La fiche est trop courte pour rédiger quelque chose de fiable.")

    while True:
        print("\nLe modèle rédige (ça peut prendre une minute)...")
        res = ask_model(model, text)
        if not res:
            print("Réponse inutilisable. Je réessaie.")
            continue
        who, warn, feats = res
        print(f"\n  Pour qui     : {who}\n  À vérifier   : {warn}")
        for f in feats:
            print("  Point fort   :", f)
        bad = suspect([who, warn] + feats, text)
        if bad:
            print("\n  ATTENTION : ces chiffres ne figurent pas dans la fiche :", ", ".join(bad))
            print("  Vérifie-les (ou corrige-les dans products.json après l'ajout).")
        c = input("\nAjouter à products.json ? o = oui, r = réécrire, n = annuler : ").strip().lower()
        if c == "r":
            continue
        if c != "o":
            sys.exit("Annulé. Rien n'a été modifié.")
        break

    p = {"asin": asin}
    if img:
        p["img"] = "images/" + img
    p.update({"name": name, "min": mn, "max": mx, "type": TYPES[t], "use": use,
              "who": who, "warn": warn, "feats": feats})
    shutil.copy(PRODUCTS, PRODUCTS.with_suffix(".json.bak"))
    data["products"].append(p)
    PRODUCTS.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("\nAjouté. Relis la fiche dans products.json, puis lance : python build.py")


main()
