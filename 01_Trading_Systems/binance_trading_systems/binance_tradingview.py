import os
import logging
from logging.handlers import RotatingFileHandler
import time
import csv
import math
import re
import base64

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from binance.client import Client
from binance.exceptions import BinanceAPIException

from bs4 import BeautifulSoup
from colorama import init, Fore, Style

# Suppress Deprecation Warnings
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Initialize colorama for colored console output
init(autoreset=True)

# Configure Logging with RotatingFileHandler and StreamHandler
logger = logging.getLogger('TradingViewEmailFetcher')
logger.setLevel(logging.DEBUG)  # Set to DEBUG to capture all levels of logs
logger.handlers.clear()

# File Handler - Rotates logs after reaching 5MB, keeps 5 backups
file_handler = RotatingFileHandler('tradingview_email_fetcher.log', maxBytes=5*1024*1024, backupCount=5)
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Console Handler - Outputs logs to console
console_handler = logging.StreamHandler()
console_formatter = logging.Formatter('%(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# Google API credentials (Use environment variables for security in real applications)
CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '92914340222-bucu7u4ts7i33n2o2qa740s3nma2gfkg.apps.googleusercontent.com')
CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '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')
REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost')
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# Binance API Credentials (Use environment variables for security in real applications)
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY', 'XUqrB8vpc0jF1hEZEzCLZw6zVdD8KFkRsPjHM12cPrS3OZ7XMBbgn3ca7HDhqsH2')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET', '1Y33KWMMFgfdzl9L9SIx2nm00hF9xdvppJwCkKMSUHG5XvmngYfSlucG492TEhLW')

def make_binance_client():
    if not BINANCE_API_KEY or not BINANCE_API_SECRET:
        logger.error("Missing Binance API credentials. Set BINANCE_API_KEY and BINANCE_API_SECRET.")
        return None
    try:
        return Client(BINANCE_API_KEY, BINANCE_API_SECRET)
    except Exception as e:
        logger.error(f"Failed to initialize Binance client: {e}")
        return None

binance_client = make_binance_client()

TRADE_USDT_AMOUNT = float(os.getenv('TRADE_USDT_AMOUNT',50))  # Default to $242 if not set
POLL_SECONDS = float(os.getenv('POLL_SECONDS', '1'))

# Track processed message IDs to prevent duplicate processing
processed_message_ids = set()

# CSV file to log processed signals
CSV_FILE = 'processed_signals.csv'

# Load processed message IDs from CSV
if os.path.exists(CSV_FILE):
    try:
        with open(CSV_FILE, mode='r') as file:
            reader = csv.reader(file)
            for row in reader:
                if row:
                    processed_message_ids.add(row[0])
        logger.info("Loaded processed message IDs from CSV.")
    except Exception as e:
        logger.error(f"Error loading processed message IDs: {e}")

# -------------------------------
# Utility Functions
# -------------------------------

def display_banner():
    banner = r"""
     _____         _           _      _         _                  
    |  __ \       | |         | |    | |       | |                 
    | |__) |__  __| |_ __ ___ | |__  | | ___   | |_ ___  _ __ ___ 
    |  ___/ _ \/ _` | '__/ _ \| '_ \ | |/ _ \  | __/ _ \| '__/ __|
    | |  |  __/ (_| | | | (_) | | | || | (_) | | || (_) | |  \__ \
    |_|   \___|\__,_|_|  \___/|_| |_|/ |\___/   \__\___/|_|  |___/
                                   |__/                            
    """
    print(Fore.CYAN + banner + Style.RESET_ALL)

def authenticate_gmail():
    """Authenticate the user and return the Gmail service."""
    if not CLIENT_ID or not CLIENT_SECRET:
        logger.error("Missing Google OAuth credentials. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.")
        return None

    creds = None
    token_file = 'token.json'

    if os.path.exists(token_file):
        try:
            creds = Credentials.from_authorized_user_file(token_file, SCOPES)
            logger.info("Loaded Gmail credentials from token file.")
        except Exception as e:
            logger.error(f"Error loading credentials: {e}")
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                logger.info("Refreshed Gmail credentials.")
            except Exception as e:
                logger.error(f"Failed to refresh Gmail credentials: {e}")
                creds = None
        if not creds:
            try:
                flow = InstalledAppFlow.from_client_config(
                    {
                        "installed": {
                            "client_id": CLIENT_ID,
                            "client_secret": CLIENT_SECRET,
                            "redirect_uris": [REDIRECT_URI],
                            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                            "token_uri": "https://oauth2.googleapis.com/token"
                        }
                    },
                    SCOPES
                )
                creds = flow.run_local_server(port=0)
                logger.info("Obtained new Gmail credentials via OAuth.")
            except Exception as e:
                logger.error(f"Failed to obtain Gmail credentials: {e}")
                return None

        if creds:
            try:
                with open(token_file, 'w') as token:
                    token.write(creds.to_json())
                logger.info("Saved Gmail credentials to token file.")
            except Exception as e:
                logger.error(f"Failed to save Gmail credentials: {e}")

    try:
        service = build('gmail', 'v1', credentials=creds)
        logger.info("Authenticated with Gmail.")
        return service
    except HttpError as error:
        logger.error(f"Error building Gmail service: {error}")
        return None


def get_email_body(payload):
    """Recursively extract the email body."""
    if 'parts' in payload:
        for part in payload['parts']:
            body = get_email_body(part)
            if body:
                return body
    else:
        if payload.get('mimeType') == 'text/plain' and 'data' in payload.get('body', {}):
            data = payload['body']['data']
            return base64.urlsafe_b64decode(data).decode('utf-8')
        elif payload.get('mimeType') == 'text/html' and 'data' in payload.get('body', {}):
            data = payload['body']['data']
            decoded_data = base64.urlsafe_b64decode(data).decode('utf-8')
            soup = BeautifulSoup(decoded_data, 'html.parser')
            return soup.get_text(separator='\n')
    return ""


def parse_signal(email_body):
    """Parse trading signals from the email body."""
    try:
        lines = email_body.strip().split('\n')
        lines = [line.strip() for line in lines if line.strip()]
        trading_pair, signal_type, price = None, None, None

        for line in lines:
            if 'Order Type:' in line:
                signal_type = line.split('Order Type:')[1].strip().capitalize()
            elif 'Asset:' in line:
                trading_pair = line.split('Asset:')[1].strip().upper().replace('/', '').replace('-', '')
            elif 'Price:' in line:
                price_str = line.split('Price:')[1].strip()
                price_matches = re.findall(r'[\d.]+', price_str)
                price = float(price_matches[0]) if price_matches else None

        if trading_pair and signal_type and price:
            logger.debug(f"Parsed Signal: {trading_pair}, {signal_type}, {price}")
            return trading_pair, signal_type, price
        else:
            logger.warning("Incomplete signal, skipping.")
            return None, None, None
    except Exception as e:
        logger.error(f"Error parsing signal: {e}")
        return None, None, None


def calculate_order_quantity(trading_pair, usdt_amount=5.0):
    """
    Calculate the order quantity based on the trading pair and USDT amount.
    """
    try:
        if binance_client is None:
            logger.error("Binance client is not initialized.")
            return None

        # Fetch the current mark price for the trading pair
        mark_price_data = binance_client.futures_mark_price(symbol=trading_pair)
        current_price = float(mark_price_data['markPrice'])
        logger.debug(f"Current price for {trading_pair}: {current_price}")

        # Calculate initial quantity
        quantity = usdt_amount / current_price
        logger.debug(f"Initial quantity for ${usdt_amount} at price {current_price}: {quantity}")

        # Fetch exchange information for filters
        symbol_info = binance_client.futures_exchange_info()
        step_size = 3
        min_notional = 5.0

        # Find the trading pair in the exchange info
        for symbol in symbol_info['symbols']:
            if symbol['symbol'] == trading_pair:
                logger.debug(f"Found symbol info for {trading_pair}")
                for filt in symbol['filters']:
                    if filt['filterType'] == 'LOT_SIZE':
                        step_size = float(filt['stepSize'])
                        logger.debug(f"Step size for {trading_pair}: {step_size}")
                    elif filt['filterType'] == 'MIN_NOTIONAL':
                        min_notional = float(filt['notional'])
                        logger.debug(f"Min notional for {trading_pair}: {min_notional}")
                break

        # Ensure the necessary filters were found
        if not step_size or not min_notional:
            logger.error(f"Step size or min notional not found for {trading_pair}.")
            return None

        # Adjust quantity to the step size
        quantity = math.floor(quantity / step_size) * step_size
        logger.debug(f"Adjusted quantity after applying step size: {quantity}")

        # Check if the quantity meets the minimum notional requirement
        trade_value = quantity * current_price
        if trade_value < min_notional:
            logger.error(f"Trade value ${trade_value:.2f} is below the minimum notional ${min_notional:.2f} for {trading_pair}.")
            return None

        return quantity
    except BinanceAPIException as e:
        logger.error(f"Binance API Exception: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in calculate_order_quantity: {e}")
        return None



def execute_market_order(trading_pair, signal_type, usdt_amount=20.0):
    """Place a market order for the given signal."""
    try:
        if binance_client is None:
            logger.error("Binance client is not initialized.")
            return

        logger.info(f"Processing {signal_type} signal for {trading_pair} with ${usdt_amount}.")

        # Determine the side and position side based on the signal type
        if signal_type.lower() == 'buy':
            new_side = 'BUY'
            new_position_side = 'LONG'
            opposite_position_side = 'SHORT'
        else:
            new_side = 'SELL'
            new_position_side = 'SHORT'
            opposite_position_side = 'LONG'

        # Fetch current positions for the trading pair
        positions = binance_client.futures_position_information(symbol=trading_pair)
        logger.debug(f"Current positions for {trading_pair}: {positions}")

        # Check if there's an open opposite position
        for position in positions:
            if position['positionSide'] == opposite_position_side and float(position['positionAmt']) != 0:
                # Close the opposite position
                quantity_to_close = abs(float(position['positionAmt']))
                logger.info(f"Closing opposite position: {opposite_position_side} {quantity_to_close} {trading_pair}")
                close_order_params = {
                    'symbol': trading_pair,
                    'side': 'BUY' if opposite_position_side == 'SHORT' else 'SELL',
                    'positionSide': opposite_position_side,
                    'type': 'MARKET',
                    'quantity': quantity_to_close 
                }
                close_order = binance_client.futures_create_order(**close_order_params)
                logger.info(f"Closed opposite position: {close_order}")

        # Calculate quantity for the new position
        quantity = calculate_order_quantity(trading_pair, usdt_amount)
        if not quantity:
            logger.error(f"Failed to calculate order quantity for {trading_pair}.")
            return

        # Open the new position
        logger.info(f"Opening new position: {new_position_side} {quantity} {trading_pair}")
        new_order_params = {
            'symbol': trading_pair,
            'side': new_side,
            'positionSide': new_position_side,
            'type': 'MARKET',
            'quantity': quantity
        }
        new_order = binance_client.futures_create_order(**new_order_params)
        logger.info(f"Opened new position: {new_order}")

    except BinanceAPIException as e:
        logger.error(f"Binance API Exception: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")




def fetch_latest_email(service):
    """Fetch the latest TradingView email and place an order."""
    try:
        query = 'from:noreply@tradingview.com subject:Alert "TRADING_SIGNAL"'
        results = service.users().messages().list(userId='me', q=query, maxResults=1).execute()
        messages = results.get('messages', [])

        if not messages:
            logger.info("No new alerts.")
            return

        message = messages[0]
        msg_id = message['id']
        msg = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
        email_body = get_email_body(msg['payload'])

        trading_pair, signal_type, price = parse_signal(email_body)

        if trading_pair and signal_type:
            if msg_id not in processed_message_ids:
                execute_market_order(trading_pair, signal_type, usdt_amount=TRADE_USDT_AMOUNT)
                processed_message_ids.add(msg_id)
                with open(CSV_FILE, mode='a', newline='') as file:
                    writer = csv.writer(file)
                    writer.writerow([msg_id])
    except Exception as e:
        logger.error(f"Error fetching latest email: {e}")


def main():
    """Main execution loop."""
    display_banner()
    logger.info("Starting TradingView Email Fetcher...")
    service = authenticate_gmail()
    if not service:
        logger.error("Failed to authenticate Gmail. Exiting.")
        return

    while True:
        fetch_latest_email(service)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main() 