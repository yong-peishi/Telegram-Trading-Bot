import os
import sqlite3
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
import binance_trader

# Load environment variables
load_dotenv()

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect('user_credentials.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS credentials
                 (user_id INTEGER PRIMARY KEY, username TEXT, password TEXT)''')
    conn.commit()
    conn.close()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Welcome! Use /setcredentials to set your username and password. Use /viewusername to see your stored username')

#username = apikey, password = secret
async def set_credentials(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Please enter your username and password separated by a space.')
    context.user_data['expecting_credentials'] = True

async def handle_credentials(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get('expecting_credentials'):
        try:
            username, password = update.message.text.split()
            user_id = update.effective_user.id
            
            conn = sqlite3.connect('user_credentials.db')
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO credentials (user_id, username, password) VALUES (?, ?, ?)",
                      (user_id, username, password))
            conn.commit()
            conn.close()
            
            await update.message.reply_text('Credentials stored successfully!')
        except ValueError:
            await update.message.reply_text('Invalid format. Please provide username and password separated by a space.')
        finally:
            context.user_data['expecting_credentials'] = False
    else:
        await update.message.reply_text('Use /setcredentials to set your username and password.')

async def view_username(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    
    conn = sqlite3.connect('user_credentials.db')
    c = conn.cursor()
    c.execute("SELECT username FROM credentials WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    
    if result:
        await update.message.reply_text(f'Your stored username is: {result[0]}')
    else:
        await update.message.reply_text('You haven\'t set your credentials yet. Use /setcredentials to do so.')

async def change_credentials(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('What would you like to change? Reply with "username" or "password".')
    context.user_data['changing_credentials'] = True
    context.user_data['change_step'] = 'choose'

async def handle_credential_change(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get('changing_credentials'):
        user_id = update.effective_user.id
        
        if context.user_data['change_step'] == 'choose':
            choice = update.message.text.lower()
            if choice in ['username', 'password']:
                context.user_data['change_type'] = choice
                context.user_data['change_step'] = 'input'
                await update.message.reply_text(f'Please enter your new {choice}:')
            else:
                await update.message.reply_text('Invalid choice. Please reply with "username" or "password".')
                return
        
        elif context.user_data['change_step'] == 'input':
            new_value = update.message.text
            change_type = context.user_data['change_type']
            
            conn = sqlite3.connect('user_credentials.db')
            c = conn.cursor()
            c.execute(f"UPDATE credentials SET {change_type} = ? WHERE user_id = ?", (new_value, user_id))
            conn.commit()
            conn.close()
            
            await update.message.reply_text(f'Your {change_type} has been updated successfully!')
            context.user_data['changing_credentials'] = False
            context.user_data['change_step'] = None
            context.user_data['change_type'] = None
    else:
        await update.message.reply_text('Use /changecredentials to change your username or password.')

#Binance Trading
async def execute_binance_trade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    
    conn = sqlite3.connect('user_credentials.db')
    c = conn.cursor()
    c.execute("SELECT username, password FROM credentials WHERE user_id = ?", (user_id,)) #username = apikey, password = secret
    result = c.fetchone()
    conn.close()
    
    if result:
        api_key, api_secret = result
        client = binance_trader.init_binance_client(api_key, api_secret)
        
        if client:
            await update.message.reply_text('Binance client initialized. Please enter trade details in the format: SYMBOL SIDE QUANTITY (e.g., BTCUSDT BUY 0.001)')
            context.user_data['expecting_trade'] = True
        else:
            await update.message.reply_text('Failed to initialize Binance client. Please check your API key and secret.')
    else:
        await update.message.reply_text('You haven\'t set your credentials yet. Use /setcredentials to do so.')

async def handle_trade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get('expecting_trade'):
        try:
            symbol, side, quantity = update.message.text.split()
            
            user_id = update.effective_user.id
            conn = sqlite3.connect('user_credentials.db')
            c = conn.cursor()
            c.execute("SELECT username, password FROM credentials WHERE user_id = ?", (user_id,))
            result = c.fetchone()
            conn.close()
            
            if result:
                api_key, api_secret = result
                client = binance_trader.init_binance_client(api_key, api_secret)
                
                if client:
                    trade_result = binance_trader.execute_trade(client, symbol, side, quantity)
                    await update.message.reply_text(trade_result)
                else:
                    await update.message.reply_text('Failed to initialize Binance client. Please check your API key and secret.')
            else:
                await update.message.reply_text('You haven\'t set your credentials yet. Use /setcredentials to do so.')
        except ValueError:
            await update.message.reply_text('Invalid format. Please provide SYMBOL SIDE QUANTITY (e.g., BTCUSDT BUY 0.001)')
        finally:
            context.user_data['expecting_trade'] = False
    else:
        await update.message.reply_text('Use /trade to execute a Binance trade.')

def main() -> None:
    # Initialize the database
    init_db()

    # Create the Application and pass it your bot's token
    application = Application.builder().token(os.getenv('TELEGRAM_BOT_TOKEN')).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("setcredentials", set_credentials))
    application.add_handler(CommandHandler("viewusername",view_username))
    application.add_handler(CommandHandler("changecredentials", change_credentials))
    application.add_handler(CommandHandler("trade", execute_binance_trade))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_trade))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_credentials))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_credential_change))

    # Run the bot until the user presses Ctrl-C
    application.run_polling()

if __name__ == '__main__':
    main()