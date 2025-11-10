#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
OKX TÍN HIỆU MẠNH: HỢP LƯU EMA20/50 + MACD + RSI
→ Trên cả M15 và H1 → Gửi tất cả tín hiệu
→ Quét 100 cặp volume cao nhất
"""

import requests
import time
from datetime import datetime

# ============================= CONFIG =============================
TELEGRAM_TOKEN = '7928253501:AAGbYEC0NXQSXb39iE-CiLk16p9C43gje2s'
CHAT_ID        = '5694180372'
INTERVAL_SECONDS = 300   # 5 phút
INST_TYPE = 'SWAP'
TOP_N = 100              # Quét 100 cặp
# =================================================================

OKX_BASE_URL = 'https://www.okx.com'
TELEGRAM_URL = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}'

def send(msg):
    try:
        requests.post(f'{TELEGRAM_URL}/sendMessage', json={
            'chat_id': CHAT_ID,
            'text': msg,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True
        }, timeout=10)
    except Exception as e:
        print(f"Lỗi gửi Telegram: {e}")

def get_tickers():
    try:
        r = requests.get(f'{OKX_BASE_URL}/api/v5/market/tickers?instType={INST_TYPE}', timeout=10)
        data = r.json()
        if data.get('code') == '0':
            return data.get('data', [])
    except Exception as e:
        print(f"Lỗi lấy tickers: {e}")
    return []

def get_candles(inst_id, bar, limit=200):
    try:
        r = requests.get(f'{OKX_BASE_URL}/api/v5/market/candles', params={
            'instId': inst_id, 'bar': bar, 'limit': limit
        }, timeout=10)
        data = r.json()
        if data.get('code') == '0':
            return data.get('data', [])
    except:
        return []
    return []

# === EMA ===
def ema(prices, period):
    if len(prices) < period:
        return 0.0
    k = 2 / (period + 1)
    ema_val = sum(prices[:period]) / period
    for p in prices[period:]:
        ema_val = p * k + ema_val * (1 - k)
    return round(ema_val, 8)

# === RSI ===
def rsi(prices, period=14):
    if len(prices) < period + 1:
        return 50.0
    gains = [max(prices[i] - prices[i-1], 0) for i in range(1, len(prices))]
    losses = [max(prices[i-1] - prices[i], 0) for i in range(1, len(prices))]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)

# === MACD ===
def macd_signal(prices, fast=12, slow=26, signal=9):
    if len(prices) < slow + signal:
        return 0.0, 0.0
    ema_fast = ema(prices, fast)
    ema_slow = ema(prices, slow)
    macd_line = ema_fast - ema_slow
    macd_values = []
    for i in range(slow, len(prices)):
        f = ema(prices[:i+1], fast)
        s = ema(prices[:i+1], slow)
        macd_values.append(f - s)
    if len(macd_values) < signal:
        return 0.0, 0.0
    signal_line = ema(macd_values[-signal:], signal)
    return macd_line, signal_line

# === Phân tích 1 khung ===
def analyze_frame(closes):
    if len(closes) < 60:
        return None

    # EMA 20 & 50
    ema20_now = ema(closes, 20)
    ema50_now = ema(closes, 50)
    ema20_prev = ema(closes[:-1], 20)
    ema50_prev = ema(closes[:-1], 50)

    # MACD
    macd_now, signal_now = macd_signal(closes, 12, 26, 9)
    macd_prev, signal_prev = macd_signal(closes[:-1], 12, 26, 9)

    # RSI
    current_rsi = rsi(closes)

    # Cắt EMA
    ema_up = ema20_prev <= ema50_prev and ema20_now > ema50_now
    ema_down = ema20_prev >= ema50_prev and ema20_now < ema50_now

    # Cắt MACD
    macd_up = macd_prev <= signal_prev and macd_now > signal_now
    macd_down = macd_prev >= signal_prev and macd_now < signal_now

    if ema_up and macd_up and current_rsi > 50:
        return {"signal": "BUY", "rsi": current_rsi}
    if ema_down and macd_down and current_rsi < 50:
        return {"signal": "SELL", "rsi": current_rsi}
    return None

# === Phân tích cặp giao dịch ===
def get_signal(inst_id):
    # Lấy nến M15
    klines_m15 = get_candles(inst_id, '15m', 200)
    if len(klines_m15) < 60:
        return None
    klines_m15 = klines_m15[::-1]
    closes_m15 = [float(k[4]) for k in klines_m15]

    # Lấy nến H1
    klines_h1 = get_candles(inst_id, '1H', 200)
    if len(klines_h1) < 60:
        return None
    klines_h1 = klines_h1[::-1]
    closes_h1 = [float(k[4]) for k in klines_h1]

    # Phân tích M15
    result_m15 = analyze_frame(closes_m15)
    if not result_m15:
        return None

    # Phân tích H1
    result_h1 = analyze_frame(closes_h1)
    if not result_h1:
        return None

    # Hợp lưu 2 khung
    if result_m15['signal'] == result_h1['signal']:
        price = closes_h1[-1]
        return {
            "symbol": inst_id,
            "signal": result_m15['signal'],
            "price": price,
            "rsi_m15": result_m15['rsi'],
            "rsi_h1": result_h1['rsi']
        }
    return None

def main():
    print("Bot Hợp Lưu M15 + H1 (EMA+MACD+RSI) khởi động...")
    send("<b>Bot Hợp Lưu M15 + H1 (EMA20/50 + MACD + RSI) đã khởi động!</b>")

    while True:
        try:
            tickers = get_tickers()
            if not tickers:
                send("Lỗi kết nối OKX.")
                time.sleep(60)
                continue

            top100 = sorted(tickers, key=lambda x: float(x['volCcy24h']), reverse=True)[:TOP_N]
            signals = []

            print(f"Đang quét {len(top100)} cặp (M15 + H1)...")
            for idx, t in enumerate(top100, 1):
                inst_id = t['instId']
                print(f"  [{idx}/100] {inst_id}", end="\r")
                sig = get_signal(inst_id)
                if sig:
                    sig['vol'] = float(t['volCcy24h']) / 1_000_000
                    signals.append(sig)
                time.sleep(0.12)

            signals = sorted(signals, key=lambda x: x['vol'], reverse=True)

            if not signals:
                send("<b>Hiện tại không có tín hiệu hợp lưu M15 + H1 nào.</b>")
            else:
                msg = f"<b>TÍN HIỆU HỢP LƯU M15 + H1 ({len(signals)} cặp)</b>\n\n"
                for i, s in enumerate(signals, 1):
                    icon = "BUY" if s['signal'] == "BUY" else "SELL"
                    msg += f"<b>{i}. {s['symbol']}</b>\n"
                    msg += f"   {icon} <code>{s['price']:.4f}</code>\n"
                    msg += f"   RSI: <b>M15={s['rsi_m15']}</b> | <b>H1={s['rsi_h1']}</b>\n"
                    msg += f"   Vol: <b>{s['vol']:.1f}M</b>\n\n"
                send(msg.strip())

            print(f"\nGửi {len(signals)} tín hiệu hợp lưu M15+H1")
            time.sleep(INTERVAL_SECONDS)

        except KeyboardInterrupt:
            send("Bot đã dừng.")
            print("\nBot dừng.")
            break
        except Exception as e:
            print(f"Lỗi: {e}")
            time.sleep(60)

if __name__ == '__main__':
    send("Kiểm tra bot hợp lưu M15+H1...")
    main()
