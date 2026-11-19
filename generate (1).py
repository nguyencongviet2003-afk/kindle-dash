#!/usr/bin/env python3
"""Tạo ảnh kindle.png (600x800, thang xám) gồm: lịch, giá vàng, giá xăng, tin tức."""
import html
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

W, H = 600, 800
TZ = ZoneInfo("Asia/Ho_Chi_Minh")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
UA = {"User-Agent": "Mozilla/5.0 (kindle-dash)"}

THU = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]


def font(size, bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT, size)


def http_get(url, headers=None, timeout=15):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


# ---------- Lấy dữ liệu (mỗi hàm lỗi thì trả None, ảnh vẫn được tạo) ----------

def get_lunar(now):
    try:
        from lunardate import LunarDate
        d = LunarDate.fromSolarDate(now.year, now.month, now.day)
        return f"Âm lịch: {d.day}/{d.month}" + (" (nhuận)" if d.isLeapMonth else "")
    except Exception as e:
        print("lunar lỗi:", e, file=sys.stderr)
        return None


def get_gold():
    """Giá vàng SJC từ vapi.vnappmob.com (cần xin key miễn phí tự động)."""
    try:
        key = json.loads(http_get(
            "https://vapi.vnappmob.com/api/request_api_key?scope=gold"))["results"]
        data = json.loads(http_get(
            "https://vapi.vnappmob.com/api/v2/gold/sjc",
            headers={"Authorization": f"Bearer {key}"}))
        row = data["results"][0]
        buy, sell = float(row["buy_1l"]), float(row["sell_1l"])
        return {"buy": buy, "sell": sell}
    except Exception as e:
        print("vàng lỗi:", e, file=sys.stderr)
        return None


def get_fuel():
    """Giá xăng RON 95 vùng 1 từ wifeed (khóa demo, có thể bị giới hạn)."""
    try:
        data = json.loads(http_get(
            "https://wifeed.vn/api/du-lieu-vimo/hang-hoa/gia-xang-dau-trong-nuoc"
            "?page=1&limit=1&apikey=demo"))
        return {"ron95": data["data"][0]["vung_1_xang_ron_95_v"]}
    except Exception as e:
        print("xăng lỗi:", e, file=sys.stderr)
        return None


def _clean(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def get_news(n=10):
    """Trả về danh sách (tiêu đề, tóm tắt)."""
    feeds = [
        "https://vnexpress.net/rss/tin-moi-nhat.rss",
        "https://tuoitre.vn/rss/tin-moi-nhat.rss",
    ]
    for url in feeds:
        try:
            root = ET.fromstring(http_get(url))
            items = []
            for i in root.iter("item"):
                title = _clean(i.findtext("title", ""))
                desc = _clean(i.findtext("description", ""))
                if title:
                    items.append((title, desc))
            if items:
                return items[:n]
        except Exception as e:
            print("tin tức lỗi:", url, e, file=sys.stderr)
    return None


# Vị trí để xem dự báo thời tiết (Cẩm Phả, Quảng Ninh). Đổi số nếu muốn nơi khác.
LAT, LON, PLACE = 21.0, 107.3, "Cẩm Phả"

WMO = {0: "Trời quang", 1: "Ít mây", 2: "Có mây", 3: "Nhiều mây", 45: "Sương mù", 48: "Sương mù",
       51: "Mưa phùn", 53: "Mưa phùn", 55: "Mưa phùn", 56: "Mưa phùn lạnh", 57: "Mưa phùn lạnh",
       61: "Mưa nhỏ", 63: "Mưa vừa", 65: "Mưa to", 66: "Mưa lạnh", 67: "Mưa lạnh",
       71: "Tuyết", 73: "Tuyết", 75: "Tuyết", 77: "Tuyết", 80: "Mưa rào", 81: "Mưa rào",
       82: "Mưa rào to", 85: "Tuyết", 86: "Tuyết", 95: "Dông", 96: "Dông, mưa đá", 99: "Dông, mưa đá"}


def get_weather():
    """Dự báo từ Open-Meteo (miễn phí, không cần khóa)."""
    try:
        url = ("https://api.open-meteo.com/v1/forecast"
               f"?latitude={LAT}&longitude={LON}"
               "&current=temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m"
               "&daily=weather_code,temperature_2m_max,temperature_2m_min,"
               "precipitation_probability_max,wind_speed_10m_max,uv_index_max"
               "&timezone=Asia%2FBangkok&forecast_days=4")
        return json.loads(http_get(url))
    except Exception as e:
        print("thời tiết lỗi:", e, file=sys.stderr)
        return None


def yahoo_quote(symbol):
    """Trả về (giá, % thay đổi) từ Yahoo Finance, hoặc None."""
    try:
        data = json.loads(http_get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1d"))
        meta = data["chart"]["result"][0]["meta"]
        price = float(meta["regularMarketPrice"])
        prev = float(meta.get("chartPreviousClose") or meta.get("previousClose"))
        return price, (price - prev) / prev * 100
    except Exception as e:
        print(f"yahoo {symbol} lỗi:", e, file=sys.stderr)
        return None


def vnindex_vietcap():
    """Dự phòng: VN-Index từ API của Vietcap."""
    try:
        body = json.dumps({"timeFrame": "ONE_DAY", "symbols": ["VNINDEX"],
                           "to": int(datetime.now().timestamp()) + 86400, "countBack": 3}).encode()
        req = urllib.request.Request(
            "https://trading.vietcap.com.vn/api/chart/OHLCChart/gap-chart", data=body,
            headers={**UA, "Content-Type": "application/json",
                     "Origin": "https://trading.vietcap.com.vn",
                     "Referer": "https://trading.vietcap.com.vn/"})
        with urllib.request.urlopen(req, timeout=15) as r:
            row = json.loads(r.read().decode())[0]
        c = [float(x) for x in row["c"]]
        price, prev = c[-1], c[-2]
        if price < 100:  # có API trả về đơn vị nghìn
            price, prev = price * 1000, prev * 1000
        return price, (price - prev) / prev * 100
    except Exception as e:
        print("vnindex vietcap lỗi:", e, file=sys.stderr)
        return None


def get_markets():
    """Danh sách (nhãn, giá, %, đơn vị) cho thị trường thế giới."""
    vni = yahoo_quote("%5EVNINDEX") or vnindex_vietcap()
    rows = [
        ("Vàng TG", yahoo_quote("GC=F"), "$/oz", 0),
        ("Dầu Brent", yahoo_quote("BZ=F"), "$", 2),
        ("Bitcoin", yahoo_quote("BTC-USD"), "$", 0),
        ("VN-Index", vni, "", 2),
        ("Dow Jones", yahoo_quote("%5EDJI"), "", 0),
        ("Nikkei 225", yahoo_quote("%5EN225"), "", 0),
    ]
    return rows


# ---------- Vẽ ảnh ----------

def wrap(draw, text, fnt, max_w):
    lines, cur = [], ""
    for word in text.split():
        test = (cur + " " + word).strip()
        if draw.textlength(test, font=fnt) <= max_w:
            cur = test
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def fmt_money(v):
    """92500000 -> '92,5 tr'  (triệu đồng/lượng)"""
    return f"{v / 1_000_000:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".") + " tr"


def fmt_num(v, dec=0):
    """1234567.891 -> '1.234.567,89' (kiểu Việt Nam)."""
    t = f"{v:,.{dec}f}"
    return t.replace(",", "X").replace(".", ",").replace("X", ".")


def render(now, lunar, gold, fuel, news, weather=None, markets=None, out="kindle.png"):
    img = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(img)
    pad = 20

    # ===== Khối 1: Lịch (trái) + thời tiết chi tiết (phải) =====
    d.text((pad, 8), THU[now.weekday()], font=font(24, True), fill=0)
    d.text((pad, 34), str(now.day), font=font(96, True), fill=0)
    d.text((pad, 140), f"Tháng {now.month}/{now.year}", font=font(20), fill=0)
    if lunar:
        d.text((pad, 166), lunar, font=font(16), fill=70)

    xw = 250
    d.line((xw - 14, 10, xw - 14, 190), fill=150, width=1)
    if weather:
        try:
            cur, day = weather["current"], weather["daily"]
            d.text((xw, 8), PLACE.upper(), font=font(15, True), fill=0)
            d.text((xw, 26), f"{cur['temperature_2m']:.0f}°C", font=font(44, True), fill=0)
            d.text((xw + 124, 32), WMO.get(cur["weather_code"], "—"), font=font(18, True), fill=0)
            d.text((xw + 124, 56), f"Cảm giác {cur['apparent_temperature']:.0f}°", font=font(15), fill=60)
            d.text((xw, 82), f"Hôm nay {day['temperature_2m_min'][0]:.0f}° - {day['temperature_2m_max'][0]:.0f}°"
                             f"   Mưa {day['precipitation_probability_max'][0]}%", font=font(16, True), fill=0)
            d.text((xw, 104), f"Ẩm {cur['relative_humidity_2m']}%   Gió {cur['wind_speed_10m']:.0f} km/h"
                              f"   UV {day['uv_index_max'][0]:.0f}", font=font(15), fill=60)
            d.line((xw, 128, W - pad, 128), fill=150, width=1)
            names = ["Mai"] + [THU[(now.weekday() + i) % 7] for i in (2, 3)]
            for i in range(1, 4):
                yy = 134 + (i - 1) * 19
                d.text((xw, yy), f"{names[i-1]}", font=font(14, True), fill=0)
                d.text((xw + 100, yy), f"{day['temperature_2m_min'][i]:.0f}-{day['temperature_2m_max'][i]:.0f}°"
                                      f"  Mưa {day['precipitation_probability_max'][i]}%", font=font(14), fill=0)
                d.text((xw + 235, yy), WMO.get(day["weather_code"][i], ""), font=font(13), fill=60)
        except Exception as e:
            print("vẽ thời tiết lỗi:", e, file=sys.stderr)
            d.text((xw, 70), "— thời tiết lỗi —", font=font(18), fill=110)
    else:
        d.text((xw, 70), "— chưa lấy được thời tiết —", font=font(18), fill=110)
    d.line((pad, 194, W - pad, 194), fill=0, width=3)

    # ===== Khối 2: vàng + xăng trong nước =====
    y = 202
    d.text((pad, y), "VÀNG SJC (đ/lượng)", font=font(15, True), fill=0)
    if gold:
        d.text((pad, y + 20), f"Mua {fmt_money(gold['buy'])}   Bán {fmt_money(gold['sell'])}",
               font=font(22, True), fill=0)
    else:
        d.text((pad, y + 22), "— chưa lấy được —", font=font(18), fill=110)
    x2 = 380
    d.text((x2, y), "XĂNG RON 95", font=font(15, True), fill=0)
    if fuel and fuel.get("ron95"):
        try:
            p = f"{float(fuel['ron95']):,.0f}".replace(",", ".")
        except ValueError:
            p = str(fuel["ron95"])
        d.text((x2, y + 20), p + " đ", font=font(22, True), fill=0)
    else:
        d.text((x2, y + 22), "— chưa có —", font=font(18), fill=110)
    d.line((pad, 256, W - pad, 256), fill=0, width=3)

    # ===== Khối 3: thị trường thế giới (2 cột x 3 hàng) =====
    y = 260
    d.text((pad, y), "THỊ TRƯỜNG", font=font(15, True), fill=0)
    y += 18
    col_w = (W - 2 * pad) // 2
    for i, (label, q, unit, dec) in enumerate(markets or []):
        cx = pad + (i % 2) * col_w
        cy = y + (i // 2) * 38
        d.text((cx, cy), label, font=font(14), fill=70)
        if q:
            price, pct = q
            arrow = "▲" if pct >= 0 else "▼"
            d.text((cx, cy + 15), fmt_num(price, dec), font=font(19, True), fill=0)
            vx = cx + d.textlength(fmt_num(price, dec), font=font(19, True)) + 8
            d.text((vx, cy + 19), f"{arrow}{abs(pct):.1f}%", font=font(14, True), fill=0)
        else:
            d.text((cx, cy + 17), "— chưa lấy được —", font=font(15), fill=110)
    d.line((pad, 402, W - pad, 402), fill=0, width=3)

    # ===== Khối 4: tin tức =====
    y = 410
    d.text((pad, y), "TIN MỚI", font=font(15, True), fill=0)
    y += 22
    f_title, f_desc = font(15, True), font(14)
    lh_t, lh_d = 19, 18
    text_w = W - 2 * pad - 14
    bottom = H - 30
    if news:
        for title, desc in news:
            t_lines = wrap(d, title, f_title, text_w)[:2]
            d_lines = wrap(d, desc, f_desc, text_w)[:2] if desc and desc != title else []
            need = len(t_lines) * lh_t + len(d_lines) * lh_d + 6
            if y + need > bottom:
                d_lines = d_lines[:max(0, (bottom - y - len(t_lines) * lh_t - 6) // lh_d)]
                need = len(t_lines) * lh_t + len(d_lines) * lh_d + 6
                if y + need > bottom:
                    break
            d.text((pad, y), "•", font=f_title, fill=0)
            for ln in t_lines:
                d.text((pad + 14, y), ln, font=f_title, fill=0)
                y += lh_t
            for ln in d_lines:
                d.text((pad + 14, y), ln, font=f_desc, fill=70)
                y += lh_d
            y += 6
    else:
        d.text((pad, y), "— chưa lấy được tin —", font=font(18), fill=110)

    d.text((pad, H - 22), "Cập nhật " + now.strftime("%H:%M %d/%m"), font=font(13), fill=110)
    img.save(out)
    print("Đã tạo", out)


if __name__ == "__main__":
    now = datetime.now(TZ)
    render(now, get_lunar(now), get_gold(), get_fuel(), get_news(),
           get_weather(), get_markets())
