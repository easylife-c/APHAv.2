import discord
import os
import json
import time
from plant_api_Test import identify_plant
from main_test import get_tank_status, activate_pump, auto_water_loop, save_tank_levels, tank_levels, compute_fertilizer , initialize_tanks, reset_tank
from discord.ui import View, Button
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
import pytz
import asyncio
from discord.ext import commands

# Configurations
TOKEN = "your discord token"
CHANNEL_ID = 951778173182431245
TIMEZONE = pytz.timezone("Asia/Bangkok")
MAX_LEN = 2000

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
scheduler = AsyncIOScheduler(timezone=TIMEZONE)

pending_users = {}
FERTILIZER_LOG_FILE = "fertilizer_log.json"
FERTILIZER_COOLDOWN_HOURS = 0.1
NUTRIENT_MAP = {
    "NITROGEN": "N",
    "PHOSPHORUS": "P",
    "POTASSIUM": "K",
    "N": "N",
    "P": "P",
    "K": "K"
}



# ===== Fertilizer log functions =====
def load_fertilizer_log():
    try:
        with open(FERTILIZER_LOG_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_fertilizer_log(log_data):
    with open(FERTILIZER_LOG_FILE, "w") as f:
        json.dump(log_data, f, indent=2)

fertilizer_log = load_fertilizer_log()

# ===== UI Components =====
class ConfirmApplyView(discord.ui.View):
    def __init__(self, user_id, species, height, width, deficiencies):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.data = {
            "species": species,
            "height": height,
            "width": width,
            "deficiencies": deficiencies
        }

    @discord.ui.button(label="✅ Confirm Apply", style=discord.ButtonStyle.success)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(" Not your confirmation", ephemeral=True)
            return

    # Defer the response so Discord doesn't time out
        await interaction.response.defer(thinking=True)

    # Run fertilizer logic
        await apply_fertilizer_logic(interaction.channel, interaction.user, self.data)

    # Send a follow-up message instead of edit_original_response
        await interaction.followup.send("💧 Fertilizer applied!", ephemeral=False)


    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.danger)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="🚫 Fertilizer application cancelled.", view=None)

class ReminderView(discord.ui.View):
    def __init__(self, original_time: datetime):
        super().__init__(timeout=None)
        self.original_time = original_time

    @discord.ui.button(label="📤 Upload Photo", style=discord.ButtonStyle.success, custom_id="upload_photo")
    async def upload_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("📷 Please upload your plant photo here!", ephemeral=True)

    @discord.ui.button(label="⏭️ Skip to Next Hour", style=discord.ButtonStyle.secondary, custom_id="skip_hour")
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        next_time = datetime.now(TIMEZONE) + timedelta(hours=1)
        scheduler.add_job(send_reminder, "date", run_date=next_time)
        await interaction.response.send_message(
            f"⏭️ Reminder rescheduled to {next_time.strftime('%H:%M')}", ephemeral=True

        )

class GrowthStageView(View):
    def __init__(self, user, data, ctx_or_channel):
        super().__init__(timeout=60)  # 1 minute timeout
        self.user = user
        self.data = data
        self.ctx_or_channel = ctx_or_channel

    async def handle_stage(self, interaction, stage):
        if interaction.user != self.user:
            await interaction.response.send_message("❌ This button isn’t for you!", ephemeral=True)
            return

        self.data["growth_stage"] = stage
        await interaction.response.send_message(f"🌱 Growth stage set to **{stage}**. Applying fertilizer...", ephemeral=True)

        # Run fertilizer logic with stage
        await apply_fertilizer_logic(self.ctx_or_channel, self.user, self.data)

        # Disable buttons after click
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)

    @discord.ui.button(label="Seedling 🌱", style=discord.ButtonStyle.primary)
    async def seedling(self, interaction, button):
        await self.handle_stage(interaction, "seedling")

    @discord.ui.button(label="Vegetative 🌿", style=discord.ButtonStyle.success)
    async def vegetative(self, interaction, button):
        await self.handle_stage(interaction, "vegetative")

    @discord.ui.button(label="Flowering 🌸", style=discord.ButtonStyle.danger)
    async def flowering(self, interaction, button):
        await self.handle_stage(interaction, "flowering")

    @discord.ui.button(label="Fruiting 🍇", style=discord.ButtonStyle.secondary)
    async def fruiting(self, interaction, button):
        await self.handle_stage(interaction, "fruiting")


# ===== Events =====
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    scheduler.add_job(send_reminder, "cron", hour=8, minute=30)
    scheduler.start()
    # Start auto watering loop
    asyncio.create_task(auto_water_loop())

    channel_id = 951778173182431245 
    channel = bot.get_channel(channel_id)

    if channel:
        msg = (
            "🤖 **Plant Care Bot is online!**\n\n"
            "Here are the available commands:\n"
            "• `!tanks` → Show current fertilizer tank levels\n"
            "• `!refill <nutrient> <amount>` → Add nutrients to a tank (ml)\n"
            "• `!reset_tank_cmd <nutrient> [level]` → Reset a single tank\n"
            "• `!init_tanks [level]` → Reset all tanks\n"
            "• Upload a plant photo → Analyze & fertilize\n"
            "• Soil moisture is auto-checked → water pump runs if dry\n"
            "• `!help` → Show this list anytime\n"
        )
        await channel.send(msg)
        print("[DEBUG] Startup help message sent.")
    else:
        print(f"[ERROR] Could not find channel with ID {channel_id}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.attachments:
        for attachment in message.attachments:
            if attachment.filename.lower().endswith((".jpg", ".jpeg", ".png")):
                await message.channel.send("🧠 Analyzing image...")
                temp_filename = f"temp_{attachment.filename}"
                try:
                    await attachment.save(temp_filename)
                    result = identify_plant(temp_filename)
                    os.remove(temp_filename)

                    await message.channel.send(result["display"])

                    if result.get("deficiencies") and result.get("height") and result.get("width"):
                        data = {
                            "species": result["species"],
                            "height": result["height"],
                            "width": result["width"],
                            "deficiencies": result["deficiencies"]
                        }
                        view = GrowthStageView(message.author, data, message.channel)
                        await message.channel.send("🌱 Please select the plant’s growth stage:", view=view)


                except Exception as e:
                    await message.channel.send(f"❌ Error processing image: {e}")

    await bot.process_commands(message)

# ===== Commands =====
@bot.command()
async def submit(ctx, species: str, height: float, width: float, *deficiencies):
    if not deficiencies:
        await ctx.send("Provide deficiencies. Example: `!submit mango 1.2 0.8 N P`")
        return
    pending_users[ctx.author.id] = {
        "species": species,
        "height": height,
        "width": width,
        "deficiencies": deficiencies
    }
    await ctx.send("📥 Data saved. Type `!applyfertilizer` to apply fertilizer.")

@bot.command()
async def applyfertilizer(ctx):
    if ctx.author.id not in pending_users:
        await ctx.send(" No pending plant data.")
        return
    await apply_fertilizer_logic(ctx, ctx.author, pending_users.pop(ctx.author.id))

@bot.command()
async def tank(ctx):
    status = get_tank_status()
    lines = [f" {nutrient}: {amount:.2f} ml remaining" for nutrient, amount in status.items()]
    await ctx.send("\n".join(lines))

@bot.command()
async def test(ctx):
    await ctx.send(f"Channel ID is: {ctx.channel.id}")

# ===== Reminder Function =====
async def send_reminder():
    now = datetime.now(TIMEZONE)
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        view = ReminderView(original_time=now)
        await channel.send("📸 Time to take a photo of your plant", view=view)
        print("Reminder sent")
    else:
        print(" Channel not found.")

# ===== Fertilizer Logic =====
async def apply_fertilizer_logic(ctx_or_channel, user, data):
    user_id = str(user.id)
    now = datetime.utcnow()
    fertilizer_log.setdefault(user_id, {})

    results = compute_fertilizer(
    data["species"],
    data["height"],
    data["width"],
    data["deficiencies"],
    data.get("growth_stage", "vegetative")
)


    print("DEBUG: Data received ->", data)
    print("DEBUG: Fertilizer results ->", results)

    msg_lines = []
    for r in results:
        original = r["nutrient"].upper()
        nutrient = NUTRIENT_MAP.get(original)

        if not nutrient:
            msg_lines.append(f"Unknown nutrient: {original}")
            continue

        last_time_str = fertilizer_log[user_id].get(nutrient)
        if last_time_str:
            last_time = datetime.fromisoformat(last_time_str)
            time_since = (now - last_time).total_seconds()
            if time_since < FERTILIZER_COOLDOWN_HOURS * 1:
                hours_left = round((FERTILIZER_COOLDOWN_HOURS * 1 - time_since) / 3600, 1)
                msg_lines.append(f"{nutrient}: Applied recently. Try again in {hours_left}h.")
                continue

        # ✅ FIX: pass amount_ml instead of pump_time_sec
        success = activate_pump(nutrient, r["amount_ml"])
        if success:
            status = get_tank_status()
            msg_lines.append(f"{nutrient}: Applied {r['amount_ml']}ml. Remaining: {status[nutrient]}ml")
            fertilizer_log[user_id][nutrient] = now.isoformat()
        else:
            msg_lines.append(f"❌ {nutrient}: Not enough in tank!")

    save_fertilizer_log(fertilizer_log)
    if msg_lines:
        await ctx_or_channel.send("\n".join(msg_lines))
    else:
    # Clarify WHY nothing happened
        if not data.get("deficiencies"):
            await ctx_or_channel.send("🌿 No deficiencies detected — no fertilizer needed.")
        else:
            await ctx_or_channel.send("All nutrients skipped (cooldown active or unknown nutrient codes).")


@bot.command()
async def refill(ctx, nutrient: str, amount: float):
    nutrient = nutrient.upper()
    if nutrient not in tank_levels:
        await ctx.send(f"Invalid nutrient: `{nutrient}`. Choose from: {', '.join(tank_levels.keys())}")
        return

    if amount <= 0:
        await ctx.send("Refill amount must be greater than 0.")
        return

    tank_levels[nutrient] += amount
    save_tank_levels()
    await ctx.send(f"🔄 {nutrient} tank refilled by {amount}ml.\n💧 New level: {tank_levels[nutrient]:.2f}ml")

@bot.command()
async def init_tanks(ctx, level: float = 1000):
    """Reset ALL tanks to a given level (default 1000 ml)."""
    new_levels = initialize_tanks(level)
    await ctx.send(f"🔄 Tanks reset: {new_levels}")


@bot.command()
async def reset_tank_cmd(ctx, nutrient: str, level: float = 1000):
    """Reset a single tank to a given level (default 1000 ml)."""
    nutrient = nutrient.upper()
    if reset_tank(nutrient, level):
        await ctx.send(f"🔄 {nutrient} tank reset to {level} ml.")
    else:
        await ctx.send(f"Unknown nutrient: {nutrient}")

@bot.command()
async def tanks(ctx):
    """Show current fertilizer tank levels."""
    
    levels = get_tank_status()
    msg = "**Tank Levels**\n"
    for nutrient, level in levels.items():
        msg += f"🔹 {nutrient}: {level:.2f} ml\n"
    await ctx.send(msg)



# ===== Run Bot =====
bot.run(TOKEN)
