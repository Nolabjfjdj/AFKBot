import asyncio
import logging
import os

import discord
from aiohttp import web
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("AFKBot")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

desired_voice_channels: dict[int, int] = {}
voice_disconnected_since: dict[int, float] = {}
VOICE_RECONNECT_GRACE_SECONDS = 120


@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        logger.info("Commandes synchronisées : %s", len(synced))
    except discord.HTTPException:
        logger.exception("Impossible de synchroniser les commandes.")
    if not voice_watchdog.is_running():
        voice_watchdog.start()
    logger.info("Connecté en tant que %s (ID : %s)", bot.user, bot.user.id)
    logger.info("Version discord.py : %s", discord.__version__)


@tasks.loop(seconds=15)
async def voice_watchdog():
    for guild_id, channel_id in list(desired_voice_channels.items()):
        guild = bot.get_guild(guild_id)
        if guild is None:
            continue

        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.VoiceChannel):
            logger.warning("Le salon vocal mémorisé %s n'est plus accessible.", channel_id)
            continue

        voice_client = guild.voice_client
        if voice_client is not None and voice_client.is_connected():
            voice_disconnected_since.pop(guild_id, None)
            if voice_client.channel and voice_client.channel.id != channel_id:
                try:
                    await voice_client.move_to(channel)
                except (discord.HTTPException, discord.ClientException):
                    logger.exception("Impossible de replacer AFKBot dans le salon vocal %s.", channel_id)
            continue

        now = asyncio.get_running_loop().time()
        disconnected_at = voice_disconnected_since.setdefault(guild_id, now)

        # discord.py already retries temporary voice WebSocket failures.
        # Do not force-disconnect its VoiceClient while those retries may be active.
        if voice_client is not None and now - disconnected_at < VOICE_RECONNECT_GRACE_SECONDS:
            continue

        try:
            if voice_client is not None:
                logger.warning(
                    "Connexion vocale toujours inactive après %s secondes ; nettoyage de l'ancienne connexion.",
                    VOICE_RECONNECT_GRACE_SECONDS,
                )
                try:
                    await voice_client.disconnect(force=True)
                except (discord.HTTPException, discord.ClientException):
                    logger.warning("Nettoyage de l'ancienne connexion vocale impossible.", exc_info=True)
            await channel.connect(timeout=30, reconnect=True)
            voice_disconnected_since.pop(guild_id, None)
            logger.info("Connexion vocale rétablie dans %s (%s).", channel.name, channel.id)
        except (discord.Forbidden, discord.HTTPException, discord.ClientException, asyncio.TimeoutError):
            logger.exception("Échec de la reconnexion vocale au salon %s ; nouvelle tentative ultérieure.", channel_id)


@voice_watchdog.before_loop
async def before_voice_watchdog():
    await bot.wait_until_ready()


@bot.tree.command(name="rejoindre", description="Fait rejoindre AFKBot à un salon vocal.")
@app_commands.describe(salon="Le salon vocal que le bot doit rejoindre")
@app_commands.default_permissions(manage_guild=True)
@app_commands.guild_only()
async def rejoindre(interaction: discord.Interaction, salon: discord.VoiceChannel):
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("Tu dois avoir la permission Gérer le serveur pour utiliser cette commande.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True, thinking=True)
    voice_client = interaction.guild.voice_client
    try:
        if voice_client and voice_client.is_connected():
            if voice_client.channel and voice_client.channel.id == salon.id:
                desired_voice_channels[interaction.guild.id] = salon.id
                await interaction.followup.send(f"Je suis déjà connecté à {salon.mention}. Je surveille la connexion et tenterai de revenir si elle tombe.", ephemeral=True)
                return
            await voice_client.move_to(salon)
        else:
            if voice_client is not None:
                try:
                    await voice_client.disconnect(force=True)
                except (discord.HTTPException, discord.ClientException):
                    logger.warning("Nettoyage de l'ancienne connexion vocale impossible.", exc_info=True)
            await salon.connect(timeout=20, reconnect=True)

        desired_voice_channels[interaction.guild.id] = salon.id
        await interaction.followup.send(f"✅ Je suis connecté à {salon.mention}. Je surveille la connexion et tenterai de revenir si elle tombe. Utilise /deco pour arrêter cette reconnexion automatique.", ephemeral=True)
        logger.info("Connexion au salon %s (%s) demandée par %s (%s)", salon.name, salon.id, interaction.user, interaction.user.id)
    except (discord.Forbidden, discord.HTTPException, discord.ClientException, asyncio.TimeoutError):
        logger.exception("Échec de connexion vocale.")
        await interaction.followup.send("❌ Impossible de rejoindre ce salon. Vérifie mes permissions Voir le salon et Se connecter.", ephemeral=True)


@bot.tree.command(name="deco", description="Déconnecte AFKBot du salon vocal.")
@app_commands.default_permissions(manage_guild=True)
@app_commands.guild_only()
async def deco(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("Tu dois avoir la permission Gérer le serveur pour utiliser cette commande.", ephemeral=True)
        return

    desired_voice_channels.pop(interaction.guild.id, None)
    voice_client = interaction.guild.voice_client
    if voice_client is None or not voice_client.is_connected():
        await interaction.response.send_message("Je ne suis connecté à aucun salon vocal. La reconnexion automatique est désactivée.", ephemeral=True)
        return

    channel_name = voice_client.channel.name if voice_client.channel else "le salon vocal"
    await voice_client.disconnect(force=True)
    await interaction.response.send_message(f"👋 Je me suis déconnecté de {channel_name} et j'ai désactivé la reconnexion automatique.", ephemeral=True)
    logger.info("Déconnexion demandée par %s (%s)", interaction.user, interaction.user.id)


async def health_check(request: web.Request) -> web.Response:
    return web.Response(text="AFKBot is running.", status=200)


async def start_health_server() -> web.AppRunner:
    app = web.Application()
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", "10000"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Serveur de santé HTTP lancé sur le port %s", port)
    return runner


async def main():
    if not TOKEN:
        raise RuntimeError("Le jeton Discord manque : ajoute DISCORD_TOKEN dans le fichier .env.")
    runner = await start_health_server()
    try:
        async with bot:
            await bot.start(TOKEN)
    finally:
        if voice_watchdog.is_running():
            voice_watchdog.cancel()
        await runner.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Arrêt demandé.")
