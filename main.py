import discord
from discord.ext import commands
import os, random, asyncio
from flask import Flask
from threading import Thread

# --- SERVEUR WEB ---
app = Flask('')
@app.route('/')
def home(): return "Arbitre OK"
def run(): app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)

# --- CONFIG BOT ---
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True 
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

def d(faces): return random.randint(1, faces)

# --- LOGIQUE DE CALCUL (TES RÈGLES) ---
def calculer_tour(rj, ra):
    nb, bv = 0, rj['bat']
    txt_b = f"🏏 **Batteur ({bv})** : "
    ba, bd = 0, 0
    if bv == 1: (txt_b := txt_b + "⚠️ **Faute !** (-2 Déf)"), (bd := -2)
    elif bv == 2: (txt_b := txt_b + "🛡️ **Renfort !** (+2 Déf)"), (bd := 2)
    elif bv == 3: (txt_b := txt_b + "🎯 **Ouverture !** (+2 Atk)"), (ba := 2)
    elif bv == 4: txt_b += "💥 **Exploit !** (+1 but bonus)"

    bda = 2 if ra['bat'] == 2 else (-2 if ra['bat'] == 1 else 0)
    fa, fd = rj['atk'] + ba, ra['def'] + bda
    ecart = fa - fd
    
    txt_a = f"\n🏹 **Attaque ({fa})** vs **Défense ({fd})** : "
    if ecart > 0:
        nb = (3 if ecart >= 8 else (2 if ecart > 3 else 1))
        txt_a += f"✅ **Réussi !** (Écart: {ecart})"
    else: txt_a += "🧤 **Arrêté !**"
    
    if bv == 4: nb += 1
    return nb * 10, f"{txt_b}{txt_a}\n➡️ **Score : {nb*10} pts**"

# --- LE MATCH ---
async def lancer_match(ctx, names, is_solo=True):
    scores = {ctx.author.id: 0, "CPU": 0}
    
    for tour in range(1, 8):
        titre = f"🏟️ TOUR {tour} / 6" if tour <= 6 else "✨ TOUR FINAL : VIF D'OR"
        emb = discord.Embed(title=titre, description="Réagissez avec 🎲 pour lancer !", color=0x3498db)
        emb.set_author(name=f"{names[ctx.author.id]} ⚔️ {names['CPU']}")
        msg = await ctx.send(embed=emb)
        await msg.add_reaction("🎲")

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) == "🎲" and reaction.message.id == msg.id

        try:
            await bot.wait_for('reaction_add', timeout=60.0, check=check)
        except asyncio.TimeoutError:
            return await ctx.send("Match annulé.")

        if tour <= 6:
            r1, r2 = {"atk": d(10), "def": d(6), "bat": d(4)}, {"atk": d(10), "def": d(6), "bat": d(4)}
            p1, d1 = calculer_tour(r1, r2)
            p2, d2 = calculer_tour(r2, r1)
            scores[ctx.author.id] += p1
            scores["CPU"] += p2

            res = discord.Embed(title=f"⚖️ RÉSULTATS TOUR {tour}", color=0xf1c40f)
            res.add_field(name=names[ctx.author.id], value=d1, inline=False)
            res.add_field(name=names["CPU"], value=d2, inline=False)
            res.set_footer(text=f"Total : {scores[ctx.author.id]} - {scores['CPU']}")
            await ctx.send(embed=res)
        else:
            # VIF D'OR
            v1, v2 = d(100), d(100)
            win_id = ctx.author.id if v1 > v2 else "CPU"
            scores[win_id] += 50
            emb_v = discord.Embed(title="🟡 VIF D'OR", description=f"🎲 {names[ctx.author.id]}: {v1} | CPU: {v2}\n🏆 **{names[win_id]}** l'attrape !", color=0xffd700)
            await ctx.send(embed=emb_v)

        await asyncio.sleep(2)

    s1, s2 = scores[ctx.author.id], scores["CPU"]
    final = names[ctx.author.id] if s1 > s2 else (names["CPU"] if s2 > s1 else "Égalité")
    await ctx.send(f"# 🏁 FINAL : **{final}** ({s1}-{s2})")

@bot.command()
async def match(ctx):
    await ctx.send("🧙‍♂️ **Nom de votre sorcier ?** (Répondez dans le chat)")
    def check(m): return m.author == ctx.author and m.channel == ctx.channel
    try:
        msg = await bot.wait_for('message', timeout=30, check=check)
        nom = msg.content
    except: nom = ctx.author.display_name

    await ctx.send("🏟️ **Préparation du terrain...**")
    await lancer_match(ctx, {ctx.author.id: nom, "CPU": "Équipe Adverse"})

@bot.event
async def on_ready(): print(f"✅ Bot prêt : {bot.user}")

Thread(target=run, daemon=True).start()
bot.run(os.environ['DISCORD_TOKEN'])
