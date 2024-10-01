from binance.spot import Spot as Client
from binance.error import ParameterRequiredError
from datetime import datetime,timedelta
import requests

def init_binance_client(api_key, api_secret):
    try:
        #client = Client(api_key, api_secret) for production
        client = Client(api_key, api_secret,base_url='https://testnet.binance.vision')
        return client
    except Exception as e:
        print(f"Error initializing Binance client: {e}")
        return None

def execute_limit(api_key, api_secret, symbol, side, time_in_force, price, quantity):
    try:
        client = Client(api_key, api_secret,base_url='https://testnet.binance.vision')
        if client:
            params = {
                    'symbol': symbol,
                    'side': side.upper(),
                    'type': 'LIMIT',
                    'timeInForce' : time_in_force,
                    'quantity' : quantity,
                    'price': price
                    }
            response = client.new_order(**params)
            return (f"Order {response['orderId']} submitted to {response['side']} {response['origQty']} {response['symbol']}\n"
                    f"Price: {response['price']}\n"
                    f"Status: {response['status']}\n"
                    f"Executed quantity: {response['executedQty']}")
        else:
            return('Failed to initialize Binance client. Please check your API key and secret.')


        return f"Order executed successfully: {order}"
    except Exception as e:
        return f"Error executing trade: {e}"

def execute_market(api_key, api_secret, symbol, side, quantity):
    try:
        client = Client(api_key, api_secret,base_url='https://testnet.binance.vision')
        if client:
            params = {
                    'symbol': symbol,
                    'side': side.upper(),
                    'type': 'MARKET',
                    'quantity' : quantity,
                    }
            print(params)
            response = client.new_order(**params)
            executed = []
            for entry in response['fills']:
                executed.append(f"Price: {entry['price']}, Executed quantity: {entry['qty']}")
            executed = '\n'.join(executed)
            return (f"Order {response['orderId']} submitted to {response['side']} {response['origQty']} {response['symbol']}\n"
                    f"Status: {response['status']}\n"
                    f"{executed}")
        else:
            return('Failed to initialize Binance client. Please check your API key and secret.')


        return f"Order executed successfully: {order}"
    except Exception as e:
        return f"Error executing trade: {e}"

def get_market_data(symbol, price_only):
    base_url = 'https://api.binance.com'
    endpoint = '/api/v3/ticker/24hr'
    params = {'symbol': symbol}
    depth_endpoint='/api/v3/depth'
    limit = 5
    depth_params = {'symbol': symbol, 'limit': limit}

    try:
        response = requests.get(base_url + endpoint, params=params)
        response.raise_for_status()  # Raise an exception for HTTP errors
        depth_response = requests.get(base_url + depth_endpoint, depth_params)
        depth_response.raise_for_status()

        data = response.json()
        price = float(data['lastPrice'])

        if price_only:
            return price
        else:
            volume = float(data['volume'])
            timestamp = data['closeTime']  # Milliseconds timestamp
            timestamp_datetime = datetime.fromtimestamp(timestamp / 1000.0)  # Convert to seconds and to datetime
            depth_data = depth_response.json()
            bids=depth_data['bids']
            asks=depth_data['asks']
            bids_str = "\n".join([f"Price: {float(bid[0]):.2f}, Quantity: {float(bid[1]):.2f}" for bid in bids])
            asks_str = "\n".join([f"Price: {float(ask[0]):.2f}, Quantity: {float(ask[1]):.2f}" for ask in asks])

            return (f"Current price of {symbol}: {price:.2f}\n"
                    f"24h Volume: {volume:.2f}\n"
                    f"Order Book for {symbol}:\n"
                    f"Time: {timestamp_datetime.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"\nTop {limit} Bids: \n{bids_str}\n"
                    f"\nTop {limit} Asks: \n{asks_str}")
    except requests.exceptions.RequestException as e:
        return f"Error fetching market data: {e}"

def get_balance(api_key, api_secret):
    try:
        client = Client(api_key, api_secret,base_url='https://testnet.binance.vision')
        print("get blanace, client ok")
        if client:
            info = client.account()
            balances = info['balances']

            messages = []
            current_message = ''
            for balance in balances:
                asset = balance['asset']
                free_balance = float(balance['free'])
                locked_balance = float(balance['locked'])

                if free_balance > 0 or locked_balance > 0:
                    balance_line = f"Asset: {asset}, Free: {free_balance:.2f}, Locked: {locked_balance:.2f}\n"

                if len(current_message) + len(balance_line) > 4096:
                    messages.append(current_message.strip())  # Add the current chunk to the list
                    current_message = balance_line  # Start a new message with the current line
                else:
                    # Otherwise, add the line to the current message
                    current_message += balance_line

             # Append the last accumulated message (if any)
            if current_message:
                messages.append(current_message.strip())

            if len(messages) == 0:
                return False
            else:
                return messages
        else:
            return('Failed to initialize Binance client. Please check your API key and secret.')

    except Exception as e:
        return f"Failed to retrieve balance: {str(e)}"

def get_margin(api_key, api_secret):
    current_time = datetime.now()
    date_30_days_ago = current_time - timedelta(days=30)

    current_time = int(current_time.timestamp()*1000)
    date_30_days_ago = int(date_30_days_ago.timestamp()*1000)
    params = {
        'asset' : 'USDT',
        'size' : 90,
        'startTime' : date_30_days_ago,
        'endTime' : current_time,
        'recvWindow': 20000,
        "timestamp": current_time
    }

    try:
        client = Client(api_key, api_secret)
        if client:
            response = client.margin_interest_rate_history(**params)
            return response[:3]
        else:
            return ('Failed to initialize Binance client. Please check your API key and secret.')

    except Exception as e:
        return f"An error occurred: {e}"


def get_max_orders(symbol):
    base_url = 'https://api.binance.com'
    endpoint = '/api/v3/exchangeInfo'
    params = {'symbol': symbol}

    try:
        response = requests.get(base_url + endpoint, params=params)
        response.raise_for_status()  # Raise an exception for HTTP errors

        data = response.json()['symbols'][0]['filters']
        max_orders = data[7]['maxNumOrders']

        return max_orders
    except requests.exceptions.RequestException as e:
        return f"Error fetching maximum number of orders: {e}"

def get_orders(api_key, api_secret, status, symbol, limit=False):
    try:
        client=Client(api_key, api_secret,base_url='https://testnet.binance.vision')
        print('get orders, client ok')
        if client:
            messages = []
            current_message = ''
            if status == 'outstanding':
                orders = client.get_orders(symbol=symbol)
                outstanding_orders = [order for order in orders if order['status'] in ['NEW', 'PARTIALLY_FILLED']]
                if len(outstanding_orders) != 0:
                    for order in outstanding_orders:
                        if order['status'] == 'NEW':
                            messages.append(f"Order {order['orderId']} submitted to {order['side']} {order['origQty']} {order['symbol']} at {order['price']} still outstanding.\n")
                        elif order['status'] == 'PARTIALLY_FILLED':
                            remaining = float(order['origQty']) - float(order['executedQty'])
                            messages.append(f"Order {order['orderId']} submitted to {order['side']} {order['origQty']} {order['symbol']} at {order['price']}, {order['executedQty']} quantity executed with {remaining} remaining.\n")

                    return messages
                else:
                    return False

            elif status == 'executed':
                orders = client.get_orders(symbol=symbol, limit = int(limit))
                executed_orders = [order for order in orders if order['status'] in ['FILLED']]
                if len(executed_orders) != 0:
                    current_message += f'Past {limit} orders executed:\n'
                    for order in executed_orders:
                        executed_time = datetime.fromtimestamp(order['updateTime']/1000)
                        if order['type'] == 'MARKET':
                            line = f"Market order {order['orderId']} submitted to {order['side']} {order['origQty']} {order['symbol']} executed at {executed_time} with {order['executedQty']} quantity executed.\n\n"

                        elif order['type'] == 'LIMIT':
                            line = f"Limit order {order['orderId']} submitted to {order['side']} {order['origQty']} {order['symbol']} at {order['price']} executed at {executed_time} with {order['executedQty']} quantity executed.\n\n"
                        if len(current_message) + len(line) > 4096:
                            messages.append(current_message.strip())  # Add the current chunk to the list
                            current_message = line
                        else:
                            current_message += line
                    if current_message:
                        messages.append(current_message.strip())
                    return messages
                else:
                    return False

            elif status == 'cancel':
                if symbol  == 'all':
                    orders = client.get_open_orders()
                    return orders

                else:
                    orders = client.get_open_orders(symbol=symbol)
                    return orders
        else:
            return ('Failed to initialize Binance client. Please check your API key and secret.')
    except Exception as e:
        return f"Failed to retrieve orders: {str(e)}"

def cancel_orders(api_key, api_secret, symbol, order_id):
    try:
        client = Client(api_key, api_secret, base_url='https://testnet.binance.vision')
        print('cancel orders, client ok')
        if client:
                response = client.cancel_order(symbol=symbol, orderId=order_id)
                return (f"Order {response['orderId']} submitted to {response['side']} {response['origQty']} {response['symbol']}\n"
                    f"Price: {response['price']}\n"
                    f"Status: {response['status']}\n"
                    f"Executed quantity: {response['executedQty']}")
        else:
            return ('Failed to initialize Binance client. Please check your API key and secret.')
    except Exception as e:
        return f"Failed to cancel order: {e}"
