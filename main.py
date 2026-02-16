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

# --- LOGIQUE DE CALCUL ---
def calculer_tour(rj, ra):
    nb, bv = 0, rj['bat']
    txt_b = f"🏏 **Batteur ({bv})** : "
    ba, bd = 0, 0
    if bv == 1: (txt_b := txt_b + "⚠️ **Faute !** (-2 Déf)"), (bd := -2)
    elif bv == 2: (txt_b := txt_b + "🛡️ **Renfort !** (+2 Déf)"), (bd := 2)
    elif bv == 3: (txt_b := txt_b + "🎯 **Ouverture !** (+2 Atk)"), (ba := 2)
    elif bv == 4: txt_b += "💥 **Exploit !** (+1 but bonus)"

    # Malus/Bonus via batteur adverse
    bda = 2 if ra['bat'] == 2 else (-2 if ra['bat'] == 1 else 0)
    
    atk_init, def_init = rj['atk'], ra['def']
    fa, fd = atk_init + ba, def_init + bda
    ecart = fa - fd
    
    txt_a = f"\n🏹 **Atk: {atk_init}** (Total: {fa}) vs **Def: {def_init}** (Total: {fd}) : "
    if ecart > 0:
        nb = (3 if ecart >= 8 else (2 if ecart > 3 else 1))
        txt_a += f"✅ **Réussi !**"
    else: txt_a += "🧤 **Arrêté !**"
    
    if bv == 4: nb += 1
    return nb * 10, f"{txt_b}{txt_a}\n➡️ **Score : {nb*10} pts**"

# --- LE MATCH ---
async def lancer_match(ctx, names, is_solo=True, j2_obj=None):
    j2_id = "CPU" if is_solo else j2_obj.id
    scores = {ctx.author.id: 0, j2_id: 0}
    
    for tour in range(1, 8):
        titre = f"🏟️ TOUR {tour} / 6" if tour <= 6 else "✨ TOUR FINAL : VIF D'OR"
        emb = discord.Embed(title=titre, description="Réagissez avec 🎲 pour lancer vos dés !", color=0x3498db)
        emb.set_author(name=f"{names[ctx.author.id]} ⚔️ {names[j2_id]}")
        msg = await ctx.send(embed=emb)
        await msg.add_reaction("🎲")

        def check(reaction, user):
            valid_users = [ctx.author] if is_solo else [ctx.author, j2_obj]
            return user in valid_users and str(reaction.emoji) == "🎲" and reaction.message.id == msg.id

        try:
            # Augmentation du timeout à 120s pour éviter le "Match annulé" en cas de lag
            await bot.wait_for('reaction_add', timeout=120.0, check=check)
        except asyncio.TimeoutError:
            return await ctx.send("🚨 Match annulé : Temps de réaction trop long.")

        if tour <= 6:
            r1 = {"atk": d(10), "def": d(6), "bat": d(4)}
            r2 = {"atk": d(10), "def": d(6), "bat": d(4)}
            p1, d1 = calculer_tour(r1, r2)
            p2, d2 = calculer_tour(r2, r1)
            scores[ctx.author.id] += p1
            scores[j2_id] += p2

            res = discord.Embed(title=f"⚖️ RÉSULTATS TOUR {tour}", color=0xf1c40f)
            res.add_field(name=names[ctx.author.id], value=d1, inline=False)
            res.add_field(name=names[j2_id], value=d2, inline=False)
            res.set_footer(text=f"Score : {scores[ctx.author.id]} - {scores[j2_id]}")
            await ctx.send(embed=res)
        else:
            # --- FIX VIF D'OR (Correction de l'erreur d'affichage) ---
            v1, v2 = d(100), d(100)
            win_id = ctx.author.id if v1 > v2 else j2_id
            scores[win_id] += 50
            emb_v = discord.Embed(title="🟡 CAPTURE DU VIF D'OR", description=f"🎲 {names[ctx.author.id]}: {v1} | {names[j2_id]}: {v2}\n\n🏆 **{names[win_id]}** l'attrape ! (+50 pts)", color=0xffd700)
            await ctx.send(embed=emb_v)

        await asyncio.sleep(2)

    s1, s2 = scores[ctx.author.id], scores[j2_id]
    final = names[ctx.author.id] if s1 > s2 else (names[j2_id] if s2 > s1 else "Égalité")
    
    # Résumé final
    fin_emb = discord.Embed(title="🏁 MATCH TERMINÉ", description=f"**{names[ctx.author.id]}** {s1} - {s2} **{names[j2_id]}**", color=0x2ecc71)
    fin_emb.add_field(name="Vainqueur", value=f"🏆 **{final}**")
    await ctx.send(embed=fin_emb)

@bot.command()
async def match(ctx):
    # --- CHOIX DU MODE ---
    menu_emb = discord.Embed(title="🏟️ MENU QUIDDITCH", description="Choisissez votre mode :\n1️⃣ **SOLO**\n2️⃣ **DUEL**", color=0x9b59b6)
    menu_msg = await ctx.send(embed=menu_emb)
    await menu_msg.add_reaction("1️⃣")
    await menu_msg.add_reaction("2️⃣")

    def check_mode(reaction, user):
        return user == ctx.author and str(reaction.emoji) in ["1️⃣", "2️⃣"] and reaction.message.id == menu_msg.id

    try:
        reaction, user = await bot.wait_for('reaction_add', timeout=60, check=check_mode)
        mode = "solo" if str(reaction.emoji) == "1️⃣" else "duel"
    except: return

    # --- NOMS ---
    await ctx.send(f"🧙‍♂️ Nom de votre sorcier **{ctx.author.display_name}** ?")
    def check_name1(m): return m.author == ctx.author and m.channel == ctx.channel
    msg_nom = await bot.wait_for('message', check=check_name1)
    nom1 = msg_nom.content

    if mode == "solo":
        await lancer_match(ctx, {ctx.author.id: nom1, "CPU": "Équipe Adverse"}, is_solo=True)
    else:
        await ctx.send("🤝 **Adversaire**, tapez votre nom pour rejoindre le match !")
        def check_j2(m): return m.author != ctx.author and m.channel == ctx.channel
        msg_j2 = await bot.wait_for('message', check=check_j2)
        nom2 = msg_j2.content
        await lancer_match(ctx, {ctx.author.id: nom1, msg_j2.author.id: nom2}, is_solo=False, j2_obj=msg_j2.author)

@bot.event
async def on_ready(): print(f"✅ Arbitre prêt !")

Thread(target=run, daemon=True).start()
bot.run(os.environ['DISCORD_TOKEN'])
