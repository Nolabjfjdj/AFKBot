# AFKBot

AFKBot est un bot Discord écrit en Python qui peut rester connecté à un salon vocal jusqu'à ce qu'un administrateur le déconnecte.

## Commandes

- `/rejoindre salon:` connecte le bot au salon vocal sélectionné. S'il est déjà connecté, il change de salon.
- `/deco` déconnecte le bot.

Par défaut, ces commandes sont destinées aux membres ayant la permission **Gérer le serveur**.

## Installation

Python 3.10 ou une version plus récente est recommandé.

1. Crée une application et un bot dans le portail développeur Discord : https://discord.com/developers/applications
2. Active les commandes d'application et invite le bot sur ton serveur avec les autorisations nécessaires : voir les salons, se connecter et utiliser les commandes d'application.
3. Installe les dépendances avec `python -m pip install -r requirements.txt`.
4. Copie `.env.example` vers un fichier nommé `.env`, puis remplace la valeur de `DISCORD_TOKEN` par le jeton de ton bot.
5. Lance le bot avec `python bot.py`.

Ne partage jamais ton jeton et ne le commit pas dans GitHub. Le fichier `.env` est ignoré par Git.

## Disponibilité permanente

GitHub stocke le code mais ne fait pas tourner le bot. Pour qu'AFKBot reste connecté 24 h/24, lance-le sur un hébergement qui maintient un processus Python actif et autorise les connexions vocales Discord.

La reconnexion intégrée à la connexion vocale gère les interruptions temporaires du réseau. Si le bot est explicitement déconnecté du salon, utilise `/rejoindre` pour le faire revenir.

## Vérification avec UptimeRobot

Le bot expose un endpoint HTTP de santé sur `/` et `/health`. Sur Render, le serveur écoute sur le port fourni par la variable d'environnement `PORT` (avec `10000` comme valeur de secours).

Pour surveiller le service avec UptimeRobot, crée un monitor **HTTP(s)** vers l'URL publique de ton service Render, par exemple `https://ton-service.onrender.com/health`. Une réponse HTTP 200 confirme que le serveur HTTP répond, mais ne garantit pas à elle seule que le bot est connecté au salon vocal ni que le processus ne redémarrera jamais.
