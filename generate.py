#!/usr/bin/env python3
"""Tạo ảnh kindle.png (600x800, thang xám) gồm: lịch, giá vàng, giá xăng, tin tức."""
import json
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


def get_news(n=6):
    feeds = [
        "https://vnexpress.net/rss/tin-moi-nhat.rss",
        "https://tuoitre.vn/rss/tin-moi-nhat.rss",
    ]
    for url in feeds:
        try:
            root = ET.fromstring(http_get(url))
            titles = [i.findtext("title", "").strip() for i in root.iter("item")]
            titles = [t for t in titles if t][:n]
            if titles:
                return titles
        except Exception as e:
            print("tin tức lỗi:", url, e, file=sys.stderr)
    return None


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


def render(now, lunar, gold, fuel, news, out="kindle.png"):
    img = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(img)
    pad = 24

    # --- Lịch ---
    d.text((pad, 14), THU[now.weekday()], font=font(30, True), fill=0)
    d.text((pad, 52), str(now.day), font=font(110, True), fill=0)
    d.text((190, 76), f"Tháng {now.month} / {now.year}", font=font(28), fill=0)
    if lunar:
        d.text((190, 116), lunar, font=font(22), fill=60)
    d.line((pad, 185, W - pad, 185), fill=0, width=3)

    # --- Giá vàng + giá xăng ---
    y = 198
    d.text((pad, y), "VÀNG SJC (đ/lượng)", font=font(20, True), fill=0)
    if gold:
        d.text((pad, y + 28), f"Mua {fmt_money(gold['buy'])}", font=font(30, True), fill=0)
        d.text((pad + 270, y + 28), f"Bán {fmt_money(gold['sell'])}", font=font(30, True), fill=0)
    else:
        d.text((pad, y + 28), "— chưa lấy được —", font=font(24), fill=110)

    y = 290
    d.text((pad, y), "XĂNG RON 95 (đ/lít)", font=font(20, True), fill=0)
    if fuel and fuel.get("ron95"):
        try:
            p = f"{float(fuel['ron95']):,.0f}".replace(",", ".")
        except ValueError:
            p = str(fuel["ron95"])
        d.text((pad, y + 28), p, font=font(30, True), fill=0)
    else:
        d.text((pad, y + 28), "— chưa lấy được —", font=font(24), fill=110)
    d.line((pad, 372, W - pad, 372), fill=0, width=3)

    # --- Tin tức ---
    y = 386
    d.text((pad, y), "TIN MỚI", font=font(20, True), fill=0)
    y += 32
    f_news = font(20)
    if news:
        for t in news:
            lines = wrap(d, t, f_news, W - 2 * pad - 18)[:3]
            if y + len(lines) * 26 > H - 40:
                break
            d.text((pad, y), "•", font=f_news, fill=0)
            for ln in lines:
                d.text((pad + 18, y), ln, font=f_news, fill=0)
                y += 26
            y += 10
    else:
        d.text((pad, y), "— chưa lấy được tin —", font=font(22), fill=110)

    # --- Giờ cập nhật ---
    d.text((pad, H - 30), "Cập nhật " + now.strftime("%H:%M %d/%m"), font=font(16), fill=110)

    img.save(out)  # PNG thang xám, đúng cỡ Kindle Basic 10
    print("Đã tạo", out)


if __name__ == "__main__":
    now = datetime.now(TZ)
    render(now, get_lunar(now), get_gold(), get_fuel(), get_news())
