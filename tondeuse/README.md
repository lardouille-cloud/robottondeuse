# RobotTondeuse.guide

Site comparatif de robots tondeuses 2026 — statique HTML/CSS/JS, hébergé sur GitHub Pages.

## Structure

```
├── index.html                    # Landing page
├── robots.html                   # Les 30 robots (9 gratuits / 21 payants)
├── comparatif.html               # Tableau comparatif
├── classement.html               # Classement par note (payant)
├── quiz.html                     # Sélection personnalisée (résultats payants)
├── fiche.html                    # Fiche détaillée d'un robot (?id=navimow)
├── comparateur.html              # Comparateur côte à côte
├── simulateur.html               # Simulateur de coût
├── checklist.html                # Checklist jardin
├── guide-pdf.html                # Guide des 7 erreurs
├── images/
│   ├── robots/                   # 30 images robots (local)
│   └── ui/                       # Images hero, avatars, jardins (local)
├── fonts/                        # Police Inter (local, pas de Google Fonts)
├── scripts/
│   └── update_prices.py          # Script mise à jour prix quotidienne
└── .github/workflows/
    └── update-prices.yml         # GitHub Actions — exécution quotidienne 06h UTC
```

## Déploiement GitHub Pages

1. Créer un repo GitHub (public ou privé)
2. Pousser le code :
   ```bash
   git remote add origin https://github.com/TON-COMPTE/TON-REPO.git
   git push -u origin master
   ```
3. Dans **Settings → Pages** : source = branche `master`, dossier `/` (root)
4. Le site sera accessible à `https://TON-COMPTE.github.io/TON-REPO/`

## Avant de mettre en ligne

- [ ] Remplacer `STRIPE_LINK_PLACEHOLDER` par ton vrai lien Stripe dans tous les fichiers HTML
- [ ] Vérifier le lien de retour Stripe (doit pointer vers `?access=granted`)
- [ ] Activer GitHub Pages dans les settings du repo

## Mise à jour des prix

Le script `scripts/update_prices.py` tourne automatiquement chaque jour à 06h UTC via GitHub Actions. Il scrape les prix et met à jour `index.html`, `fiche.html` et `PRICE_HISTORY.md`.

## Accès payant

- Clé localStorage : `rt_premium_v1`
- Robots gratuits : navimow, ecovacs, dreame, worx, yuka, luba2, husqvarna, mova, a3pro (9 premiers)
- Robots payants : tous les autres (21 robots)
- Prix : 9,90 € paiement unique via Stripe
