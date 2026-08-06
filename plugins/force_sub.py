import asyncio
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
from helper.helper_func import is_bot_admin

#===============================================================#

async def fsub(client, query):
    # Create a formatted list of channels with names and IDs
    if client.fsub_dict:
        channel_list = []
        for channel_id, channel_data in client.fsub_dict.items():
            channel_name = channel_data[0] if channel_data and len(channel_data) > 0 else "Unknown"
            request_status = "Request: ✅" if channel_data[2] else "Request: ❌"
            timer_status = f"Timer: {channel_data[3]}m" if channel_data[3] > 0 else "Timer: ∞"
            channel_list.append(f"• `{channel_name}` (`{channel_id}`) - {request_status}, {timer_status}")
        
        channels_display = "\n".join(channel_list)
    else:
        channels_display = "_No force subscription channels configured_"

    folder = getattr(client, 'fsub_folder', None) or {}
    if folder.get('link'):
        folder_display = f"• `{folder['link']}`\n  Channels: `{', '.join(str(c) for c in folder.get('channels', []))}`"
    else:
        folder_display = "_No force subscription folder configured_"

    msg = f"""<blockquote>**Force Subscription Settings:**</blockquote>
**Configured Channels:**
{channels_display}

**Configured Folder:**
{folder_display}

__Use the appropriate button below to add or remove a force subscription channel/folder based on your needs!__
"""
    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton('ᴀᴅᴅ ᴄʜᴀɴɴᴇʟ', 'add_fsub'), InlineKeyboardButton('ʀᴇᴍᴏᴠᴇ ᴄʜᴀɴɴᴇʟ', 'rm_fsub')],
        [InlineKeyboardButton('ᴀᴅᴅ ꜰᴏʟᴅᴇʀ', 'add_folder'), InlineKeyboardButton('ʀᴇᴍᴏᴠᴇ ꜰᴏʟᴅᴇʀ', 'rm_folder')],
        [InlineKeyboardButton('◂ ʙᴀᴄᴋ', 'settings')]]
    )
    await query.message.edit_text(msg, reply_markup=reply_markup)
    return

#===============================================================#

@Client.on_callback_query(filters.regex('^add_fsub$'))
async def add_fsub(client: Client, query: CallbackQuery):
    await query.answer()
    ask_channel_info = await client.ask(query.from_user.id, "Send channel id(negative integer value), request boolean(yes/no/true/false), timers(integer without decimal)(to enable it keep it greator than 0 otherwise the invite link will not have any timer to invalidate it) seperated by a space in the next 60 seconds!\n<blockquote expandable>Eg: `-10089479289 yes 5`\n\n__It means `-10089479289` is the force sub channel id, `yes` means to enable request it means the link will be request link and only after user sends request to the channel bot will work for that user even if you do not accept his request or user is not a member, `5` means timer in minutes aftetr 5 minutes the invite link will be expired.__</blockquote>", filters=filters.text, timeout=60)
    try:
        channel_info = ask_channel_info.text.split()
        channel_id, request, timer = channel_info
        channel_id = int(channel_id)
        if channel_id in client.fsub_dict.keys():
            return await ask_channel_info.reply("**This channel id already exists in force sub list, remove it to change it's configuration!!**")
        val, res = await is_bot_admin(client, channel_id)
        if not val:
            return await ask_channel_info.reply(f"**Error:** `{res}`")
        if request.lower() in ('true', 'on', 'yes'):
            request = True
        elif request.lower() in ('false', 'off', 'no'):
            request = False
        else:
            raise Exception("Invalid request value or type.")
        if timer.isdigit():
            timer = int(timer)
        else:
            raise Exception("Timer is not a valid integer.")
        chat = await client.get_chat(channel_id)
        name = chat.title
        if timer > 0:
            client.fsub_dict[channel_id] = [name, None, request, timer]
        else:
            chat_link = await client.create_chat_invite_link(channel_id, creates_join_request=request)
            link = chat_link.invite_link
            client.fsub_dict[channel_id] = [name, link, request, timer]
        
        # Update req_channels list if request is enabled
        if request and channel_id not in client.req_channels:
            client.req_channels.append(channel_id)
            await client.mongodb.set_channels(client.req_channels)
        
        # Save to database for persistence across bot restarts
        await client.mongodb.add_fsub_channel(channel_id, client.fsub_dict[channel_id])
        
        await fsub(client, query)
        return await ask_channel_info.reply(f"__Channel with name: `{name.strip()}` is added as a force sub channel!!__")
    except Exception as e:
        return await ask_channel_info.reply(f"**Error:** `{e}`")
    
#===============================================================#

@Client.on_callback_query(filters.regex('^rm_fsub$'))
async def rm_fsub(client: Client, query: CallbackQuery):
    await query.answer()
    ask_channel_info = await client.ask(query.from_user.id, "Send channel id(negative integer value) in the next 60 seconds!", filters=filters.text, timeout=60)
    try:
        channel_id = int(ask_channel_info.text)
        if channel_id not in client.fsub_dict.keys():
            return await ask_channel_info.reply("**This channel id is not in force sub list!**")
        
        # Check if it was a request channel and remove from req_channels
        if channel_id in client.req_channels:
            client.req_channels.remove(channel_id)
            await client.mongodb.set_channels(client.req_channels)
        
        client.fsub_dict.pop(channel_id)
        
        # Remove from database for persistence across bot restarts
        await client.mongodb.remove_fsub_channel(channel_id)
        
        await fsub(client, query)
        return await ask_channel_info.reply(f"__Channel with id: `{channel_id}` has been removed as a force sub channel!!__")
    except Exception as e:
        return await ask_channel_info.reply(f"**Error:** `{e}`")

#===============================================================#

@Client.on_callback_query(filters.regex('^add_folder$'))
async def add_folder(client: Client, query: CallbackQuery):
    await query.answer()
    user_id = query.from_user.id

    # Step 1: just the folder link — no need to type any channel ids by hand.
    try:
        ask_link = await client.ask(
            user_id,
            "Send the **Telegram folder invite link** (looks like `https://t.me/addlist/xxxxxxxx`) in the next 60 seconds!\n"
            "<blockquote expandable>__Create it yourself first: Telegram Settings > Chat Folders > (your folder) > "
            "Share, then copy the link and paste it here.__</blockquote>",
            filters=filters.text,
            timeout=60
        )
    except asyncio.TimeoutError:
        return

    link = ask_link.text.strip()
    if "/addlist/" not in link:
        return await ask_link.reply("**Error:** `That doesn't look like a folder invite link (it must contain /addlist/).`")

    # Step 2: instead of typing channel ids, just forward one message from each
    # channel that's inside the folder — the bot reads the id off the forward.
    info_msg = await ask_link.reply(
        "__Now **forward one message from each channel** that's inside that folder — one at a time. "
        "The bot must already be an admin in each of them.\n\n"
        "Send /done once you've forwarded all of them, or /cancel to abort.__"
    )

    channel_ids = []
    while True:
        try:
            reply = await client.listen(user_id=user_id, filters=filters.text | filters.forwarded, timeout=180)
        except asyncio.TimeoutError:
            return await info_msg.reply("**Error:** `Timed out waiting for a forwarded message.`")

        text = (reply.text or "").strip().lower()
        if text == "/cancel":
            return await reply.reply("**Folder setup cancelled.**")
        if text == "/done":
            break

        fwd_chat = getattr(reply, "forward_from_chat", None)
        if not fwd_chat:
            await reply.reply("__That wasn't a forwarded channel message. Forward a message from the channel, or send /done to finish.__")
            continue

        channel_id = fwd_chat.id
        if channel_id in channel_ids:
            await reply.reply(f"__`{fwd_chat.title}` was already added, forward the next channel or send /done.__")
            continue

        if channel_id not in client.fsub_dict:
            val, res = await is_bot_admin(client, channel_id)
            if not val:
                await reply.reply(f"**Error:** `{res}` — `{fwd_chat.title}` was skipped. Forward the next one or /done.")
                continue
            client.fsub_dict[channel_id] = [fwd_chat.title, None, False, 0]
            await client.mongodb.add_fsub_channel(channel_id, client.fsub_dict[channel_id])

        channel_ids.append(channel_id)
        await reply.reply(f"__Added `{fwd_chat.title}`. Forward the next channel in the folder, or send /done.__")

    if not channel_ids:
        return await info_msg.reply("**Error:** `No channels were added, folder was not saved.`")

    client.fsub_folder = {"link": link, "channels": channel_ids}
    await client.mongodb.set_fsub_folder(client.fsub_folder)

    await fsub(client, query)
    return await info_msg.reply(
        f"__Force sub folder set with `{len(channel_ids)}` channel(s)! Users must join the folder link to unlock files.__"
    )

#===============================================================#

@Client.on_callback_query(filters.regex('^rm_folder$'))
async def rm_folder(client: Client, query: CallbackQuery):
    if not getattr(client, 'fsub_folder', None) or not client.fsub_folder.get('link'):
        return await query.answer("No force sub folder is currently configured!", show_alert=True)
    await query.answer()
    client.fsub_folder = {}
    await client.mongodb.remove_fsub_folder()
    await fsub(client, query)
    return await query.message.reply("__The force sub folder has been removed!!__")
