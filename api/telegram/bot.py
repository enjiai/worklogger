import logging
import os

from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, CallbackContext, Application, filters

from settings import settings

# Configure logging
logger = logging.getLogger(__name__)

# Use Telegram token from settings
BOT_TOKEN = settings.TELEGRAM_TOKEN
logger.info("Telegram bot token loaded from settings")


class CommunicationBot:
    def __init__(self, bot_token: str, trigger_handler, message_handler):
        self.bot_token = bot_token
        self.application = Application.builder().token(bot_token).build()
        self.trigger_handler = trigger_handler
        self.message_handler = message_handler

    async def run(self):
        # Register handlers
        await self.application.initialize()

        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.retrieve_message_from_human))
        self.application.add_handler(CommandHandler("chatid", self.print_chat_id))
        self.application.add_handler(CommandHandler("trigger", self.trigger))

        # Start the Bot
        print("Bot is starting")

        await self.application.start()
        print("Bot has started")
        # Run the bot until you send a stop signal
        await self.application.updater.start_polling()
        # await self.application.stop()
        print("Bot has stopped")

    async def print_chat_id(self, update: Update, context: CallbackContext):
        chat_id = update.message.chat_id
        print(f"Chat ID: {chat_id}")
        await update.message.reply_text(f"Your Chat ID is {chat_id}")

    async def trigger(self, update: Update, context: CallbackContext):
        print(f"message is {update.message.text}")
        response = await self.trigger_handler(update.message.text.removeprefix("/trigger ").strip("\n\t "))
        await update.message.reply_text(response)

    async def write_message_to_human(self, chat_id: int, message: str):
        await self.application.bot.send_message(chat_id=chat_id, text=message)

    async def retrieve_message_from_human(self, update: Update, context: CallbackContext):
        human_message = update.message.text
        print(f"Received message: {human_message}")
        response = await self.message_handler(human_message)
        await update.message.reply_text(response, reply_to_message_id=update.message.message_id)
