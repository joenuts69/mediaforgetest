import asyncio
import glob
import io
import os
import typing

import nextcord as discord
from nextcord.ext import commands

import config
import database
import heartbeat
import improcessing
import renderpool
from clogs import logger
from cog_other import showcog
# from main import renderpool, bot, database.db, quote
from mainutils import number_range, imagesearch, saveurls, fetch, quote
from tempfiles import TempFileSession


class Debug(commands.Cog, name="Owner Only", command_attrs=dict(hidden=True)):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["segfault", "segmentationfault"])
    @commands.is_owner()
    async def sigsegv(self, ctx, ftype: typing.Literal["overflow", "oskill", "ctypes"] = "oskill"):
        """
        cause the main process to segfault. used for debugging purposes. seems it wont kill child processes.
        """
        if ftype == "overflow":
            # https://codegolf.stackexchange.com/a/62613
            exec('()' * 7 ** 6)
        elif ftype == "oskill":
            os.kill(os.getpid(), 11)
        elif ftype == "ctypes":
            import ctypes
            ctypes.string_at(0)
        else:
            await ctx.reply("unknown segfault causer.")

    @commands.command()
    @commands.is_owner()
    async def rangetest(self, ctx, arg: number_range(-1.5, 1.5)):
        await ctx.reply(arg)

    @commands.command()
    @commands.is_owner()
    async def replytonothing(self, ctx):
        await ctx.message.delete()
        await ctx.reply("test")

    @commands.command()
    @commands.is_owner()
    async def listmesage(self, ctx):
        async for m in ctx.channel.history(limit=50, before=ctx.message):
            logger.debug(m.type)

    @commands.command()
    @commands.is_owner()
    async def reply(self, ctx):
        await ctx.reply("test")

    @commands.command()
    @commands.is_owner()
    async def say(self, ctx, channel: typing.Optional[typing.Union[discord.TextChannel, discord.User]], *, msg):
        if not channel:
            channel = ctx.channel
        if ctx.channel.permissions_for(ctx.me).manage_messages:
            asyncio.create_task(ctx.message.delete())
        asyncio.create_task(channel.send(msg))

    @commands.command(hidden=True)
    @commands.is_owner()
    async def error(self, _):
        """
        Raise an error
        """
        raise Exception("Exception raised by $error command")

    @commands.command(hidden=True)
    @commands.is_owner()
    async def errorafter5(self, _):
        """
        Raise an error after 5 seconds
        """
        await asyncio.sleep(5)
        raise Exception("Exception raised by $error command")

    @commands.command(hidden=True)
    @commands.is_owner()
    async def errorcmd(self, _):
        """
        Raise an error from the commandline
        """
        await improcessing.run_command("ffmpeg", "-hide_banner", "dsfasdfsadfasdfasdf")

    @commands.command(hidden=True)
    @commands.is_owner()
    async def cleartemp(self, ctx):
        """
        Clear the /temp folder
        """
        l = len(glob.glob('temp/*'))
        for f in glob.glob('temp/*'):
            os.remove(f)
        await ctx.send(f"✅ Removed {l} files.")

    @commands.command(hidden=True, aliases=["verify", "check", "watermark", "integrity", "verifywatermark"])
    @commands.is_owner()
    async def checkwatermark(self, ctx):
        """
        searches for MediaForge metadata
        """
        with TempFileSession() as tempfilesession:
            file = await imagesearch(ctx, 1)
            if file:
                file = await saveurls(file)
                result = await improcessing.checkwatermark(file[0])
                if result:
                    await ctx.reply(f"{config.emojis['working']} This file was made by MediaForge.")
                else:
                    await ctx.reply(
                        f"{config.emojis['x']} This file does not appear to have been made by MediaForge.")
            else:
                await ctx.send(f"{config.emojis['x']} No file found.")

    @commands.command(hidden=True, aliases=["stop", "close", "die", "kill", "murder", "death"])
    @commands.is_owner()
    async def shutdown(self, ctx):
        """
        Shut down the bot
        """
        await ctx.send(f"{config.emojis['check']} Shutting Down...")
        logger.critical("Shutting Down...")
        await renderpool.renderpool.shutdown()
        if heartbeat.heartbeat_active:
            heartbeat.heartbeatprocess.terminate()
        await self.bot.close()
        await self.bot.loop.shutdown_asyncgens()
        await self.bot.loop.shutdown_default_executor()
        self.bot.loop.stop()
        self.bot.loop.close()

    @commands.command()
    @commands.is_owner()
    async def generate_command_list(self, ctx):
        out = ""
        for cog in self.bot.cogs.values():
            if not showcog(cog):
                continue
            out += f"### {cog.qualified_name}\n"
            for command in sorted(cog.get_commands(), key=lambda x: x.name):
                if not command.hidden:
                    out += f"- **${command.name}**: {command.short_doc}\n"
        with io.StringIO() as buf:
            buf.write(out)
            buf.seek(0)
            await ctx.reply(file=discord.File(buf, filename="commands.md"))

    @commands.command(aliases=["beat"])
    @commands.is_owner()
    async def heartbeat(self, ctx):
        if hasattr(config, "heartbeaturl"):
            await fetch(config.heartbeaturl)
            await ctx.reply("Successfully sent heartbeat.")
        else:
            await ctx.reply("No heartbeat URL set in config.")

    @commands.command()
    @commands.is_owner()
    async def ban(self, ctx, user: discord.User, *, reason: str = ""):
        async with database.db.execute("SELECT count(*) from bans WHERE user=?", (user.id,)) as cur:
            if (await cur.fetchone())[0] > 0:  # check if ban exists
                await ctx.reply(f"{config.emojis['x']} {user.mention} is already banned.")
            else:
                await database.db.execute("INSERT INTO bans(user,banreason) values (?, ?)", (user.id, reason))
                await database.db.commit()
                await ctx.reply(f"{config.emojis['check']} Banned {user.mention}.")

    @commands.command()
    @commands.is_owner()
    async def unban(self, ctx, user: discord.User):
        cur = await database.db.execute("DELETE FROM bans WHERE user=?",
                                        (user.id,))
        await database.db.commit()
        if cur.rowcount > 0:
            await ctx.reply(f"{config.emojis['check']} Unbanned {user.mention}.")
        else:
            await ctx.reply(f"{config.emojis['x']} {user.mention} is not banned.")

    @commands.command()
    @commands.is_owner()
    async def quote(self, ctx, *, string):
        await ctx.reply(quote(string))
