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

# --- CONFIG BOT ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

def d(faces): return random.randint(1, faces)

# --- MODAL POUR LES NOMS ---
class NameModal(discord.ui.Modal):
    def __init__(self, player_num, parent_view):
        super().__init__(title=f"Nom du Sorcier - Joueur {player_num}")
        self.player_num, self.parent_view = player_num, parent_view
        self.name_input = discord.ui.TextInput(label="Nom du personnage", min_length=2, max_length=20)
        self.add_item(self.name_input)

    async def on_submit(self, interaction: discord.Interaction):
        self.parent_view.names[interaction.user.id] = self.name_input.value
        await interaction.response.send_message(f"✅ Nom enregistré : {self.name_input.value}", ephemeral=True)
        await self.parent_view.check_start(interaction.channel)

# --- CONFIGURATION MATCH ---
class SetupMatchView(discord.ui.View):
    def __init__(self, j1, j2=None, is_solo=False):
        super().__init__(timeout=120)
        self.j1, self.j2, self.is_solo = j1, j2, is_solo
        self.j2_id = "CPU" if is_solo else (j2.id if j2 else None)
        self.names = {j1.id: None, "CPU": "Équipe Adverse"} if is_solo else {j1.id: None, self.j2_id: None}

    @discord.ui.button(label="Joueur 1 : Nom", style=discord.ButtonStyle.secondary)
    async def set_j1(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id == self.j1.id:
            await interaction.response.send_modal(NameModal(1, self))

    @discord.ui.button(label="Joueur 2 : Nom", style=discord.ButtonStyle.secondary)
    async def set_j2(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_solo and interaction.user.id == self.j2.id:
            await interaction.response.send_modal(NameModal(2, self))

    async def check_start(self, channel):
        if all(v is not None for v in self.names.values()):
            self.stop()
            match = MatchView(self.j1, self.j2_id, self.names, self.is_solo)
            await match.lancer_tour(channel)

# --- MENU PRINCIPAL ---
class StartMenuView(discord.ui.View):
    def __init__(self, author):
        super().__init__(timeout=60)
        self.author = author

    @discord.ui.button(label="Mode Solo", style=discord.ButtonStyle.primary)
    async def solo(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author: return
        await interaction.response.edit_message(content="🧙‍♂️ **Configuration Solo**", view=SetupMatchView(self.author, is_solo=True))

    @discord.ui.button(label="Mode Duel", style=discord.ButtonStyle.success)
    async def duel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author: return
        await interaction.response.send_message("🤝 Pour rejoindre le duel, l'adversaire doit taper `!rejoindre`", ephemeral=False)

# --- LE MATCH ---
class MatchView(discord.ui.View):
    def __init__(self, j1, j2_id, names, is_solo):
        super().__init__(timeout=None)
        self.j1, self.j2_id, self.names, self.is_solo = j1, j2_id, names, is_solo
        self.scores = {j1.id: 0, j2_id: 0}
        self.tour = 1
        self.lock = asyncio.Lock()

    async def lancer_tour(self, channel):
        titre = f"🏟️ TOUR {self.tour} / 6" if self.tour <= 6 else "✨ TOUR FINAL : VIF D'OR"
        embed = discord.Embed(title=titre, color=0x3498db)
        embed.set_author(name=f"{self.names[self.j1.id]} ⚔️ {self.names[self.j2_id]}")
        embed.description = "Appuyez sur le bouton pour lancer !"
        await channel.send(embed=embed, view=self)

    @discord.ui.button(label="LANCER LES DÉS 🎲", style=discord.ButtonStyle.success)
    async def lancer_bouton(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer(ephemeral=True)
        except: return

        async with self.lock:
            self.stop()
            if self.tour <= 6: await self.resolution_tour(interaction.channel)
            else: await self.resolution_vif(interaction.channel)

    async def resolution_tour(self, channel):
        r1, r2 = {"atk": d(10), "def": d(6), "bat": d(4)}, {"atk": d(10), "def": d(6), "bat": d(4)}

        def calculer(rj, ra):
            nb, bv = 0, rj['bat']
            txt_b = f"🏏 **Batteur ({bv})** : "
            ba, bd = 0, 0
            if bv == 1: txt_b += "⚠️ **Faute !** (-2 Déf)"; bd = -2
            elif bv == 2: txt_b += "🛡️ **Renfort !** (+2 Déf)"; bd = 2
            elif bv == 3: txt_b += "🎯 **Ouverture !** (+2 Atk)"; ba = 2
            elif bv == 4: txt_b += "💥 **Exploit !** (+1 but bonus)"

            bda = 2 if ra['bat'] == 2 else (-2 if ra['bat'] == 1 else 0)
            fa, fd = rj['atk'] + ba, ra['def'] + bda
            ecart = fa - fd
            txt_a = f"\n🏹 **Attaque ({fa})** vs **Défense ({fd})** : "
            if ecart > 0:
                buts = 3 if ecart >= 8 else (2 if ecart > 3 else 1)
                nb = buts; txt_a += f"✅ **Réussi !** (Écart: {ecart})"
            else: txt_a += "🧤 **Arrêté !**"
            if bv == 4: nb += 1
            return nb * 10, f"{txt_b}{txt_a}\n➡️ **Score : {nb*10} pts**"

        p1, d1 = calculer(r1, r2); p2, d2 = calculer(r2, r1)
        self.scores[self.j1.id] += p1; self.scores[self.j2_id] += p2

        res = discord.Embed(title=f"⚖️ RÉSULTATS TOUR {self.tour}", color=0xf1c40f)
        res.add_field(name=self.names[self.j1.id], value=d1, inline=False)
        res.add_field(name=self.names[self.j2_id], value=d2, inline=False)
        res.set_footer(text=f"Total : {self.scores[self.j1.id]} - {self.scores[self.j2_id]}")
        await channel.send(embed=res)
        
        self.tour += 1
        await asyncio.sleep(2)
        await self.lancer_tour(channel)

    async def resolution_vif(self, channel):
        v1, v2 = d(100), d(100)
        win_id = self.j1.id if v1 > v2 else self.j2_id
        self.scores[win_id] += 50
        
        emb = discord.Embed(title="🟡 CAPTURE DU VIF D'OR", color=0xffd700)
        emb.description = f"🎲 **{self.names[self.j1.id]}** : `{v1}` | **{self.names[self.j2_id]}** : `{v2}`\n🏆 **{self.names[win_id]}** l'attrape !"
        await channel.send(embed=emb)
        
        s1, s2 = self.scores[self.j1.id], self.scores[self.j2_id]
        win = self.names[self.j1.id] if s1 > s2 else (self.names[self.j2_id] if s2 > s1 else "Égalité")
        await channel.send(f"# 🏁 FINAL : **{win}** ({s1}-{s2})")

@bot.command()
async def match(ctx):
    await ctx.send("🏟️ **BIENVENUE AU QUIDDITCH**", view=StartMenuView(ctx.author))

@bot.event
async def on_ready(): print(f"✅ Bot prêt : {bot.user}")

if __name__ == "__main__":
    Thread(target=run, daemon=True).start()
    bot.run(os.environ['DISCORD_TOKEN'])

