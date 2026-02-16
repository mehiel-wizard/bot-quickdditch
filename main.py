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
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

def d(faces): return random.randint(1, faces)

# --- LOGIQUE DE MATCH ---
class MatchView(discord.ui.View):
    def __init__(self, j1, names, is_solo=True):
        super().__init__(timeout=None)
        self.j1 = j1
        self.names = names
        self.scores = {j1.id: 0, "CPU": 0}
        self.tour = 1
        self.lock = asyncio.Lock()

    async def lancer_tour(self, channel):
        # On définit le titre selon le tour (1-6 ou Vif d'Or)
        if self.tour <= 6:
            titre = f"🏟️ TOUR {self.tour} / 6"
            desc = "Prêt pour le lancer ?"
        else:
            titre = "✨ TOUR FINAL : LE VIF D'OR"
            desc = "Attrapez-le avant l'adversaire !"

        embed = discord.Embed(title=titre, description=desc, color=0x3498db)
        embed.set_author(name=f"{self.names[self.j1.id]} ⚔️ {self.names['CPU']}")
        await channel.send(embed=embed, view=self)

    @discord.ui.button(label="LANCER LES DÉS 🎲", style=discord.ButtonStyle.success)
    async def lancer_bouton(self, interaction: discord.Interaction, button: discord.ui.Button):
        # RÉPONSE IMMEDIATE (Anti-bug)
        await interaction.response.defer(ephemeral=True)

        async with self.lock:
            # Désactive le bouton pour éviter le spam et les erreurs
            self.stop() 
            
            if self.tour <= 6:
                await self.resolution_normale(interaction.channel)
            else:
                await self.resolution_vif(interaction.channel)

    async def resolution_normale(self, channel):
        # Tirages
        r1 = {"atk": d(10), "def": d(6), "bat": d(4)}
        r2 = {"atk": d(10), "def": d(6), "bat": d(4)}

        def calculer_complet(rj, ra, nom_j):
            nb_buts = 0
            bv = rj['bat']
            txt_b = f"🏏 **Batteur ({bv})** : "
            
            # Application des règles Batteurs avec descriptions
            ba, bd = 0, 0
            if bv == 1: 
                txt_b += "⚠️ **Faute !** (-2 Défense)"
                bd = -2
            elif bv == 2: 
                txt_b += "🛡️ **Renfort !** (+2 Défense)"
                bd = 2
            elif bv == 3: 
                txt_b += "🎯 **Ouverture !** (+2 Attaque)"
                ba = 2
            elif bv == 4: 
                txt_b += "💥 **Exploit !** (+1 but bonus)"

            # Malus/Bonus défense adverse via batteur adverse
            bda = 2 if ra['bat'] == 2 else (-2 if ra['bat'] == 1 else 0)
            
            f_a = rj['atk'] + ba
            f_d = ra['def'] + bda
            ecart = f_a - f_d
            
            txt_a = f"\n🏹 **Attaque ({f_a})** vs **Défense ({f_d})** : "
            if ecart > 0:
                buts_ecart = 3 if ecart >= 8 else (2 if ecart > 3 else 1)
                nb_buts = buts_ecart
                txt_a += f"✅ **Réussi !** (Écart: {ecart})"
            else:
                txt_a += "🧤 **Arrêté !**"

            if bv == 4: nb_buts += 1
            pts = nb_buts * 10
            return pts, f"{txt_b}{txt_a}\n➡️ **RÉSULTAT : {nb_buts} but(s) ({pts} pts)**"

        p1, desc1 = calculer_complet(r1, r2, self.names[self.j1.id])
        p2, desc2 = calculer_complet(r2, r1, "CPU")
        
        self.scores[self.j1.id] += p1
        self.scores["CPU"] += p2

        embed = discord.Embed(title=f"⚖️ RÉSULTATS DU TOUR {self.tour}", color=0xf1c40f)
        embed.add_field(name=f"🧤 {self.names[self.j1.id]}", value=desc1, inline=False)
        embed.add_field(name="🧤 Équipe Adverse", value=desc2, inline=False)
        embed.set_footer(text=f"Score : {self.scores[self.j1.id]} - {self.scores['CPU']}")
        
        await channel.send(embed=embed)
        self.tour += 1
        await asyncio.sleep(2)
        await self.lancer_tour(channel)

    async def resolution_vif(self, channel):
        v1, v2 = d(100), d(100)
        n1 = self.names[self.j1.id]
        win_id = self.j1.id if v1 > v2 else "CPU"
        self.scores[win_id] += 50
        
        embed = discord.Embed(title="🟡 CAPTURE DU VIF D'OR", color=0xffd700)
        embed.description = f"🎲 **{n1}** : `{v1}` | **CPU** : `{v2}`\n\n🏆 **{self.names[win_id]}** l'attrape ! (+50 pts)"
        await channel.send(embed=embed)
        
        s1, s2 = self.scores[self.j1.id], self.scores["CPU"]
        final = n1 if s1 > s2 else ("Équipe Adverse" if s2 > s1 else "Égalité")
        await channel.send(f"# 🏁 MATCH TERMINÉ\nVictoire : **{final}** (`{s1}-{s2}`)")

# --- COMMANDES ---
@bot.command()
async def match(ctx):
    # Pour éviter le bug d'interaction, on demande le nom en texte simple juste avant
    await ctx.send("🧙‍♂️ **Bienvenue au Quidditch !**\nComment s'appelle votre sorcier ?")
    
    def check(m): return m.author == ctx.author and m.channel == ctx.channel
    
    try:
        msg = await bot.wait_for('message', check=check, timeout=30.0)
        nom = msg.content
    except asyncio.TimeoutError:
        nom = ctx.author.display_name

    names = {ctx.author.id: nom, "CPU": "Équipe Adverse"}
    game = MatchView(ctx.author, names)
    await game.lancer_tour(ctx)

@bot.event
async def on_ready():
    print(f"✅ Bot prêt : {bot.user}")

Thread(target=run, daemon=True).start()
bot.run(os.environ['DISCORD_TOKEN'])

