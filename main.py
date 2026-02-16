import discord
from discord.ext import commands
import os
import random
import asyncio
from flask import Flask
from threading import Thread

# --- SERVEUR WEB (Indispensable pour Render) ---
app = Flask('')
@app.route('/')
def home(): return "Arbitre en ligne ! 🏟️"

def run():
    # use_reloader=False est vital pour éviter de lancer le bot deux fois
    app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)

def keep_alive():
    t = Thread(target=run, daemon=True)
    t.start()

# --- CONFIGURATION DU BOT ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

def d(faces): return random.randint(1, faces)

# --- VUE DU MATCH ---
class MatchView(discord.ui.View):
    def __init__(self, j1, j2_id, names, is_solo):
        super().__init__(timeout=None)
        self.j1, self.j2_id, self.names, self.is_solo = j1, j2_id, names, is_solo
        self.scores = {j1.id: 0, j2_id: 0}
        self.tour = 1
        self.actions = {}
        self.lock = asyncio.Lock()
        self._en_cours = False

    async def lancer_tour(self, channel):
        self.actions = {self.j1.id: None}
        if not self.is_solo: self.actions[self.j2_id] = None
        self._en_cours = False
        
        embed = discord.Embed(title=f"🏟️ TOUR {self.tour} / 6", color=discord.Color.blue())
        embed.description = f"**{self.names[self.j1.id]}** ⚔️ **{self.names[self.j2_id]}**\n\nAppuyez sur le bouton pour lancer vos dés !"
        await channel.send(embed=embed, view=self)

    @discord.ui.button(label="LANCER LES DÉS 🎲", style=discord.ButtonStyle.success)
    async def lancer_bouton(self, interaction: discord.Interaction, button: discord.ui.Button):
        # ÉTAPE 1 : Réponse flash (0.1s). Discord valide l'interaction immédiatement.
        # On utilise ephemeral=True pour ne pas polluer le chat.
        await interaction.response.send_message(f"✅ Lancer enregistré pour {interaction.user.display_name} !", ephemeral=True)

        async with self.lock:
            uid = interaction.user.id
            if uid not in self.actions or self.actions[uid] is not None:
                return

            # Calcul des dés
            self.actions[uid] = {"atk": d(10), "def": d(6), "bat": d(4)}
            if self.is_solo: self.actions["CPU"] = {"atk": d(10), "def": d(6), "bat": d(4)}

            # Si tous les joueurs ont lancé
            if all(v is not None for v in self.actions.values()) and not self._en_cours:
                self._en_cours = True
                donnees_tours = self.actions.copy()
                self.actions.clear()
                
                # Désactivation des boutons pour ce tour
                self.stop()
                
                # On informe le canal public
                await interaction.channel.send(f"🎲 **Tous les dés sont jetés !** Calcul des résultats du tour {self.tour}...")
                await self.resolution_tour(interaction.channel, donnees_tours)

    async def resolution_tour(self, channel, acts):
        n1, n2 = self.names[self.j1.id], self.names[self.j2_id]
        r1, r2 = acts[self.j1.id], acts[self.j2_id]

        def calculer(r_j, r_adv):
            nb_buts, b_v = 0, r_j['bat']
            b_a, b_d = (2 if b_v == 3 else 0), (2 if b_v == 2 else (-2 if b_v == 1 else 0))
            b_da = 2 if r_adv['bat'] == 2 else (-2 if r_adv['bat'] == 1 else 0)
            
            f_a, f_da = r_j['atk'] + b_a, r_adv['def'] + b_da
            ecart = f_a - f_da
            
            txt_res = f"🏏 Batteur: {b_v} | 🏹 Atk: {f_a} vs Def: {f_da}"
            if ecart > 0:
                nb_buts = 3 if ecart >= 8 else (2 if ecart > 3 else 1)
                txt_res += " ✅"
            else: txt_res += " 🧤"
            
            if b_v == 4: nb_buts += 1
            return nb_buts * 10, txt_res

        p1, d1 = calculer(r1, r2)
        p2, d2 = calculer(r2, r1)
        self.scores[self.j1.id] += p1
        self.scores[self.j2_id] += p2
        
        embed = discord.Embed(title=f"⚖️ SCORE TOUR {self.tour}", color=discord.Color.gold())
        embed.add_field(name=f"🧤 {n1}", value=f"{d1}\n**+{p1} pts**", inline=False)
        embed.add_field(name=f"🧤 {n2}", value=f"{d2}\n**+{p2} pts**", inline=False)
        embed.set_footer(text=f"Total : {n1} {self.scores[self.j1.id]} - {self.scores[self.j2_id]} {n2}")
        await channel.send(embed=embed)
        
        self.tour += 1
        await asyncio.sleep(2)
        if self.tour <= 6: 
            await self.lancer_tour(channel)
        else: 
            await self.vif_dor(channel)

    async def vif_dor(self, channel):
        await channel.send("✨ **TOUR FINAL : LE VIF D'OR !**")
        await asyncio.sleep(2)
        v1, v2 = d(100), d(100)
        n1, n2 = self.names[self.j1.id], self.names[self.j2_id]
        win_id = self.j1.id if v1 > v2 else self.j2_id
        self.scores[win_id] += 50
        
        embed = discord.Embed(title="🟡 CAPTURE", description=f"🎲 **{n1}** : `{v1}` | **{n2}** : `{v2}`\n🏆 **{self.names[win_id]}** l'attrape ! (+50 pts)", color=discord.Color.yellow())
        await channel.send(embed=embed)
        
        s1, s2 = self.scores[self.j1.id], self.scores[self.j2_id]
        winner = n1 if s1 > s2 else (n2 if s2 > s1 else "Égalité")
        await channel.send(f"# 🏁 MATCH TERMINÉ\nVictoire : **{winner}** (`{s1}-{s2}`)")

# --- COMMANDES ---
@bot.command()
async def match(ctx):
    # Mode solo simplifié sans Modal pour tester la stabilité
    names = {ctx.author.id: "Sorcier", "CPU": "Équipe adverse"}
    await MatchView(ctx.author, "CPU", names, is_solo=True).lancer_tour(ctx)

@bot.event
async def on_ready():
    print(f"✅ Bot prêt : {bot.user}")

# --- LANCEMENT ---
if __name__ == "__main__":
    keep_alive()
    bot.run(os.environ['DISCORD_TOKEN'])
