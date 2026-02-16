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

# --- BOT CONFIG ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

def d(faces): return random.randint(1, faces)

class MatchView(discord.ui.View):
    def __init__(self, j1, names):
        super().__init__(timeout=None)
        self.j1 = j1
        self.names = names
        self.scores = {j1.id: 0, "CPU": 0}
        self.tour = 1
        self.lock = asyncio.Lock()

    @discord.ui.button(label="LANCER LES DÉS 🎲", style=discord.ButtonStyle.success)
    async def lancer_bouton(self, interaction: discord.Interaction, button: discord.ui.Button):
        # RÉPONSE ÉCLAIR
        try:
            await interaction.response.defer(ephemeral=True)
        except:
            return

        async with self.lock:
            button.disabled = True # Évite le spam
            await interaction.edit_original_response(view=self)

            # --- TES RÈGLES DE JEU ---
            r1 = {"atk": d(10), "def": d(6), "bat": d(4)}
            r2 = {"atk": d(10), "def": d(6), "bat": d(4)}

            def calculer_points(rj, ra):
                nb_buts = 0
                bv = rj['bat']
                ba = 2 if bv == 3 else 0
                bd = 2 if bv == 2 else (-2 if bv == 1 else 0)
                
                # Bonus/Malus Batteur adverse
                bda = 2 if ra['bat'] == 2 else (-2 if ra['bat'] == 1 else 0)
                
                # Calcul de l'écart Attaque vs Défense
                force_atk = rj['atk'] + ba
                force_def = ra['def'] + bda
                ecart = force_atk - force_def
                
                # Logique des buts
                if ecart > 0:
                    if ecart >= 8: nb_buts = 3
                    elif ecart > 3: nb_buts = 2
                    else: nb_buts = 1
                
                # Règle spéciale Batteur 4 (Exploit)
                if bv == 4: nb_buts += 1
                
                return nb_buts * 10, bv, force_atk, force_def

            p1, v1, a1, df1 = calculer_points(r1, r2)
            p2, v2, a2, df2 = calculer_points(r2, r1)
            
            self.scores[self.j1.id] += p1
            self.scores["CPU"] += p2

            # Affichage complet
            embed = discord.Embed(title=f"⚖️ RÉSULTAT TOUR {self.tour}", color=0xf1c40f)
            
            desc1 = f"🏏 Batteur: {v1}\n🏹 Atk: {a1} vs Def: {df1}\n➡️ **+{p1} pts**"
            desc2 = f"🏏 Batteur: {v2}\n🏹 Atk: {a2} vs Def: {df2}\n➡️ **+{p2} pts**"
            
            embed.add_field(name=self.names[self.j1.id], value=desc1, inline=False)
            embed.add_field(name="Équipe Adverse", value=desc2, inline=False)
            embed.set_footer(text=f"Score : {self.scores[self.j1.id]} - {self.scores['CPU']}")
            
            await interaction.channel.send(embed=embed)

            self.tour += 1
            if self.tour <= 6:
                await asyncio.sleep(2)
                button.disabled = False
                prochain = discord.Embed(title=f"🏟️ TOUR {self.tour} / 6", description="Prêt pour le prochain lancer ?", color=0x3498db)
                await interaction.channel.send(embed=prochain, view=self)
            else:
                await self.vif_dor(interaction.channel)

    async def vif_dor(self, channel):
        await channel.send("✨ **TOUR FINAL : LE VIF D'OR !**")
        await asyncio.sleep(2)
        v1, v2 = d(100), d(100)
        n1 = self.names[self.j1.id]
        
        if v1 > v2:
            self.scores[self.j1.id] += 50
            gagnant_vif = n1
        else:
            self.scores["CPU"] += 50
            gagnant_vif = "Équipe Adverse"
            
        embed = discord.Embed(title="🟡 CAPTURE", description=f"🎲 **{n1}** : `{v1}` | **CPU** : `{v2}`\n🏆 **{gagnant_vif}** l'attrape ! (+50 pts)", color=0xe74c3c)
        await channel.send(embed=embed)
        
        s1, s2 = self.scores[self.j1.id], self.scores["CPU"]
        final_win = n1 if s1 > s2 else ("Équipe Adverse" if s2 > s1 else "Égalité")
        await channel.send(f"# 🏁 SCORE FINAL\n**{n1}** {s1} - {s2} **CPU**\n🏆 Victoire : **{final_win}**")

@bot.command()
async def match(ctx):
    names = {ctx.author.id: ctx.author.display_name}
    await ctx.send(f"🏟️ **Match lancé pour {ctx.author.display_name} !**", view=MatchView(ctx.author, names))

@bot.event
async def on_ready(): print(f"✅ Bot prêt : {bot.user}")

if __name__ == "__main__":
    Thread(target=run, daemon=True).start()
    bot.run(os.environ['DISCORD_TOKEN'])
