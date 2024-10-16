import numpy as np
from telegram.error import TimedOut
import datetime
import re
import asyncio
import time
import os
import sqlite3
from telegram import Bot
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
        [InlineKeyboardButton("Execute Scale", callback_data='execute_scale')],
        [InlineKeyboardButton("Info Scale", callback_data='info_scale')],
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
    await update.callback_query.message.reply_text('Please enter your username and password in this format: Set Username Password')
    context.user_data['expecting_credentials'] = True
    print(f'context.user_data: {context.user_data}')

async def handle_credentials(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(update.message.text)
    print("Handle credentials function called.")
    if context.user_data.get('expecting_credentials'):
        print("Expecting credentials flag is True.")
        try:
            message_text_upper = update.message.text.upper()
            message_text = message_text_upper[len('SET '):]
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
            await update.message.reply_text('Invalid format. Please provide username and password in this format: Set Username Password.')
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
            await update.callback_query.message.reply_text(
                    'Please enter trade details in the format:\n\n'
                    'Trade OrderType Symbol Side TimeInForce Price Quantity\n\n'
                    '\\(e\\.g\\., Trade Limit BTCUSDT Buy GTC 65000 0\\.001\\)\n\n'
                    '*OR*\n\n'
                    'Trade OrderType Symbol Side Quantity\n\n'
                    '\\(e\\.g\\., Trade Market BTCUSDT Buy 0\\.01\\)',
                    parse_mode='MarkdownV2')
            context.user_data['expecting_trade'] = True
        else:
            await update.callback_query.message.reply_text('Failed to initialize Binance client. Please check your API key and secret.')
    else:
        await update.callback_query.message.reply_text('You haven\'t set your credentials yet. Use /setcredentials to do so.')

async def handle_trade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get('expecting_trade'):
        try:
            order=False
            message_text_upper = update.message.text.upper()
            if message_text_upper[:11]=='TRADE LIMIT':
                order='LIMIT'
                message_text = message_text_upper[len('TRADE LIMIT '):]
                symbol, side, time_in_force, price, quantity = message_text.split()

            elif message_text_upper[:12]=='TRADE MARKET':
                order='MARKET'
                message_text = message_text_upper[len('TRADE MARKET '):]
                symbol, side, quantity = message_text.split()

            if order:
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
                    else:
                        await update.message.reply_text('Failed to initialize Binance client. Please check your API key and secret.')
                else:
                    await update.message.reply_text('You haven\'t set your credentials yet. Click on Set Credentials to do so.')
            else:
                await update.message.reply_text(
                        'Invalid format. Please enter trade details in the format:\n\n'
                        'Trade OrderType Symbol Side TimeInForce Price Quantity\n\n'
                        '\\(e\\.g\\., Trade Limit BTCUSDT Buy GTC 65000 0\\.001\\)\n\n'
                        '*OR*\n\n'
                        'Trade OrderType Symbol Side Quantity\n\n'
                        '\\(e\\.g\\., Trade Market BTCUSDT Buy 0\\.01\\)',
                        parse_mode='MarkdownV2')
        except ValueError:
            await update.message.reply_text(
                    'Invalid format. Please enter trade details in the format:\n\n'
                    'Trade OrderType Symbol Side TimeInForce Price Quantity\n\n'
                    '\\(e\\.g\\., Trade Limit BTCUSDT Buy GTC 65000 0\\.001\\)\n\n'
                    '*OR*\n\n'
                    'Trade OrderType Symbol Side Quantity\n\n'
                    '\\(e\\.g\\., Trade Market BTCUSDT Buy 0\\.01\\)',
                    parse_mode='MarkdownV2')
            #finally:
            #    context.user_data['expecting_trade'] = False
    else:
        await update.message.reply_text('Click \'Execute Trade\' to execute a Binance trade.')

async def info_scale(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()  # Acknowledge the button click
    chat_id = update.effective_chat.id
    image_paths=['/root/Telegram-Trading-Bot-Prod/exponentialfactor-graphics/expfactor0.png', '/root/Telegram-Trading-Bot-Prod/exponentialfactor-graphics/expfactor20.png', '/root/Telegram-Trading-Bot-Prod/exponentialfactor-graphics/expfactor50.png', '/root/Telegram-Trading-Bot-Prod/exponentialfactor-graphics/expfactor70.png', '/root/Telegram-Trading-Bot-Prod/exponentialfactor-graphics/expfactor100.png']
    for path in image_paths:
        with open(path, 'rb') as image_file:
            await context.bot.send_photo(chat_id=chat_id, photo=image_file)

async def execute_scale(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
            await update.callback_query.message.reply_text('Please enter trade details in the format:\n'
                    'Scale Total Symbol Side TimeInForce MaxPrice MinPrice NumOfOrders TotalQuantity\n\n'
                    '\\(e\\.g\\., Scale Total BTCUSDT Buy GTC 63000 62000 10 0\\.01\\) \n\n'
                    '*OR*\n\n'
                    'Scale Indi Symbol Side TimeInForce MaxPrice MinPrice ExpFactor%\\(0 \\- 100\\) NumOfOrders TotalQuantity\n\n'
                    '\\(e\\.g\\., Scale Indi BTCUSDT Buy GTC 63000 62000 10 10 0\\.01\\)',
                    parse_mode='MarkdownV2')
            context.user_data['expecting_scale'] = True
        else:
            await update.callback_query.message.reply_text('Failed to initialize Binance client. Please check your API key and secret.')
    else:
        await update.callback_query.message.reply_text('You haven\'t set your credentials yet. Use /setcredentials to do so.')

async def handle_scale(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get('expecting_scale'):
        try:
            message_text_upper = update.message.text.upper()
            if message_text_upper[:11] =='SCALE TOTAL':
                message_text = message_text_upper[len('SCALE TOTAL '):]
                symbol, side, time_in_force, maxprice, minprice, no_of_orders, quantity = message_text.split()
                maxprice = float(maxprice)
                minprice = float(minprice)
                priceadj = abs(maxprice - minprice) / (int(no_of_orders) - 1)
                quantity = float(quantity) / int(no_of_orders)
                prices = []
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

            elif message_text_upper[:10] =='SCALE INDI':
                message_text = message_text_upper[len('SCALE INDI '):]
                symbol, side, time_in_force, maxprice, minprice, factor, no_of_orders, quantity = message_text.split()
                if float(factor) >= 0 and float(factor) <= 100:
                    maxprice = float(maxprice)
                    minprice = float(minprice)
                    factor = round(1 + (float(factor) / 100),2)
                    quantity = float(quantity) / int(no_of_orders)
                    # Function to create exponentially spaced orders with custom exponent
                    def create_exponential_orders(start_price, end_price, n, exp_factor):                                       # Create an exponentially spaced sequence from 0 to 1
                        exp_sequence = np.geomspace(1, np.e, n) - 1  # Subtract 1 to start at 0    
                        # Apply custom exponential factor
                        exp_sequence = exp_sequence ** exp_factor                                                               # Normalize the exponential sequence to be within the range x to y
                        #exp_orders = start_price + exp_sequence * (end_price - start_price) / (np.e**exp_factor - 1)    
                        exp_orders = start_price + (end_price - start_price) * exp_sequence / exp_sequence[-1]
                        return exp_orders.tolist()

                    if side == 'BUY':
                        prices = create_exponential_orders(start_price = maxprice, end_price = minprice, n = int(no_of_orders), exp_factor = factor)
                    elif side == 'SELL':
                        prices = create_exponential_orders(start_price = minprice, end_price = maxprice, n = int(no_of_orders), exp_factor = factor)

                else:
                    return await update.message.reply_text(f'Submitted factor % {factor} is not within range. Please submit % between 0 - 100.')

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
                    max_orders = binance_trader.get_max_orders(symbol)
                    print(f'maximum orders for {symbol}: {max_orders}')

                    if len(prices) > int(max_orders):
                        await update.message.reply_text('Number of orders exceed maximum, adjust and resubmit again')
                    else:
                        for price in prices:
                            price = round(price, 2)
                            trade_result = binance_trader.execute_limit(api_key, api_secret, symbol, side, time_in_force, price, quantity)
                            await update.message.reply_text(trade_result)
                else:
                    await update.message.reply_text('Failed to initialize Binance client. Please check your API key and secret.')
            else:
                await update.message.reply_text('You haven\'t set your credentials yet. Click on Set Credentials to do so.')

        except ValueError:
            await update.message.reply_text(
                    'Invalid format. Please enter trade details in the format:\n'
                    'Scale Total Symbol Side TimeInForce MaxPrice MinPrice NumOfOrders TotalQuantity\n\n'
                    '\\(e\\.g\\., Scale Total BTCUSDT Buy GTC 63000 62000 10 0\\.01\\) \n\n'
                    '*OR*\n\n'
                    'Scale Indi Symbol Side TimeInForce MaxPrice MinPrice ExpFactor%\\(0 \\- 100\\) NumOfOrders TotalQuantity\n\n'
                    '\\(e\\.g\\., Scale Indi BTCUSDT Buy GTC 63000 62000 10 10 0\\.01\\)',
                    parse_mode='MarkdownV2')
            #finally:
            #    context.user_data['expecting_trade'] = False
    else:
        await update.message.reply_text('Click \'Execute Scale\' to execute a Binance scale trade.')



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
            await update.callback_query.message.reply_text(
                    'Please enter twap details in the format:\n'
                    'TWAP AMOUNT Symbol Side TimeInForce Duration\\(Mins\\) NumOfOrders\\* AmountUSD\n'
                    '\\(e\\.g\\., TWAP AMOUNT BTCUSDT Buy GTC 10 10 100000\\)\n\n'
                    '*OR*\n\n'
                    'TWAP PERCENT Symbol Side TimeInForce Duration\\(Mins\\) NumOfOrders\\* PercentageOfHoldingsToTrade\n'
                    '\\(e\\.g\\., TWAP PERCENT BTCUSDT Buy GTC 10 10 50\\)\n\n'
                    '\\*NumOfOrders can input "default" or integer, default \\= 50',
                    parse_mode='MarkdownV2')
            context.user_data['expecting_twap'] = True
        else:
            await update.callback_query.message.reply_text('Failed to initialize Binance client. Please check your API key and secret.')
    else:
        await update.callback_query.message.reply_text('You haven\'t set your credentials yet. Use /setcredentials to do so.')

async def handle_twap(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get('expecting_twap'):
        try:
            twap_type = ''
            message_text_upper = update.message.text.upper()
            if message_text_upper[:11] == 'TWAP AMOUNT':
                twap_type = 'amount'
                message_text = message_text_upper[len('TWAP AMOUNT '):]
                symbol, side, time_in_force, duration, num_of_orders, usd_size = message_text.split()
                duration = float(duration)*60

                if side.upper() == 'SELL':
                    last_price = binance_trader.get_last_price(symbol)
                    coin_sell_amount = float(usd_size) / last_price
                elif side.upper() == 'BUY':
                    coin_sell_amount = 0

            elif message_text_upper[:12] == 'TWAP PERCENT':
                twap_type = 'percent'
                message_text = message_text_upper[len('TWAP PERCENT '):]
                symbol, side, time_in_force, duration, num_of_orders, percent = message_text.split()
                duration = float(duration)*60

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
                    if twap_type == 'percent':
                        balances = binance_trader.get_balance(api_key, api_secret, position = True, display=False)
                        acc_pct = float(percent) / 100
                        if acc_pct == 1:
                            acc_pct = 0.995
                        if side.upper() == 'SELL':
                            if symbol[:-4] in balances:
                                coin_balance = balances[symbol[:-4]]["coin_amount"]
                            else:
                                coin_balance = 0
                            coin_sell_amount = coin_balance * acc_pct
                            usd_size = 0
                        elif side.upper() == 'BUY':
                            if "USDT" in balances:
                                usdt_balance = balances["USDT"]["coin_amount"]
                            else:
                                usdt_balance = 0
                            usd_size = round(usdt_balance * acc_pct)
                            coin_sell_amount = 0
                    asyncio.create_task(linear_twap(api_key, api_secret, update, symbol, side, time_in_force, float(duration), num_of_orders, coin_sell_amount, float(usd_size)))
                else:
                    await update.message.reply_text('Failed to initialize Binance client. Please check your API key and secret.')
            else:
                await update.message.reply_text('You haven\'t set your credentials yet. Click on Set Credentials to do so.')
        except ValueError:
            await update.message.reply_text(
                    'Invalid format\\. Please enter twap details in the format:\n'
                    'TWAP AMOUNT Symbol Side TimeInForce Duration\\(Mins\\) NumOfOrders\\* AmountUSD\n'
                    '\\(e\\.g\\., TWAP AMOUNT BTCUSDT Buy GTC 10 10 100000\\)\n\n'
                    '*OR*\n\n'
                    'TWAP PERCENT Symbol Side TimeInForce Duration\\(Mins\\) NumOfOrders* PercentageOfHoldingsToTrade\n'
                    '\\(e\\.g\\., TWAP PERCENT BTCUSDT Buy GTC 10 10 50\\)\n\n'
                    '\\*NumOfOrders can input "default" or integer, default \\= 100',
                    parse_mode='MarkdownV2')

async def linear_twap(api_key, api_secret, update, symbol, side, time_in_force, duration, num_of_orders, coin_sell_amount, usd_size):
    """
    fuction that split order into equal sized orders and executes them over specified duration with equal time delays
    :param client: bybit client
    :param usd_size: size in usd
    :param symbol: choose ticker
    :param side: buy, sell
    :param duration: in seconds
    :param num_of_orders: amount of orders [default: 100 orders, int: specific number of orders)
    :return:
    """

    min_notional, max_notional, decimals, tick_decimals ,min_qty, max_qty = binance_trader.get_instrument_info(api_key, api_secret, symbol)

    balances = binance_trader.get_balance(api_key, api_secret, position=True, display=False)

    # check if size doesn't excedes available usdt qty
    # if based on order amount size becomes lower than min qty fix it to min qty
    orders = []
    if min_qty is not None and decimals is not None and tick_decimals is not None and max_qty is not None:
        if side.upper() == "BUY":
            if "USDT" in balances:
                usdt_balance = balances["USDT"]["coin_amount"]
            else:
                usdt_balance = 0
            if usd_size < usdt_balance:
                # min order size is in usd
                if num_of_orders.isalpha():
                    if num_of_orders.upper() == "DEFAULT":
                        num_of_orders = 100
                        single_order = int(usd_size / num_of_orders)
                        last_price = binance_trader.get_last_price(symbol)
                        single_order = round(single_order / last_price, decimals)

                        if single_order > min_qty:
                            if single_order < max_qty:
                                for i in range(num_of_orders):
                                    orders.append(single_order)
                            else:
                                await update.message.reply_text(f"Single order too big to execute TWAP. Current order size: {single_order}, Max order size: {max_qty} ")
                        else:
                            await update.message.reply_text(f"Current total TWAP size too low: {usd_size}")
                    else:
                        await update.message.reply_text(f"Format for NumOfOrders is wrong. Please check.")
                else:
                    orders = []
                    num_of_orders = int(num_of_orders)
                    single_order = int(usd_size / num_of_orders)
                    last_price = binance_trader.get_last_price(symbol)
                    single_order = round(single_order / last_price, decimals)

                    if single_order > min_qty:
                        if single_order < max_qty:
                            for i in range(num_of_orders):
                                orders.append(single_order)
                        else:
                            await update.message.reply_text(f"Single order too big to execute TWAP. Current order size: {single_order}, Max order size: {max_qty} ")
                    else:
                        await update.message.reply_text(f"Single order size too low to execute TWAP. Current order size: {int(usd_size / num_of_orders)}, Min order size: {min_qty}")
            else:
                await update.message.reply_text(f"Not enough USDT to execute TWAP. Available funds: ${usdt_balance}, TWAP size: ${usd_size}")


        elif side.upper() == "SELL":
            # min order size is in coins
            if symbol[:-4] in balances:
                coin_balance = balances[symbol[:-4]]["coin_amount"]
            else:
                coin_balance = 0

            coins_to_sell = coin_sell_amount
            if coin_balance >= coin_sell_amount:
                if num_of_orders.isalpha():
                    if num_of_orders.upper() == "DEFAULT":
                        num_of_orders = 100
                        single_order = round(coins_to_sell / num_of_orders, decimals)
                        if single_order > min_qty:
                            if single_order < max_qty:
                                for i in range(num_of_orders):
                                    orders.append(single_order)
                            else:
                                await update.message.reply_text(f"Single order to big to execute TWAP. Current order size: {single_order} coins, Max order size: {max_qty} coins ")
                        else:
                            await update.message.reply_text(f"Total TWAP size is too low: {usd_size} >> should be at least $100")
                    else:
                        await update.message.reply_text(f"Format for NumOfOrders is wrong. Please check.")
                else:
                    orders = []
                    num_of_orders = int(num_of_orders)
                    single_order = round(coins_to_sell /num_of_orders, decimals)

                    if single_order > min_qty:
                        if single_order < max_qty:
                            for i in range(num_of_orders):
                                orders.append(single_order)
                        else:
                            await update.message.reply_text(f"Single order too big to execute TWAP. Current order size: {single_order} coins, Max order size: {max_qty} coins")
                    else:
                        await update.message.reply_text(f"Single order size too low to execute TWAP. Current order size: {single_order} coins, Min order size: {min_qty} coins")
            else:
                await update.message.reply_text(f"Not enough coins to execute Sell TWAP. Available funds: {coin_balance} coins, TWAP size: {coin_sell_amount} coins")

        else:
            await update.message.reply_text(f"Error with side input. Input: {side}, Expected: Buy/Sell")

        if orders:
            time_delay = duration / int(num_of_orders)
            await execute_orders(api_key, api_secret, update, symbol, side, orders, time_delay)

        '''
        if orders and side.upper() in ["BUY", "SELL"]:
            i = 0
            for order in orders:
                start = time.time()
                try:
                    trade_result = binance_trader.execute_market(api_key, api_secret, symbol, side, quantity=order)
                    await update.message.reply_text(trade_result)
                    await update.message.reply_text(f"TWAP order {i+1}/{num_of_orders} filled for {symbol}")

                    loop_time = time.time() - start
                    delay = time_delay - loop_time
                    if delay > 0:
                        asyncio.sleep(time_delay)
            
                    i += 1

                except Exception as e:
                    await update.message.reply_text(f"Error placing TWAP order: {e}")
        
            if i == num_of_orders:
                await update.message.reply_text(f"TWAP order completed for {symbol}")
        '''
    else:
        await update.message.reply_text(f'Unable to retrieve essential values to execute TWAP.')

async def execute_orders(api_key, api_secret, update, symbol, side, orders, time_delay):
    order_updates = []
    for i, order in enumerate(orders, 1):
        start = time.time()
        try:
            trade_result = await binance_trader.execute_market(api_key, api_secret, symbol, side, quantity=order)
            #await update.message.reply_text(trade_result)
            #await update.message.reply_text(f"TWAP order {i}/{len(orders)} filled for {symbol}")

            order_updates.append(trade_result)
            order_updates.append(f"TWAP order {i}/{len(orders)} filled for {symbol}")

            if i % 10 == 0 or i == len(orders):
                asyncio.create_task(send_telegram_updates(update, order_updates))
                order_updates = []

            loop_time = time.time() - start
            delay = time_delay - loop_time
            # Check if this is the last order
            if i == len(orders):
                # If it's the last order, send the completion message immediately
                await update.message.reply_text(f"TWAP order completed for {symbol}")
            else:
                # If not the last order, wait for the specified delay

                if delay > 0:
                    await asyncio.sleep(delay)

        except Exception as e:
            await update.message.reply_text(f"Error placing TWAP order: {e}")

async def send_telegram_updates(update, order_updates):
    try:
        await update.message.reply_text("\n".join(order_updates))
    except FloodWait as e:
        # Sleep for the time specified in the exception and retry sending updates
        await asyncio.sleep(e.x)
        await update.message.reply_text("\n".join(order_updates))

'''
async def run_twap(api_key, api_secret, update, symbol, side, time_in_force, timeframe, num_orders, quantity):
    quantity_per_order = quantity / num_orders
    interval_minutes = (timeframe * 60) / num_orders

    await update.message.reply_text(f"TWAP order for {symbol} started. First order will be placed in {interval_minutes} minutes.")

    for i in range(int(num_orders)):
        # Wait for the interval before placing each order, including the first one
        await asyncio.sleep(interval_minutes * 60)  # Convert minutes to seconds

        try:
            # Place market order
            trade_result = binance_trader.execute_market(api_key, api_secret, symbol, side, quantity=quantity_per_order)
            await update.message.reply_text(trade_result)
            if trade_result:
                status = re.search(r'Status: (\w+)', trade_result).group(1)
                if status == 'FILLED':
                    await update.message.reply_text(f"TWAP order {i+1}/{num_orders} filled for {symbol}")
            
        except Exception as e:
            await update.message.reply_text(f"Error placing TWAP order: {e}")

    await update.message.reply_text(f"TWAP order completed for {symbol}")
'''

async def retrieve_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()  # Acknowledge the button click
    await update.callback_query.message.reply_text('Please enter the symbol in this format:\n' 'Data SYMBOL\n' '(e.g., Data BTCUSDT)')
    context.user_data['expecting_symbol'] = True

async def handle_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(update.message.text)
    print("Handling symbol function called.")
    if context.user_data.get('expecting_symbol'):
        print("Expecting symbol flag is True.")
        try:
            message_text_upper = update.message.text.upper()
            symbol = message_text_upper[len('DATA '):]
            data = binance_trader.get_market_data(symbol, price_only=False)
            await update.message.reply_text(data)
        except ValueError:
            await update.message.reply_text('Invalid format. Please enter the symbol in this format:\n' 'Data SYMBOL\n' '(e.g., Data BTCUSDT)')

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
            print(api_key, api_secret)
            client = binance_trader.init_binance_client(api_key, api_secret)
            print("init client")
            if client:
                print("client ok")
                data = binance_trader.get_balance(api_key, api_secret, position=False, display=False)
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
    await update.callback_query.message.reply_text('Please enter the type of orders to retrieve in this format:\n' 'Check Outstanding/Executed NumOfOrders(for executed orders only) Symbol\n' '(e.g., Check Outstanding ALL) or\n'  '(e.g., Check Outstanding BTCUSDT) or\n' '(e.g., Check Executed 10 BTCUSDT)')
    context.user_data['expecting_orders'] = True

async def handle_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(update.message.text)
    print("Handling orders function called.")
    if context.user_data.get('expecting_orders'):
        print("Expecting orders flag is True.")
        try:
            message_text_upper = update.message.text.upper()
            if message_text_upper[:18]=='CHECK OUTSTANDING ':
                status = 'outstanding'
                symbol = message_text_upper[len('CHECK OUTSTANDING '):]
            elif message_text_upper[:15] =='CHECK EXECUTED ':
                status = 'executed'
                message_text = message_text_upper[len('CHECK EXECUTED '):]
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
                                #await update.message.reply_text(message)
                                await retry_send_message(context.bot, update.effective_chat.id, message)
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
            await update.message.reply_text('Please enter the type of orders to retrieve in this format:\n' 'Check Outstanding/Executed NumOfOrders(for executed orders only) Symbol\n' '(e.g., Check Outstanding ALL) or\n'  '(e.g., Check Outstanding BTCUSDT) or\n' '(e.g., Check Executed 10 BTCUSDT)')

async def cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()  # Acknowledge the button click
    await update.callback_query.message.reply_text('Please enter the type of orders to cancel in this format:\n' 'Cancel All or\n' 'Cancel All Side\n' '(e.g., Cancel All Buy/Sell) or\n' 'Cancel All Symbol \n' '(e.g., Cancel All BTCUSDT) or\n' 'Cancel All Symbol Side \n' '(e.g., Cancel All BTCUSDT Buy/Sell) or\n' 'Cancel Symbol OrderID\n' '(e.g., Cancel BTCUSDT 12345678)')
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
            message_text_upper = update.message.text.upper()
            if message_text_upper[:10] == 'CANCEL ALL':
                cancel_status = 'cancel'
                if message_text_upper == 'CANCEL ALL':
                    cancel_symbol = 'all'

                elif message_text_upper[:11] == 'CANCEL ALL ':
                    message_text = message_text_upper[len('CANCEL ALL '):]
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
                message_text = message_text_upper[len('CANCEL '):]
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
                        if len(open_orders) == 0:
                            await update.message.reply_text(f'No outstanding orders')
                        else:
                            for order in open_orders:
                                symbol = order['symbol']
                                order_id = order['orderId']
                                if not cancel_side or cancel_side == order['side'] or cancel_symbol == symbol:
                                    cancelled_orders = binance_trader.cancel_orders(api_key, api_secret, symbol, order_id)
                                    await update.message.reply_text(cancelled_orders)
                    elif cancel_status and cancel_both:
                        open_orders = binance_trader.get_orders(api_key, api_secret, status = cancel_status, symbol = cancel_both_symbol, limit=False)
                        if len(open_orders) == 0:
                            await update.message.reply_text(f'No outstanding orders')
                        else:
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
            await update.message.reply_text('Invalid format. Please enter the type of orders to cancel in this format:\n' 'Cancel All or\n' 'Cancel All Side\n' '(e.g., Cancel All Buy/Sell) or\n' 'Cancel All Symbol \n' '(e.g., Cancel All BTCUSDT) or\n' 'Cancel All Symbol Side \n' '(e.g., Cancel All BTCUSDT Buy/Sell) or\n' 'Cancel Symbol OrderID\n' '(e.g., Cancel BTCUSDT 12345678)')
        except Exception as e:
            await update.message.reply_text(f'An error occurred: {e}')

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
    elif action =='execute_scale':
        await execute_scale(update, context)
    elif action =='info_scale':
        await info_scale(update, context)

async def retry_send_message(bot, chat_id, message, retries=10):
    for attempt in range(retries):
        try:
            await bot.send_message(chat_id=chat_id, text=message)
            break  # If successful, exit the loop
        except TimedOut:
            if attempt < retries - 1:
                print(f"Retrying... ({attempt + 1}/{retries})")
                await asyncio.sleep(2)  # Wait before retrying
            else:
                print("Max retries reached. Message could not be sent.")

def main() -> None:
    # Initialize the database
    init_db()

    # Initialize the Bot with the custom Request
    bot = Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'))

    # Create the Application and pass it your bot's token
    application = Application.builder().bot(bot).build()

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
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'(?i)^TRADE '), handle_trade))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'(?i)^SET '), handle_credentials))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'(?i)^CHANGE '), handle_credential_change))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'(?i)^DATA '), handle_data))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'(?i)^CHECK '), handle_orders))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'(?i)^CANCEL '), handle_cancel_orders))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'(?i)^TWAP '), handle_twap))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'(?i)^SCALE '), handle_scale))
    application.add_handler(CallbackQueryHandler(button_handler))

    #application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_trade))
    #application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_credentials))
    #application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_credential_change))

    # Run the bot until the user presses Ctrl-C
    application.run_polling()

if __name__ == '__main__':
    main()

                                                     974,0-1       Bot
