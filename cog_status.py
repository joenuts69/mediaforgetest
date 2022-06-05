import datetime

import nextcord as discord
from nextcord.ext import commands, tasks

import config


class StatusCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.changestatus.start()

    def cog_unload(self):
        self.changestatus.cancel()

    @tasks.loop(seconds=60)
    async def changestatus(self):
        if datetime.datetime.now().month == 6:  # june (pride month)
            game = discord.Activity(
                name=f"I'm not too fond of gay people {len(self.bot.guilds)} servers{'' if len(self.bot.guilds) == 1 else 's'}! | "
                     f"{config.default_command_prefix}help",
                type=discord.ActivityType.playing)
        else:
            game = discord.Activity(
                name=f"with your media in {len(self.bot.guilds)} server{'' if len(self.bot.guilds) == 1 else 's'} | "
                     f"{config.default_command_prefix}help",
                type=discord.ActivityType.playing)
        await self.bot.change_presence(activity=game)

    @changestatus.before_loop
    async def before_printer(self):
        await self.bot.wait_until_ready()
