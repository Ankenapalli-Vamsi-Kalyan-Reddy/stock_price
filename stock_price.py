import streamlit as st
import yfinance as yf
import websocket
import json
import threading
import pandas as pd
from datetime import datetime, timedelta

# Initialize Streamlit session state
if 'symbol' not in st.session_state:
    st.session_state.symbol = "TSLA"
if 'price' not in st.session_state:
    st.session_state.price = 0.0
if 'volume' not in st.session_state:
    st.session_state.volume = 0
if 'position' not in st.session_state:
    st.session_state.position = None
if 'entry_price' not in st.session_state:
    st.session_state.entry_price = 0.0
if 'stop_loss' not in st.session_state:
    st.session_state.stop_loss = 0.0
if 'take_profit' not in st.session_state:
    st.session_state.take_profit = 0.0
if 'bar_data' not in st.session_state:
    st.session_state.bar_data = []

# Streamlit UI
st.title("Real-Time Stock Trading Bot")
symbol = st.sidebar.text_input("Enter Stock Symbol", value="TSLA")

# Placeholders for real-time updates
price_placeholder = st.empty()
volume_placeholder = st.empty()
position_placeholder = st.empty()
pnl_placeholder = st.empty()

def calculate_bar_range(data):
    return max(data) - min(data)

def check_trade_conditions(current_price):
    current_time = datetime.now()
    current_minute = current_time.minute
    bar_start = current_time.replace(minute=current_minute - (current_minute % 5), second=0, microsecond=0)
    
    if len(st.session_state.bar_data) < 2:
        return None
    
    current_bar = st.session_state.bar_data[-1]
    previous_bar = st.session_state.bar_data[-2]
    
    current_range = calculate_bar_range(current_bar['prices'])
    previous_range = calculate_bar_range(previous_bar['prices'])
    
    if current_range > previous_range and (current_time - bar_start).total_seconds() < 180:
        if current_price > current_bar['prices'][0]:
            return 'LONG'
        elif current_price < current_bar['prices'][0]:
            return 'SHORT'
    
    return None

def execute_trade(trade_type, current_price):
    st.session_state.position = trade_type
    st.session_state.entry_price = current_price
    st.session_state.stop_loss = current_price * (0.9925 if trade_type == 'LONG' else 1.0075)
    st.session_state.take_profit = current_price * (1.01 if trade_type == 'LONG' else 0.99)
    position_placeholder.write(f"Position: {st.session_state.position}")

def display_trade_details():
    if 'position' in st.session_state:  # Ensure the position exists in session state
        trade_details = {
            "Position": st.session_state.position,
            "Entry Price": st.session_state.entry_price,
            "Stop Loss": st.session_state.stop_loss,
            "Take Profit": st.session_state.take_profit
        }
        
        # Display trade details
        for key, value in trade_details.items():
            st.write(f"{key}: {value}")
    else:
        st.write("No trade executed yet.")

def check_exit_conditions(current_price):
    if st.session_state.position is None:
        return False
    
    pnl = (current_price - st.session_state.entry_price) / st.session_state.entry_price
    if st.session_state.position == 'SHORT':
        pnl = -pnl
    
    if pnl <= -0.0075:  # Stop loss at 0.75%
        st.session_state.position = None
        pnl_placeholder.write(f"Exited position. P&L: {pnl:.2%}")
        return True
    elif pnl >= 0.01 or abs(current_price - st.session_state.entry_price) >= 1.5:  # Take profit at 1% or $1.5
        
        st.session_state.position = None
        pnl_placeholder.write(f"Exited position. P&L: {pnl:.2%}") 
        return True 
    
    return False



# WebSocket callback functions
def on_message(ws, message):
    data = json.loads(message)
    if 'data' in data:
        for item in data['data']:
            if item['s'] == symbol:
                current_price = item['p']
                st.session_state.price = current_price
                st.session_state.volume = item['v']
                


                # Update Streamlit UI
                price_placeholder.write(f"Price: ${st.session_state.price:.2f}")
                volume_placeholder.write(f"Volume: {st.session_state.volume}")
                
                # Update bar data
                current_time = datetime.now()
                current_minute = current_time.minute
                bar_start = current_time.replace(minute=current_minute - (current_minute % 5), second=0, microsecond=0)
                
                if not st.session_state.bar_data or st.session_state.bar_data[-1]['start_time'] != bar_start:
                    st.session_state.bar_data.append({'start_time': bar_start, 'prices': [current_price]})
                else:
                    st.session_state.bar_data[-1]['prices'].append(current_price)
                
                # Check for trade conditions
                if st.session_state.position is None:
                    trade_signal = check_trade_conditions(current_price)
                    if trade_signal:
                        execute_trade(trade_signal, current_price)
                        display_trade_details()
                else:
                    if check_exit_conditions(current_price):
                        st.session_state.position = None
                        position_placeholder.write("No position")
                        display_trade_details()

def on_error(ws, error):
    st.error(f"WebSocket Error: {error}")

def on_close(ws):
    st.write("WebSocket connection closed")

def on_open(ws):
    ws.send(json.dumps({"type":"subscribe", "symbol": symbol}))


# Function to create WebSocket connection
def connect_websocket():
    websocket.enableTrace(True)
    ws = websocket.WebSocketApp(f"wss://ws.finnhub.io?token=ctk4pdhr01qntkqo6hngctk4pdhr01qntkqo6ho0",
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.on_open = on_open
    ws.run_forever()

# Start WebSocket connection in a separate thread
websocket_thread = threading.Thread(target=connect_websocket)
websocket_thread.start()

# Display additional stock information using yfinance
stock = yf.Ticker(symbol)
info = stock.info

st.subheader("Company Information")
st.write(f"Company Name: {info.get('longName', 'N/A')}")
st.write(f"Sector: {info.get('sector', 'N/A')}")
st.write(f"Industry: {info.get('industry', 'N/A')}")

# Display historical data
st.subheader("Historical Data")
historical_data = stock.history(period="1d", interval= "5m")
st.line_chart(historical_data['Close'])

# Display trade details below historical data
st.subheader("Trade Details")
display_trade_details()

# Keep the app running
st.empty()


