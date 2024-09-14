from binance.client import Client
from binance.exceptions import BinanceAPIException

def init_binance_client(api_key, api_secret):
    try:
        client = Client(api_key, api_secret)
        return client
    except BinanceAPIException as e:
        print(f"Error initializing Binance client: {e}")
        return None

def execute_trade(client, symbol, side, quantity):
    try:
        if side.upper() == 'BUY':
            order = client.create_order(
                symbol=symbol,
                side=Client.SIDE_BUY,
                type=Client.ORDER_TYPE_MARKET,
                quantity=quantity
            )
        elif side.upper() == 'SELL':
            order = client.create_order(
                symbol=symbol,
                side=Client.SIDE_SELL,
                type=Client.ORDER_TYPE_MARKET,
                quantity=quantity
            )
        else:
            return "Invalid side. Use 'BUY' or 'SELL'."

        return f"Order executed successfully: {order}"
    except BinanceAPIException as e:
        return f"Error executing trade: {e}"

# Add more functions for other Binance operations as needed