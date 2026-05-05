# Instructions pour Claude

- Agir directement sans demander de confirmation ou de validation.
- Toujours faire `git add`, `git commit` et `git push` après chaque modification de fichier.
- Ne jamais proposer une action sans la faire immédiatement.

## Environnement local

- Python 3.14.3 installé, `pip` disponible dans le PATH (`C:\Users\Lo\AppData\Local\Programs\Python\Python314\Scripts`).
- `python` et `python3` ne sont PAS dans le PATH bash. Toujours utiliser l'outil PowerShell avec `py` (Windows launcher) pour exécuter Python.
- Pour les chemins Windows dans les scripts Python passés via `-c`, toujours utiliser des raw strings : `r'D:\...'`.
- Ne jamais utiliser `read_only=True` avec openpyxl si on a besoin de `.dimensions` — utiliser le mode normal.
