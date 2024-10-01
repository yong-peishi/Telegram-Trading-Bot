import re
import asyncio
import time
import os
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from dotenv import load_dotenv
import binance_trader

# Load environment variables
load_dotenv()

# Initialize SQLite database
def init_db():
    db_path = 'user_credentials.db'
    print(f'Using database file: {os.path.abspath(db_path)}')

    try:
        conn = sqlite3.connect('user_credentials.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS credentials
                 (user_id INTEGER PRIMARY KEY, username TEXT, password TEXT)''')
        conn.commit()
        conn.close()
        print('Database initialized successfully')
    except sqlite3.Error as e:
        print(f'An error occcurred: {e}')
    except Exception as e:
        print(f"Error: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    #await update.message.reply_text('Welcome! Use /setcredentials to set your username and password. Use /viewusername to see your stored username')
    # Create an inline keyboard with buttons for each command
    keyboard = [
        [InlineKeyboardButton("Set Credentials", callback_data='set_credentials')],
        [InlineKeyboardButton("View Username", callback_data='view_username')],
        [InlineKeyboardButton("Retrieve Balances", callback_data='retrieve_balance')],
        [InlineKeyboardButton("Execute Trade", callback_data='execute_binance_trade')],
        [InlineKeyboardButton("Execute TWAP", callback_data='execute_twap')],
        [InlineKeyboardButton("Retrieve Orders", callback_data='retrieve_orders')],
        [InlineKeyboardButton("Cancel Order", callback_data='cancel_order')],
        [InlineKeyboardButton("Retrieve Data", callback_data='retrieve_data')],
        [InlineKeyboardButton("USDT Margin History", callback_data='margin_history')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Send a message with the inline keyboard
    await update.message.reply_text(
        'Welcome! Choose an action:',
        reply_markup=reply_markup
    )

#username = apikey, password = secret
async def set_credentials(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()  # Acknowledge the button click
    await update.callback_query.message.reply_text('Please enter your username and password in this format: SET username password')
    context.user_data['expecting_credentials'] = True
    print(f'context.user_data: {context.user_data}')

async def handle_credentials(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(update.message.text)
    print("Handle credentials function called.")
    if context.user_data.get('expecting_credentials'):
        print("Expecting credentials flag is True.")
        try:
            message_text = update.message.text[len('SET '):]
            username, password = message_text.split()
            user_id = update.effective_user.id

            print(f'Received credentials: user_id={user_id}, username={username}, password={password}')  # Debug print

            conn = sqlite3.connect('user_credentials.db')
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO credentials (user_id, username, password) VALUES (?, ?, ?)",
                      (user_id, username, password))
            conn.commit()
            conn.close()

            await update.message.reply_text('Credentials stored successfully!')
        except ValueError:
            await update.message.reply_text('Invalid format. Please provide username and password in this format: SET username password.')
        finally:
            context.user_data['expecting_credentials'] = False
    else:
        await update.message.reply_text('Click on Set Credentials to set your username and password.')

async def view_username(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()  # Acknowledge the button click
    user_id = update.effective_user.id

    conn = sqlite3.connect('user_credentials.db')
    c = conn.cursor()
    c.execute("SELECT username FROM credentials WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()

    if result:
        await update.callback_query.message.reply_text(f'Your stored username is: {result[0]}')
    else:
        await update.callback_query.message.reply_text('You haven\'t set your credentials yet. Click on Set Credentias to do so.')

async def change_credentials(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()  # Acknowledge the button click
    await update.callback_query.message.reply_text('What would you like to change? Reply with "username" or "password".')
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
    await update.callback_query.answer()  # Acknowledge the button click
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
            await update.callback_query.message.reply_text('Please enter trade details in the format:\n' 'TRADE LAYER ORDERTYPE SYMBOL SIDE TIMEINFORCE MAXPRICE MINPRICE NUMBEROFORDERS QUANTITY\n' '(e.g., TRADE LAYER LIMIT BTCUSDT BUY GTC 63000 62000 10 20000) or\n' 'TRADE ORDERTYPE SYMBOL SIDE TIMEINFORCE PRICE QUANTITY\n' '(e.g., TRADE LIMIT BTCUSDT BUY GTC 65000 0.001) or\n' 'TRADE ORDERTYPE SYMBOL SIDE QUANTITY\n' '(e.g., TRADE MARKET BTCUSDT BUY 0.01)')
            context.user_data['expecting_trade'] = True
        else:
            await update.callback_query.message.reply_text('Failed to initialize Binance client. Please check your API key and secret.')
    else:
        await update.callback_query.message.reply_text('You haven\'t set your credentials yet. Use /setcredentials to do so.')

async def handle_trade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get('expecting_trade'):
        try:
            if update.message.text[:11]=='TRADE LIMIT':
                order='LIMIT'
                message_text = update.message.text[len('TRADE LIMIT '):]
                symbol, side, time_in_force, price, quantity = message_text.split()

            elif update.message.text[:17] =='TRADE LAYER LIMIT':
                order='LIMIT'
                message_text = update.message.text[len('TRADE LAYER LIMIT'):]
                symbol, side, time_in_force, maxprice, minprice, no_of_orders, quantity = message_text.split()
                maxprice = float(maxprice)
                minprice = float(minprice)
                priceadj = abs(maxprice - minprice) / (int(no_of_orders) - 1)
                prices = []
                order = 'LAYER'
                if side == 'BUY':
                    prices.append(maxprice)
                    price = maxprice
                    while price > minprice and len(prices) < (int(no_of_orders) - 1):
                        price = round(price - priceadj,2)
                        if price > minprice:
                            prices.append(price)
                        else:
                            break

                    if minprice not in prices:
                        prices.append(minprice)
                elif side == 'SELL':
                    prices.append(minprice)
                    price = minprice
                    while price < maxprice and len(prices) < (int(no_of_orders) - 1):
                        price = round(price + priceadj,2)
                        if price < maxprice:
                            prices.append(price)
                        else:
                            break

                    if maxprice not in prices:
                        prices.append(maxprice)

            elif update.message.text[:12]=='TRADE MARKET':
                order='MARKET'
                message_text = update.message.text[len('TRADE MARKET '):]
                symbol, side, quantity = message_text.split()

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
                    if order=='LIMIT':
                        trade_result = binance_trader.execute_limit(api_key, api_secret, symbol, side, time_in_force,  price, quantity)
                        await update.message.reply_text(trade_result)
                    elif order=='MARKET':
                        trade_result = binance_trader.execute_market(api_key, api_secret, symbol, side, quantity)
                        await update.message.reply_text(trade_result)
                    elif order =='LAYER':
                        max_orders = binance_trader.get_max_orders(symbol)
                        print(f'maximum orders for {symbol}: {max_orders}')

                        if len(prices) > int(max_orders):
                            update.message.reply_text('Number of orders exceed maximum, adjust and resubmit again')
                        else:
                            for price in prices:
                                trade_result = binance_trader.execute_limit(api_key, api_secret, symbol, side, time_in_force, price, quantity)
                                await update.message.reply_text(trade_result)
                else:
                    await update.message.reply_text('Failed to initialize Binance client. Please check your API key and secret.')
            else:
                await update.message.reply_text('You haven\'t set your credentials yet. Click on Set Credentials to do so.')
        except ValueError:
            await update.message.reply_text('Invalid format. Please enter trade details in the format:\n' 'TRADE LAYER ORDERTYPE SYMBOL SIDE TIMEINFORCE MAXPRICE MINPRICE NUMBEROFORDERS QUANTITY\n' '(e.g., TRADE LAYER LIMIT BTCUSDT BUY GTC 63000 62000 10 20000) or\n' 'TRADE ORDERTYPE SYMBOL SIDE TIMEINFORCE PRICE QUANTITY\n' '(e.g., TRADE LIMIT BTCUSDT BUY GTC 65000 0.001) or\n' 'TRADE ORDERTYPE SYMBOL SIDE QUANTITY\n' '(e.g., TRADE MARKET BTCUSDT BUY 0.01)')
        finally:
            context.user_data['expecting_trade'] = False
    else:
        await update.message.reply_text('Click \'Execute Trade\' to execute a Binance trade.')

async def execute_twap(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()  # Acknowledge the button click
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
            await update.callback_query.message.reply_text('Please enter twap details in the format:\n' 'TWAP SYMBOL SIDE TIMEINFORCE TIMEFRAME(HOURS) NUMBEROFORDERS QUANTITY\n' '(e.g., TWAP BTCUSDT BUY GTC 1 10 20000)')
            context.user_data['expecting_twap'] = True
        else:
            await update.callback_query.message.reply_text('Failed to initialize Binance client. Please check your API key and secret.')
    else:
        await update.callback_query.message.reply_text('You haven\'t set your credentials yet. Use /setcredentials to do so.')

async def handle_twap(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get('expecting_twap'):
        try:
            message_text = update.message.text[len('TWAP '):]
            symbol, side, time_in_force, timeframe, num_orders, quantity = message_text.split()

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
                    asyncio.create_task(run_twap(api_key, api_secret, update, symbol, side, time_in_force, float(timeframe), int(num_orders), float(quantity)))
                else:
                    await update.message.reply_text('Failed to initialize Binance client. Please check your API key and secret.')
            else:
                await update.message.reply_text('You haven\'t set your credentials yet. Click on Set Credentials to do so.')
        except ValueError:
            await update.message.reply_text('Invalid format. Please enter twap details in the format:\n' 'TWAP SYMBOL SIDE TIMEINFORCE TIMEFRAME(HOURS) NUMBEROFORDERS QUANTITY\n' '(e.g., TWAP BTCUSDT BUY GTC 1 10 20000)')


async def run_twap(api_key, api_secret, update, symbol, side, time_in_force, timeframe, num_orders, quantity):
    quantity_per_order = quantity / num_orders
    interval_minutes = (timeframe * 60) / num_orders

    await update.message.reply_text(f"TWAP order for {symbol} started. First order will be placed in {interval_minutes} minutes.")

    for i in range(int(num_orders)):
        # Wait for the interval before placing each order, including the first one
        await asyncio.sleep(interval_minutes * 60)  # Convert minutes to seconds

        try:
            # Get current price
            current_price = binance_trader.get_market_data(symbol, price_only=True)
            # Place limit order
            trade_result = binance_trader.execute_limit(api_key, api_secret, symbol, side, time_in_force, price=current_price, quantity=quantity_per_order)
            await update.message.reply_text(trade_result)
            await update.message.reply_text(f"TWAP limit order {i+1}/{num_orders} placed for {symbol}")

            # Check if the order is filled
            order_id = re.search(r'Order (\d+)', trade_result).group(1)
            order_filled = False
            check_interval = min(30, interval_minutes * 60)  # Check every 30 seconds or at the next interval, whichever is sooner

            while not order_filled:
                client = binance_trader.init_binance_client(api_key, api_secret)
                order_status = client.get_order(symbol=symbol, orderId=order_id)
                if order_status['status'] == 'FILLED':
                    await update.message.reply_text(f"TWAP order {i+1}/{num_orders} filled for {symbol}")
                    order_filled = True
                elif order_status['status'] == 'CANCELED':
                    await update.message.reply_text(f"TWAP order {i+1}/{num_orders} was canceled for {symbol}")
                    break
                await asyncio.sleep(check_interval)

        except Exception as e:
            await update.message.reply_text(f"Error placing TWAP order: {e}")

    await update.message.reply_text(f"TWAP order completed for {symbol}")

async def retrieve_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()  # Acknowledge the button click
    await update.callback_query.message.reply_text('Please enter the symbol in this format:\n' 'DATA SYMBOL\n' '(e.g., DATA BTCUSDT)')
    context.user_data['expecting_symbol'] = True

async def handle_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(update.message.text)
    print("Handling symbol function called.")
    if context.user_data.get('expecting_symbol'):
        print("Expecting symbol flag is True.")
        try:
            symbol = update.message.text[len('DATA '):]
            data = binance_trader.get_market_data(symbol, price_only=False)
            await update.message.reply_text(data)
        except ValueError:
            await update.message.reply_text('Invalid format. Please enter the symbol in this format:\n' 'DATA SYMBOL\n' '(e.g., DATA BTCUSDT)')

async def retrieve_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()  # Acknowledge the button click
    try:
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
                data = binance_trader.get_balance(api_key, api_secret)
                if data == False:
                    await update.callback_query.message.reply_text('No balances for account.')
                else:
                    for message in data:
                        await update.callback_query.message.reply_text(message)
            else:
                await update.callback_query.message.reply_text('Failed to initialize Binance client. Please check your API key and secret.')
        else:
            await update.callback_query.message.reply_text('You haven\'t set your credentials yet. Click on Set Credentials to do so.')
    except Exception as e:
        await update.callback_query.message.reply_text(f'An error occurred: {str(e)}')

async def margin_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    await update.callback_query.answer() #Acknowledge the button click

    try:
        user_id = update.effective_user.id
        conn = sqlite3.connect('user_credentials.db')
        c = conn.cursor()
        c.execute("SELECT username, password FROM credentials WHERE user_id = ?", (user_id,)) #username = apikey, passw>
        result = c.fetchone()
        conn.close()

        if result:
            api_key, api_secret = result
            data = binance_trader.get_margin(api_key, api_secret)
            await update.callback_query.message.reply_text(data)
        else:
            await update.callback_query.mesasge.reply_text('You haven\'t set your credentials yet. Click on Set Credentials to do so.')
    except Exception as e:
        await update.callback_query.message.reply_text(f"An error occurred: {e}")

async def retrieve_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()  # Acknowledge the button click
    await update.callback_query.message.reply_text('Please enter the type of orders to retrieve in this format:\n' 'CHECK OUSTANDING/EXECUTED NUMBEROFORDERS(for executed orders only) SYMBOL\n' '(e.g., CHECK OUTSTANDING BTCUSDT) or\n' '(e.g., CHECK EXECUTED 10 BTCUSDT)')
    context.user_data['expecting_orders'] = True

async def handle_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(update.message.text)
    print("Handling orders function called.")
    if context.user_data.get('expecting_orders'):
        print("Expecting orders flag is True.")
        try:
            if update.message.text[:18]=='CHECK OUTSTANDING ':
                status = 'outstanding'
                symbol = update.message.text[len('CHECK OUTSTANDING '):]
            elif update.message.text[:15] =='CHECK EXECUTED ':
                status = 'executed'
                message_text = update.message.text[len('CHECK EXECUTED '):]
                limit, symbol = message_text.split()

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
                    if status == 'outstanding':
                        outstanding_orders = binance_trader.get_orders(api_key, api_secret, status, symbol)
                        if outstanding_orders == False:
                            await update.message.reply_text(f'No outstanding orders for {symbol}')
                        else:
                            for message in outstanding_orders:
                                await update.message.reply_text(message)
                    elif status == 'executed':
                        print(f'Limit = {limit}')
                        executed_orders = binance_trader.get_orders(api_key, api_secret, status, symbol, limit)
                        if executed_orders == False:
                            await update.message.reply_text(f'No executed orders for {symbol}')
                        else:
                            for message in executed_orders:
                                await update.message.reply_text(message)

                else:
                    await update.message.reply_text('Failed to initialize Binance client. Please check your API key and secret.')
            else:
                await update.message.reply_text('You haven\'t set your credentials yet. Click on Set Credentials to do so.')

        except ValueError:
            await update.message.reply_text('Please enter the type of orders to retrieve in this format:\n' 'CHECK OUSTANDING/EXECUTED NUMBEROFORDERS(for executed orders only) SYMBOL\n' '(e.g., CHECK OUTSTANDING BTCUSDT) or\n' '(e.g., CHECK EXECUTED 10 BTCUSDT)')

async def cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()  # Acknowledge the button click
    await update.callback_query.message.reply_text('Please enter the type of orders to cancel in this format:\n' 'CANCEL ALL or\n' 'CANCEL ALL SIDE\n' '(e.g., CANCEL ALL BUY/SELL) or\n' 'CANCEL ALL TICKER \n' '(e.g., CANCEL ALL BTCUSDT) or\n' 'CANCEL ALL TICKER SIDE \n' '(e.g., CANCEL ALL BTCUSDT BUY/SELL) or\n' 'CANCEL SYMBOL ORDERID\n' '(e.g., CANCEL BTCUSDT 12345678)')
    context.user_data['cancelling_orders'] = True

async def handle_cancel_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(update.message.text)
    print("Handling cancel orders function called.")
    if context.user_data.get('cancelling_orders'):
        print("Cancelling orders flag is True.")
        try:
            cancel_status = ''
            cancel_symbol = ''
            cancel_side = ''
            cancel_both = ''
            if update.message.text[:10] == 'CANCEL ALL':
                cancel_status = 'cancel'
                if update.message.text == 'CANCEL ALL':
                    cancel_symbol = 'all'

                elif update.message.text[:11] == 'CANCEL ALL ':
                    message_text = update.message.text[len('CANCEL ALL '):]
                    if message_text == 'BUY' or message_text == 'SELL':
                        cancel_side = message_text
                        cancel_symbol = 'all'
                    elif 'BUY' not in message_text and 'SELL' not in message_text:
                        cancel_side = 'symbol'
                        cancel_symbol = message_text
                    else:
                        cancel_both_symbol, cancel_both_side = message_text.split()
                        cancel_both = True

            else:
                message_text = update.message.text[len('CANCEL '):]
                symbol, order_id = message_text.split()

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
                    if cancel_status and not cancel_both:
                        open_orders = binance_trader.get_orders(api_key, api_secret, status = cancel_status, symbol = cancel_symbol, limit=False)
                        for order in open_orders:
                            symbol = order['symbol']
                            order_id = order['orderId']
                            if not cancel_side or cancel_side == order['side'] or cancel_symbol == symbol:
                                cancelled_orders = binance_trader.cancel_orders(api_key, api_secret, symbol, order_id)
                                await update.message.reply_text(cancelled_orders)
                    elif cancel_status and cancel_both:
                        open_orders = binance_trader.get_orders(api_key, api_secret, status = cancel_status, symbol = cancel_both_symbol, limit=False)
                        for order in open_orders:
                            side = order['side']
                            symbol = order['symbol']
                            order_id = order['orderId']
                            if cancel_both_side == side:
                                cancelled_orders = binance_trader.cancel_orders(api_key, api_secret, symbol, order_id)
                                await update.message.reply_text(cancelled_orders)
                    else:
                        cancelled_orders = binance_trader.cancel_orders(api_key, api_secret, symbol, order_id)
                        await update.message.reply_text(cancelled_orders)

                else:
                    await update.message.reply_text('Failed to initialize Binance client. Please check your API key and secret.')
            else:
                await update.message.reply_text('You haven\'t set your credentials yet. Click on Set Credentials to do so.')

        except ValueError:
            await update.message.reply_text('Invalid format. Please enter the type of orders to cancel in this format:\n' 'CANCEL ALL or\n' 'CANCEL ALL SIDE\n' '(e.g., CANCEL ALL BUY/SELL) or\n' 'CANCEL ALL TICKER \n' '(e.g., CANCEL ALL BTCUSDT) or\n' 'CANCEL ALL TICKER SIDE\n' '(e.g., CANCEL ALL BTCUSDT BUY/SELL) or\n' 'CANCEL SYMBOL ORDERID\n' '(e.g., CANCEL BTCUSDT 12345678)')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Handle button presses
    query = update.callback_query
    action = query.data

    if action == 'set_credentials':
        await set_credentials(update, context)
    elif action == 'view_username':
        await view_username(update, context)
    elif action == 'change_credentials':
        await change_credentials(update, context)
    elif action == 'execute_binance_trade':
        await execute_binance_trade(update, context)
    elif action == 'retrieve_data':
        await retrieve_data(update, context)
    elif action == 'retrieve_balance':
        await retrieve_balance(update, context)
    elif action == 'margin_history':
        await margin_history(update, context)
    elif action =='retrieve_orders':
        await retrieve_orders(update, context)
    elif action =='cancel_order':
        await cancel_order(update, context)
    elif action =='execute_twap':
        await execute_twap(update, context)

def main() -> None:
    # Initialize the database
    init_db()

    # Create the Application and pass it your bot's token
    application = Application.builder().token(os.getenv('TELEGRAM_BOT_TOKEN')).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    '''
    application.add_handler(CommandHandler("setcredentials", set_credentials))
    application.add_handler(CommandHandler("viewusername",view_username))
    #application.add_handler(CommandHandler("changecredentials", change_credentials))
    application.add_handler(CommandHandler("trade", execute_binance_trade))
    application.add_handler(CommandHandler("retrievedata", retrieve_data))
    '''
    # Register handlers with more specific conditions
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^TRADE '), handle_trade))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^SET '), handle_credentials))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^CHANGE '), handle_credential_change))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^DATA '), handle_data))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^CHECK '), handle_orders))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^CANCEL '), handle_cancel_orders))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^TWAP '), handle_twap))
    application.add_handler(CallbackQueryHandler(button_handler))

    #application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_trade))
    #application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_credentials))
    #application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_credential_change))

    # Run the bot until the user presses Ctrl-C
    application.run_polling()

if __name__ == '__main__':
    main()
