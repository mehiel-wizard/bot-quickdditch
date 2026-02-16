import discord
from discord.ext import commands
import os, random, asyncio
from flask import Flask
from threading import Thread

# --- SERVEUR WEB ---
app = Flask('')
@app.route('/')
def home(): return "Arbitre en ligne ! 🏟️"

def run():
    app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)

def keep_alive():
    t = Thread(target=run, daemon=True); t.start()

# --- CONFIG BOT ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

def d(faces): return random.randint(1, faces)

# --- FENÊTRE DE NOM ---
class NameModal(discord.ui.Modal):
    def __init__(self, player_num, parent_view):
        super().__init__(title=f"Nom du Sorcier - Joueur {player_num}")
        self.player_num, self.parent_view = player_num, parent_view
        self.name_input = discord.ui.TextInput(label="Entrez votre nom", min_length=2, max_length=20)
        self.add_item(self.name_input)

    async def on_submit(self, interaction: discord.Interaction):
        self.parent_view.names[interaction.user.id] = self.name_input.value
        await interaction.response.send_message(f"✅ Nom enregistré : **{self.name_input.value}**", ephemeral=True)
        await self.parent_view.check_start(interaction.channel)

# --- MENU DE DÉPART ---
class StartMenuView(discord.ui.View):
    def __init__(self, author):
        super().__init__(timeout=60)
        self.author = author

    @discord.ui.button(label="Mode Solo", style=discord.ButtonStyle.primary)
    async def solo(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author: return
        view = SetupMatchView(self.author, is_solo=True)
        await interaction.response.edit_message(content="🧙‍♂️ **Configuration Mode Solo**", view=view)

    @discord.ui.button(label="Mode Duel", style=discord.ButtonStyle.success)
    async def duel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author: return
        await interaction.response.edit_message(content="🤝 **Duel** : Demandez à votre adversaire de taper `!rejoindre`", view=None)

# --- CONFIGURATION DES JOUEURS ---
class SetupMatchView(discord.ui.View):
    def __init__(self, j1, j2=None, is_solo=False):
        super().__init__(timeout=120)
        self.j1, self.is_solo = j1, is_solo
        self.j2_id = "CPU" if is_solo else (j2.id if j2 else None)
        self.names = {j1.id: None, "CPU": "Équipe Adverse"} if is_solo else {j1.id: None}

    @discord.ui.button(label="Définir mon Nom", style=discord.ButtonStyle.secondary)
    async def set_name(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(NameModal(1, self))

    async def check_start(self, channel):
        if all(v is not None for v in self.names.values()):
            self.stop()
            match = MatchView(self.j1, self.j2_id, self.names, self.is_solo)
            await match.lancer_tour(channel)

# --- LE MATCH ---
class MatchView(discord.ui.View):
    def __init__(self, j1, j2_id, names, is_solo):
        super().__init__(timeout=None)
        self.j1, self.j2_id, self.names, self.is_solo = j1, j2_id, names, is_solo
        self.scores = {j1.id: 0, j2_id: 0}
        self.tour = 1
        self.actions = {}
        self.lock = asyncio.Lock()

    async def lancer_tour(self, channel):
        self.actions = {self.j1.id: None}
        if not self.is_solo: self.actions[self.j2_id] = None
        
        title = f"🏟️ TOUR {self.tour} / 6" if self.tour <= 6 else "✨ TOUR FINAL : VIF D'OR"
        embed = discord.Embed(title=title, color=0x3498db)
        embed.description = f"**{self.names[self.j1.id]}** ⚔️ **{self.names[self.j2_id]}**\n\nAppuyez pour lancer les dés !"
        await channel.send(embed=embed, view=self)

    @discord.ui.button(label="LANCER LES DÉS 🎲", style=discord.ButtonStyle.success)
    async def lancer_bouton(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        async with self.lock:
            uid = interaction.user.id
            if uid not in self.actions or self.actions[uid] is not None: return

            self.actions[uid] = {"atk": d(10), "def": d(6), "bat": d(4)}
            if self.is_solo: self.actions["CPU"] = {"atk": d(10), "def": d(6), "bat": d(4)}

            if all(v is not None for v in self.actions.values()):
                data = self.actions.copy(); self.actions.clear(); self.stop()
                if self.tour <= 6: await self.resolution_tour(interaction.channel, data)
                else: await self.resolution_vif(interaction.channel, data)

    async def resolution_tour(self, channel, acts):
        n1, n2 = self.names[self.j1.id], self.names[self.j2_id]
        r1, r2 = acts[self.j1.id], acts[self.j2_id]

        def calculer(rj, ra):
            bv = rj['bat']
            ba = 2 if bv == 3 else 0
            bd = 2 if bv == 2 else (-2 if bv == 1 else 0)
            bda = 2 if ra['bat'] == 2 else (-2 if ra['bat'] == 1 else 0)
            f_a, f_d = rj['atk'] + ba, ra['def'] + bda
            ecart = f_a - f_d
            nb = (3 if ecart >= 8 else (2 if ecart > 3 else 1)) if ecart > 0 else 0
            if bv == 4: nb += 1
            return nb * 10, f"🏏Bat:{bv} | 🏹Atk:{f_a} vs Def:{f_d}"

        p1, d1 = calculer(r1, r2); p2, d2 = calculer(r2, r1)
        self.scores[self.j1.id] += p1; self.scores[self.j2_id] += p2
        
        emb = discord.Embed(title=f"⚖️ RÉSULTATS TOUR {self.tour}", color=0xf1c40f)
        emb.add_field(name=n1, value=f"{d1}\n**+{p1} pts**", inline=False)
        emb.add_field(name=n2, value=f"{d2}\n**+{p2} pts**", inline=False)
        emb.set_footer(text=f"Score: {n1} {self.scores[self.j1.id]} - {self.scores[self.j2_id]} {n2}")
        await channel.send(embed=emb)
        
        self.tour += 1
        await asyncio.sleep(2)
        await self.lancer_tour(channel)

    async def resolution_vif(self, channel, acts):
        v1, v2 = d(100), d(100)
        n1, n2 = self.names[self.j1.id], self.names[self.j2_id]
        win_id = self.j1.id if v1 > v2 else self.j2_id
        self.scores[win_id] += 50
        
        emb = discord.Embed(title="🟡 CAPTURE DU VIF D'OR", color=0xffd700)
        emb.description = f"🎲 **{n1}** : `{v1}` | **{n2}** : `{v2}`\n\n🏆 **{self.names[win_id]}** l'attrape ! (+50 pts)"
        await channel.send(embed=emb)
        
        s1, s2 = self.scores[self.j1.id], self.scores[self.j2_id]
        final = n1 if s1 > s2 else (n2 if s2 > s1 else "Égalité")
        await channel.send(f"# 🏁 MATCH TERMINÉ\nVictoire : **{final}** (`{s1}-{s2}`)")

@bot.command()
async def match(ctx):
    await ctx.send("🧙‍♂️ **Bienvenue au Quidditch !**", view=StartMenuView(ctx.author))

@bot.event
async def on_ready(): print(f"✅ Arbitre prêt !")

keep_alive()
bot.run(os.environ['DISCORD_TOKEN'])
