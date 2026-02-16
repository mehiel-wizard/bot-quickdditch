import discord
from discord.ext import commands
import os, random, asyncio
from flask import Flask
from threading import Thread

# --- SERVEUR WEB ---
app = Flask('')
@app.route('/')
def home(): return "Arbitre prêt"
def run(): app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)

# --- CONFIG BOT ---
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True 
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

def d(faces): return random.randint(1, faces)

# --- CALCUL DES RÈGLES ---
def calculer_tour(rj, ra):
    nb, bv = 0, rj['bat']
    txt_b = f"🏏 **Batteur ({bv})** : "
    ba, bd = 0, 0
    if bv == 1: (txt_b := txt_b + "⚠️ **Faute !** (-2 Déf)"), (bd := -2)
    elif bv == 2: (txt_b := txt_b + "🛡️ **Renfort !** (+2 Déf)"), (bd := 2)
    elif bv == 3: (txt_b := txt_b + "🎯 **Ouverture !** (+2 Atk)"), (ba := 2)
    elif bv == 4: txt_b += "💥 **Exploit !** (+1 but bonus)"

    bda = 2 if ra['bat'] == 2 else (-2 if ra['bat'] == 1 else 0)
    ai, di = rj['atk'], ra['def']
    fa, fd = ai + ba, di + bda
    ecart = fa - fd
    
    txt_a = f"\n🏹 **Atk: {ai}** ({fa}) vs **Def: {di}** ({fd}) : "
    if ecart > 0:
        nb = (3 if ecart >= 8 else (2 if ecart > 3 else 1))
        txt_a += "✅ **But !**"
    else: txt_a += "🧤 **Arrêté !**"
    
    if bv == 4: nb += 1
    return nb * 10, f"{txt_b}{txt_a}\n➡️ **Score : {nb*10} pts**"

# --- MOTEUR DE MATCH ---
async def lancer_match(ctx, names, players):
    j1, j2 = players[0], players[1]
    is_solo = (j2 == "CPU")
    j2_id = "CPU" if is_solo else j2.id
    scores = {j1.id: 0, j2_id: 0}
    
    for tour in range(1, 8):
        titre = f"🏟️ TOUR {tour} / 6" if tour <= 6 else "✨ TOUR FINAL : VIF D'OR"
        emb = discord.Embed(title=titre, description="Réagissez avec 🎲 pour lancer vos dés !", color=0x3498db)
        emb.set_author(name=f"{names[j1.id]} ⚔️ {names[j2_id]}")
        msg = await ctx.send(embed=emb)
        await msg.add_reaction("🎲")

        prets = []
        def check_sync(reaction, user):
            targets = [j1] if is_solo else [j1, j2]
            if user in targets and str(reaction.emoji) == "🎲" and reaction.message.id == msg.id:
                if user.id not in prets:
                    prets.append(user.id)
                    return is_solo or len(prets) == 2
            return False

        try:
            await bot.wait_for('reaction_add', timeout=120.0, check=check_sync)
        except asyncio.TimeoutError:
            return await ctx.send("🚨 Match annulé : Un joueur n'a pas lancé ses dés.")

        if tour <= 6:
            r1, r2 = {"atk": d(10), "def": d(6), "bat": d(4)}, {"atk": d(10), "def": d(6), "bat": d(4)}
            p1, d1 = calculer_tour(r1, r2); p2, d2 = calculer_tour(r2, r1)
            scores[j1.id] += p1; scores[j2_id] += p2

            res = discord.Embed(title=f"⚖️ RÉSULTATS TOUR {tour}", color=0xf1c40f)
            res.add_field(name=names[j1.id], value=d1, inline=False)
            res.add_field(name=names[j2_id], value=d2, inline=False)
            res.set_footer(text=f"Score : {scores[j1.id]} - {scores[j2_id]}")
            await ctx.send(embed=res)
        else:
            v1, v2 = d(100), d(100)
            win_id = j1.id if v1 > v2 else j2_id
            scores[win_id] += 50
            ev = discord.Embed(title="🟡 VIF D'OR", description=f"🎲 {names[j1.id]}: {v1} | {names[j2_id]}: {v2}\n🏆 **{names[win_id]}** l'attrape !", color=0xffd700)
            await ctx.send(embed=ev)
        await asyncio.sleep(2)

    s1, s2 = scores[j1.id], scores[j2_id]
    final = names[j1.id] if s1 > s2 else (names[j2_id] if s2 > s1 else "Égalité")
    await ctx.send(embed=discord.Embed(title="🏁 FIN DU MATCH", description=f"Victoire : **{final}** ({s1}-{s2})", color=0x2ecc71))

# --- INTERFACES ---
class StartView(discord.ui.View):
    def __init__(self, author):
        super().__init__(timeout=60)
        self.author = author

    @discord.ui.button(label="Mode Solo", style=discord.ButtonStyle.primary)
    async def solo(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author: return
        await interaction.response.send_message("🧙‍♂️ Quel est le nom de votre sorcier ?", ephemeral=True)
        try:
            m = await bot.wait_for('message', check=lambda m: m.author == self.author, timeout=30)
            names = {self.author.id: m.content, "CPU": "Équipe Adverse"}
            await lancer_match(interaction.channel, names, [self.author, "CPU"])
        except: pass

    @discord.ui.button(label="Mode Duel", style=discord.ButtonStyle.success)
    async def duel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author: return
        await interaction.response.send_message("⚔️ Pour lancer un duel, tapez : `!duel @adversaire`", ephemeral=True)

# --- COMMANDES ---
@bot.command()
async def match(ctx):
    await ctx.send("🏟️ **BIENVENUE AU QUIDDITCH**\nChoisissez votre mode de jeu :", view=StartView(ctx.author))

@bot.command()
async def duel(ctx, adversaire: discord.Member):
    if adversaire == ctx.author: return await ctx.send("Tu ne peux pas te défier toi-même !")
    await ctx.send(f"🧙‍♂️ {ctx.author.mention}, nom de votre sorcier ?")
    m1 = await bot.wait_for('message', check=lambda m: m.author == ctx.author)
    await ctx.send(f"🤝 {adversaire.mention}, nom de votre sorcier pour accepter ?")
    m2 = await bot.wait_for('message', check=lambda m: m.author == adversaire)
    await lancer_match(ctx, {ctx.author.id: m1.content, adversaire.id: m2.content}, [ctx.author, adversaire])

@bot.event
async def on_ready(): print(f"✅ Arbitre prêt !")

Thread(target=run, daemon=True).start()
bot.run(os.environ['DISCORD_TOKEN'])

