import discord
from discord.ext import commands
import os
import random
import asyncio
from flask import Flask
from threading import Thread

# --- SERVEUR ANTI-SOMMEIL ---
app = Flask('')
@app.route('/')
def home(): return "L'arbitre est sur le terrain ! 🏟️"

def run(): app.run(host='0.0.0.0', port=8080)
def keep_alive():
    t = Thread(target=run)
    t.start()

# --- CONFIG BOT ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

def d(faces): return random.randint(1, faces)

# --- VUE DU VIF D'OR (LANCER MANUEL SÉCURISÉ) ---
class VifDorMatchView(discord.ui.View):
    def __init__(self, game_instance, channel):
        super().__init__(timeout=180)
        self.game = game_instance
        self.channel = channel
        self.lancers = {self.game.j1.id: None, self.game.j2_id: None}
        self.processing = False # Verrou de sécurité

    @discord.ui.button(label="LANCER LE DÉ 100 🎲", style=discord.ButtonStyle.success, emoji="🏆")
    async def lancer_vif(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        if uid not in self.lancers or self.lancers[uid] is not None or self.processing:
            return await interaction.response.send_message("Action déjà enregistrée ou match en cours de calcul.", ephemeral=True)

        self.lancers[uid] = d(100)
        if self.game.is_solo: self.lancers["CPU"] = d(100)

        if all(v is not None for v in self.lancers.values()):
            self.processing = True # On verrouille tout de suite
            self.stop()
            
            v1, v2 = self.lancers[self.game.j1.id], self.lancers[self.game.j2_id]
            n1, n2 = self.game.names[self.game.j1.id], self.game.names[self.game.j2_id]
            
            win_id = self.game.j1.id if v1 > v2 else self.game.j2_id
            self.game.scores[win_id] += 50
            
            embed = discord.Embed(title="🟡 RÉSULTAT DU VIF D'OR", 
                                  description=f"🎲 **{n1}** : `{v1}` | **{n2}** : `{v2}`\n🏆 **{self.game.names[win_id]}** l'attrape !", 
                                  color=discord.Color.yellow())
            
            await interaction.response.edit_message(content="✨ Le Vif d'Or a été capturé !", view=None)
            await self.channel.send(embed=embed)
            
            s1, s2 = self.game.scores[self.game.j1.id], self.game.scores[self.game.j2_id]
            winner = n1 if s1 > s2 else (n2 if s2 > s1 else "Égalité")
            await self.channel.send(f"# 🏁 FINAL : **{winner}** (`{s1}-{s2}`)")
        else:
            await interaction.response.edit_message(content=f"✅ **{interaction.user.display_name}** a lancé son dé !")

# --- LOGIQUE DE MATCH SÉCURISÉE ---
class MatchView(discord.ui.View):
    def __init__(self, j1, j2_id, names, is_solo):
        super().__init__(timeout=300)
        self.j1, self.j2_id, self.names, self.is_solo = j1, j2_id, names, is_solo
        self.scores = {j1.id: 0, j2_id: 0}
        self.tour = 1
        self.actions = {}
        self.processing = False # Verrou de sécurité

    async def lancer_tour(self, channel):
        self.processing = False
        self.actions = {self.j1.id: None}
        if not self.is_solo: self.actions[self.j2_id] = None
        
        embed = discord.Embed(title=f"🏟️ TOUR {self.tour} / 6", color=discord.Color.blue())
        embed.description = f"**{self.names[self.j1.id]}** ⚔️ **{self.names[self.j2_id]}**\nEn attente des lancers..."
        await channel.send(embed=embed, view=self)

    @discord.ui.button(label="LANCER LES DÉS 🎲", style=discord.ButtonStyle.success)
    async def lancer_bouton(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        if uid not in self.actions or self.actions[uid] is not None or self.processing: 
            return

        self.actions[uid] = {"atk": d(10), "def": d(6), "bat": d(4)}
        if self.is_solo: self.actions["CPU"] = {"atk": d(10), "def": d(6), "bat": d(4)}
        
        if all(v is not None for v in self.actions.values()):
            self.processing = True # Bloque toute autre exécution
            self.stop()
            await interaction.response.edit_message(content="🎲 Calcul des scores...", embed=None, view=None)
            await self.resolution_tour(interaction.channel)
        else:
            await interaction.response.edit_message(content=f"✅ {interaction.user.display_name} a lancé !")

    async def resolution_tour(self, channel):
        n1, n2 = self.names[self.j1.id], self.names[self.j2_id]
        r1, r2 = self.actions[self.j1.id], self.actions[self.j2_id]
        
        def calculer(r_j, r_adv):
            nb_buts, b_v = 0, r_j['bat']
            b_a = 2 if b_v == 3 else 0
            b_d = -2 if b_v == 1 else (2 if b_v == 2 else 0)
            b_da = -2 if r_adv['bat'] == 1 else (2 if r_adv['bat'] == 2 else 0)
            f_a, f_da = r_j['atk'] + b_a, r_adv['def'] + b_da
            ecart = f_a - f_da
            if ecart > 0: nb_buts = 3 if ecart >= 8 else (2 if ecart > 3 else 1)
            if b_v == 4: nb_buts += 1
            return nb_buts * 10, f"🏏 Batteur: {b_v} | 🏹 Atk: {f_a} vs Def: {f_da}"

        p1, d1 = calculer(r1, r2)
        p2, d2 = calculer(r2, r1)
        self.scores[self.j1.id] += p1
        self.scores[self.j2_id] += p2
        
        embed = discord.Embed(title=f"⚖️ SCORE TOUR {self.tour}", color=discord.Color.gold())
        embed.add_field(name=n1, value=d1, inline=False)
        embed.add_field(name=n2, value=d2, inline=False)
        embed.set_footer(text=f"Total: {n1} {self.scores[self.j1.id]} - {self.scores[self.j2_id]} {n2}")
        await channel.send(embed=embed)
        
        self.tour += 1
        await asyncio.sleep(2)
        if self.tour <= 6:
            await self.lancer_tour(channel)
        else:
            await self.vif_dor(channel)

    async def vif_dor(self, channel):
        await channel.send("✨ **VIF D'OR !**")
        view = VifDorMatchView(self, channel)
        await channel.send(f"🏆 Cliquez sur le bouton doré pour tenter d'attraper le Vif d'Or (Dé 100) !", view=view)

# --- CLASSES DE CONFIGURATION (NameModal, StartMenuView, SetupMatchView) ---
class NameModal(discord.ui.Modal):
    def __init__(self, player_num, parent_view):
        super().__init__(title=f"Nom du Personnage - Joueur {player_num}")
        self.player_num, self.parent_view = player_num, parent_view
        self.name_input = discord.ui.TextInput(label="Nom du sorcier", min_length=2, max_length=20)
        self.add_item(self.name_input)
    async def on_submit(self, interaction: discord.Interaction):
        self.parent_view.names[interaction.user.id] = self.name_input.value
        await interaction.response.send_message(f"✅ Nom enregistré : **{self.name_input.value}**", ephemeral=True)
        await self.parent_view.check_start(interaction.channel)

class StartMenuView(discord.ui.View):
    def __init__(self, author):
        super().__init__(timeout=60)
        self.author = author
    @discord.ui.button(label="Mode Solo", style=discord.ButtonStyle.primary)
    async def solo(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author: return
        await interaction.response.edit_message(content="🧙‍♂️ **Mode Solo** ! Choisissez votre nom :", view=SetupMatchView(self.author, is_solo=True))
    @discord.ui.button(label="Mode Duel", style=discord.ButtonStyle.success)
    async def duel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author: return
        await interaction.response.edit_message(content="🤝 **Duel** : Tapez `!duel @nom` pour défier quelqu'un !", view=None)

class SetupMatchView(discord.ui.View):
    def __init__(self, j1, j2=None, is_solo=False):
        super().__init__(timeout=120)
        self.j1, self.j2_id, self.is_solo = j1, (j2.id if j2 else "CPU"), is_solo
        self.names = {j1.id: None, self.j2_id: "Équipe adverse" if is_solo else None}
    @discord.ui.button(label="Joueur 1 : Nom", style=discord.ButtonStyle.secondary)
    async def set_j1(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id == self.j1.id: await interaction.response.send_modal(NameModal(1, self))
    @discord.ui.button(label="Joueur 2 : Nom", style=discord.ButtonStyle.secondary)
    async def set_j2(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_solo and interaction.user.id == self.j2_id: await interaction.response.send_modal(NameModal(2, self))
    async def check_start(self, channel):
        if all(v is not None for v in self.names.values()):
            self.stop()
            await MatchView(self.j1, self.j2_id, self.names, self.is_solo).lancer_tour(channel)

# --- COMMANDES ---
@bot.command()
async def match(ctx):
    await ctx.send("🧙‍♂️ Bienvenue au Quickdditch !", view=StartMenuView(ctx.author))

@bot.command()
async def duel(ctx, adversaire: discord.Member):
    if not adversaire.bot and adversaire != ctx.author:
        await ctx.send(f"🏟️ Duel lancé !", view=SetupMatchView(ctx.author, adversaire))

@bot.command()
async def helpquickdditch(ctx):
    await ctx.send("🏟️ `!match` : Jouer | `!reglesquickdditch` : Règles")

@bot.command()
async def reglesquickdditch(ctx):
    await ctx.send("📜 6 tours de dés tactiques + duel final au dé 100 pour le Vif d'Or (+50 pts) !")

@bot.event
async def on_ready(): print(f"✅ Arbitre Quickdditch prêt !")

keep_alive()
bot.run(os.environ['DISCORD_TOKEN'])
