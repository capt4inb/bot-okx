import telegram
import asyncio
import requests
from datetime import datetime

# ==================== CẤU HÌNH ====================
TELEGRAM_TOKEN = '7928253501:AAGbYEC0NXQSXb39iE-CiLk16p9C43gje2s'
CHAT_ID = '5694180372'

SCAN_INTERVAL = 70  # quét mỗi 70 giây
TOP_N = 30
# ================================================

bot = telegram.Bot(token=TELEGRAM_TOKEN)
sent_signals = {}  # chống spam: {symbol: "BUY"/"SELL"}

def get_top_30_by_volume():
    """Lấy chính xác TOP 30 coin có VOLUME 24h lớn nhất"""
    url = "https://www.okx.com/api/v5/market/tickers?instType=SWAP"
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()

        if data.get('code') != '0':
            print(f"API Error: {data.get('msg')}")
            return []

        coins = []
        for item in data['data']:
            inst_id = item.get('instId', '')
            if not inst_id.endswith('-USDT-SWAP'):
                continue

            symbol = inst_id.replace('-USDT-SWAP', '')
            volume_24h = float(item.get('volCcy24h', 0))  # Volume 24h tính bằng USDT

            if volume_24h > 0:
                coins.append({
                    'symbol': symbol,
                    'instId': inst_id,
                    'volume': volume_24h,
                    'trades': int(item.get('cnt24h', 0))
                })

        # Sắp xếp theo VOLUME 24h giảm dần → lấy TOP 30
        top_30 = sorted(coins, key=lambda x: x['volume'], reverse=True)[:TOP_N]

        print(f"ĐÃ TẢI TOP {TOP_N} COIN THEO VOLUME 24h:")
        for i, c in enumerate(top_30[:10], 1):
            print(f"  {i:2}. {c['symbol']:>8} → ${c['volume']:>15,.0f}")

        return top_30

    except Exception as e:
        print(f"Lỗi lấy TOP 30 volume: {e}")
        return []


def get_candles(inst_id, timeframe, limit=300):
    url = "https://www.okx.com/api/v5/market/candles"
    params = {'instId': inst_id, 'bar': timeframe, 'limit': str(limit)}
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        return data['data'] if data.get('code') == '0' else None
    except:
        return None


def ema(prices, period=200):
    prices = [float(p) for p in prices[-period:]]
    if len(prices) < period:
        return None
    k = 2 / (period + 1)
    ema_val = prices[0]
    for price in prices[1:]:
        ema_val = price * k + ema_val * (1 - k)
    return round(ema_val, 8)


async def send_signal(coin):
    symbol = coin['symbol']
    signal = coin['signal']
    ema200 = coin['ema200']
    volume = coin['volume']

    if sent_signals.get(symbol) == signal:
        return  # không spam

    direction = "trên" if signal == "BUY" else "dưới"
    emoji = "BUY" if signal == "BUY" else "SELL"

    msg = f"""
TÍN HIỆU MỚI - TOP 30 VOLUME 24h

{symbol}-USDT Perpetual
{emoji} **{signal}**

4 nến M5 đóng {direction} EMA200 (H1)
EMA200 H1: `{ema200}`
Volume 24h: `${volume:,.0f}` ← SIÊU KHỦNG!

Thời gian: {datetime.now().strftime('%H:%M:%S | %d/%m/%Y')}

Coin đang được ĐỔ TIỀN MẠNH NHẤT toàn sàn OKX!
    """.strip()

    try:
        await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode='Markdown')
        print(f"ĐÃ GỬI {signal} → {symbol} | Volume: ${volume:,.0f}")
        sent_signals[symbol] = signal
    except Exception as e:
        print(f"Telegram lỗi: {e}")


async def check_coin(coin):
    symbol = coin['symbol']
    inst_id = coin['instId']

    # === EMA200 từ H1 ===
    h1 = get_candles(inst_id, '1H', 250)
    if not h1 or len(h1) < 200:
        return
    closes_h1 = [float(c[4]) for c in reversed(h1[-200:])]
    ema200 = ema(closes_h1, 200)
    if not ema200:
        return

    # === 4 nến M5 mới nhất ===
    m5 = get_candles(inst_id, '5m', 10)
    if not m5 or len(m5) < 4:
        return
    closes_m5 = [float(c[4]) for c in m5[:4]]

    all_above = all(c > ema200 for c in closes_m5)
    all_below = all(c < ema200 for c in closes_m5)

    if all_above or all_below:
        coin.update({
            'signal': "BUY" if all_above else "SELL",
            'ema200': ema200
        })
        await send_signal(coin)
    else:
        if symbol in sent_signals:
            del sent_signals[symbol]  # reset khi hết điều kiện


async def scanner():
    print(f"\n{'='*75}")
    print(f"QUÉT TOP {TOP_N} COIN VOLUME 24h LỚN NHẤT TRÊN OKX")
    print(f"Thời gian: {datetime.now().strftime('%H:%M:%S | %d/%m/%Y')}")
    print(f"{'='*75}")

    top_coins = get_top_30_by_volume()
    if not top_coins:
        print("Không lấy được dữ liệu TOP 30!")
        return

    await asyncio.gather(*[check_coin(c) for c in top_coins])

    print(f"Hoàn thành quét {len(top_coins)} coin. Nghỉ {SCAN_INTERVAL}s...\n")


async def main():
    print("BOT TOP 30 VOLUME 24h + EMA200 ĐÃ KHỞI ĐỘNG!")
    print("Chỉ báo coin được ĐỔ TIỀN NHIỀU NHẤT toàn sàn!")
    print("Sẵn sàng bắt những cú pump KHỦNG!\n")

    while True:
        try:
            await scanner()
            await asyncio.sleep(SCAN_INTERVAL)
        except KeyboardInterrupt:
            print("\nBot đã dừng.")
            break
        except Exception as e:
            print(f"Lỗi hệ thống: {e}")
            await asyncio.sleep(30)


if __name__ == "__main__":
    asyncio.run(main())
