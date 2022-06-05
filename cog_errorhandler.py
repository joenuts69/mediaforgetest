import asyncio
import concurrent.futures
import datetime
import difflib
import io
import traceback
import urllib.parse

import nextcord as discord
import selenium.common
from aiohttp import client_exceptions as aiohttp_client_exceptions
from nextcord.ext import commands

import config
import improcessing
import renderpool as renderpoolmodule
from clogs import logger
from mainutils import now, prefix_function, get_full_class_name


class ErrorHandlerCog(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.antispambucket = {}

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, commanderror: commands.CommandError):
        async def dmauthor(*args, **kwargs):
            try:
                return await ctx.reply(*args, **kwargs)
            except discord.Forbidden:
                logger.warning(f"Reply to {ctx.message.id} and dm to {ctx.author.id} failed. Aborting.")

        async def reply(*args, **kwargs):
            try:
                if ctx.guild and not ctx.channel.permissions_for(ctx.me).send_messages:
                    logger.debug(f"No permissions to reply to {ctx.message.id}, trying to DM author.")
                    return await dmauthor(*args, **kwargs)
                return await ctx.reply(*args, **kwargs)
            except discord.Forbidden:
                logger.debug(f"Forbidden to reply to {ctx.message.id}, trying to DM author")
                return await dmauthor(*args, **kwargs)

        async def logandreply(message):
            if ctx.guild:
                ch = f"channel #{ctx.channel.name} ({ctx.channel.id}) in server {ctx.guild} ({ctx.guild.id})"
            else:
                ch = "DMs"
            logger.warning(f"Command '{ctx.message.content}' by "
                           f"@{ctx.message.author.name}#{ctx.message.author.discriminator} ({ctx.message.author.id}) "
                           f"in {ch} failed due to {message}.")
            await reply(message)

        global renderpool
        if isinstance(commanderror, concurrent.futures.process.BrokenProcessPool):
            renderpool = renderpoolmodule.initializerenderpool()
        errorstring = str(commanderror)
        if isinstance(commanderror, discord.Forbidden):
            await dmauthor(f"{config.emojis['x']} I don't have permissions to send messages in that channel.")
            logger.warning(commanderror)
        if isinstance(commanderror, discord.ext.commands.errors.CommandNotFound):
            # to prevent funny 429s, error cooldowns are only sent once before the cooldown is over.
            if ctx.author.id in self.antispambucket.keys():
                if self.antispambucket[ctx.author.id] > now():
                    logger.debug(f"Skipping error reply to {ctx.author} ({ctx.author.id}): {errorstring}")
                    return
            if ctx.message.content.strip().lower() in ["$w", "$wa", "$waifu", "$h", "$ha", "$husbando", "$wx", "$hx",
                                                       "$m", "$ma", "$marry", "$mx", "$g", "$tu", "$top", "$mmrk",
                                                       "$rolls"]:
                # this command is spammed so much, fuckn ignore it
                # https://mudae.fandom.com/wiki/List_of_Commands#.24waifu_.28.24w.29
                logger.debug(f"Ignoring {ctx.message.content}")
                return
            # remove prefix, remove excess args
            cmd = ctx.message.content[len(ctx.prefix):].split(' ')[0]
            allcmds = []
            for botcom in self.bot.commands:
                if not botcom.hidden:
                    allcmds.append(botcom.name)
                    allcmds += botcom.aliases
            prefix = await prefix_function(self.bot, ctx.message, True)
            match = difflib.get_close_matches(cmd, allcmds, n=1, cutoff=0)[0]
            err = f"{config.emojis['exclamation_question']} Command `{prefix}{cmd}` does not exist. " \
                  f"Did you mean **{prefix}{match}**?"
            if not (cmd.startswith("$") and all([i.isdecimal() or i in ".," for i in cmd.replace("$", "")])):
                # exclude just numbers/decimals, it annoys people
                await logandreply(err)
                self.antispambucket[ctx.author.id] = now() + config.cooldown
        elif isinstance(commanderror, discord.ext.commands.errors.NotOwner):
            err = f"{config.emojis['x']} You are not authorized to use this command."
            await logandreply(err)
        elif isinstance(commanderror, discord.ext.commands.errors.CommandOnCooldown):
            # to prevent funny 429s, error cooldowns are only sent once before the cooldown is over.
            if ctx.author.id in self.antispambucket.keys():
                if self.antispambucket[ctx.author.id] > now():
                    logger.debug(f"Skipping error reply to {ctx.author} ({ctx.author.id}): {errorstring}")
                    return
            err = f"{config.emojis['clock']} {errorstring}"
            await logandreply(err)
            self.antispambucket[ctx.author.id] = now() + commanderror.retry_after
        elif isinstance(commanderror, discord.ext.commands.errors.UserInputError):
            err = f"{config.emojis['warning']} {errorstring}"
            if ctx.command:
                prefix = await prefix_function(self.bot, ctx.message, True)
                err += f" Run `{prefix}help {ctx.command}` to see how to use this command."
            await logandreply(err)
        elif isinstance(commanderror, discord.ext.commands.errors.NoPrivateMessage):
            err = f"{config.emojis['warning']} {errorstring}"
            await logandreply(err)
        elif isinstance(commanderror, discord.ext.commands.errors.CheckFailure):
            err = f"{config.emojis['x']} {errorstring}"
            await logandreply(err)
        elif isinstance(commanderror, discord.ext.commands.errors.CommandInvokeError) and \
                isinstance(commanderror.original, improcessing.NonBugError):
            await logandreply(f"{config.emojis['2exclamation']} {str(commanderror.original)[:1000]}")
        else:
            if isinstance(commanderror, discord.ext.commands.errors.CommandInvokeError):
                commanderror = commanderror.original
            logger.error(commanderror, exc_info=(type(commanderror), commanderror, commanderror.__traceback__))

            is_hosting_issue = isinstance(commanderror, (aiohttp_client_exceptions.ClientOSError,
                                                         aiohttp_client_exceptions.ServerDisconnectedError,
                                                         asyncio.exceptions.TimeoutError,
                                                         concurrent.futures.process.BrokenProcessPool,
                                                         selenium.common.exceptions.TimeoutException))

            if is_hosting_issue:
                desc = "If this error keeps occurring, report this with the attached traceback file to the GitHub."
            else:
                desc = "Please report this error with the attached traceback file to the GitHub."
            embed = discord.Embed(color=0xed1c24, description=desc)
            embed.add_field(name=f"{config.emojis['2exclamation']} Report Issue to GitHub",
                            value=f"[Create New Issue](https://github.com/HexCodeFFF/mediaforge"
                                  f"/issues/new?labels=bug&template=bug_report.md&title"
                                  f"={urllib.parse.quote(str(commanderror), safe='')[:848]})\n[View Issu"
                                  f"es](https://github.com/HexCodeFFF/mediaforge/issues)")
            with io.BytesIO() as buf:
                trheader = f"DATETIME:{datetime.datetime.now()}\nCOMMAND:{ctx.message.content}\nTRACEBACK:\n"
                buf.write(bytes(trheader + ''.join(
                    traceback.format_exception(etype=type(commanderror), value=commanderror,
                                               tb=commanderror.__traceback__)), encoding='utf8'))
                buf.seek(0)
                if is_hosting_issue:
                    errtxt = f"{config.emojis['2exclamation']} Your command encountered an error due to limited " \
                             f"resources on the server. If you would like to support the upkeep of MediaForge and " \
                             f"getting a better server, support me on Ko-Fi here: <https://ko-fi.com/reticivis>"
                else:
                    errtxt = (f"{config.emojis['2exclamation']} `{get_full_class_name(commanderror)}: "
                              f"{errorstring}`")[:2000]
                await reply(errtxt, file=discord.File(buf, filename="traceback.txt"), embed=embed)
