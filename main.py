import os
import httpx
import anthropic
from flask import Flask, request, abort, send_from_directory, jsonify
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, PushMessageRequest,
    TextMessage, FlexMessage, FlexContainer
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, JoinEvent
from linebot.v3.exceptions import InvalidSignatureError
from datetime import datetime, timedelta
import threading
import schedule
import time
import pytz

app = Flask(__name__)

LINE_CHANNEL_SECRET       = os.environ.get("LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
ANTHROPIC_API_KEY         = os.environ.get("ANTHROPIC_API_KEY", "")
GROUP_ID                  = os.environ.get("LINE_GROUP_ID", "")

handler       = WebhookHandler(LINE_CHANNEL_SECRET)
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, http_client=httpx.Client())

THAI_TZ = pytz.timezone("Asia/Bangkok")

DAY_DATA = {
    "จันทร์":    {"element": "น้ำ 💧", "color": "ขาว/เงิน",    "food": "ปลา/อาหารทะเล",          "bg": "#4A90D9", "btn": "#2C6FAC"},
    "อังคาร":   {"element": "ไฟ 🔥",  "color": "แดง/ชมพู",    "food": "ขิง/พริก/อาหารร้อน",     "bg": "#C0392B", "btn": "#96281B"},
    "พุธ":      {"element": "ดิน 🌿", "color": "เขียว",        "food": "ผัก/สมุนไพร",             "bg": "#27AE60", "btn": "#1E8449"},
    "พฤหัสบดี": {"element": "ไม้ 🌳", "color": "ส้ม/เหลือง",  "food": "ข้าวโพด/ถั่ว",            "bg": "#8E44AD", "btn": "#6C3483"},
    "ศุกร์":    {"element": "โลหะ ✨","color": "ฟ้า/น้ำเงิน", "food": "ดอกไม้/อาหารหวาน",        "bg": "#E91E8C", "btn": "#B5176C"},
    "เสาร์":    {"element": "ดิน 🪨", "color": "ม่วง/ดำ",     "food": "เห็ด/ราก/หัว",            "bg": "#2C3E50", "btn": "#1A252F"},
    "อาทิตย์":  {"element": "ไฟ ☀️", "color": "ทอง/เหลือง",  "food": "น้ำผึ้ง/อาหารสีเหลือง",  "bg": "#E67E22", "btn": "#CA6F1E"},
}
DAYS_TH = ["จันทร์","อังคาร","พุธ","พฤหัสบดี","ศุกร์","เสาร์","อาทิตย์"]

def get_day_info(offset_days=0):
    now = datetime.now(THAI_TZ) + timedelta(days=offset_days)
    day_name = DAYS_TH[now.weekday()]
    d = DAY_DATA[day_name]
    return {"date": now.strftime("%d/%m/%Y"), "day": day_name,
            "element": d["element"], "lucky_color": d["color"],
            "lucky_food": d["food"], "bg": d["bg"], "btn": d["btn"]}

def generate_daily_fortune(day_info):
    prompt = f"""คุณคือ "บุญดวง" หมอดูขี้บ่นสุดกวน แต่ใจดีลึกๆ เชี่ยวชาญศาสตร์โบราณทั้งไทย จีน และตะวันตก
วันนี้คือวัน{day_info['day']} ที่ {day_info['date']}
ธาตุ: {day_info['element']} | สีมงคล: {day_info['lucky_color']} | อาหารมงคล: {day_info['lucky_food']}

สร้างดวงรายวันแบบกวนๆ ครอบคลุม:
1. 🔮 ภาพรวมพลังงานวันนี้ (อ้างอิงโหราศาสตร์ไทยหรือจีน พูดแบบกวนนิดๆ)
2. 💼 การงาน/การเงิน (1-2 ประโยค)
3. ❤️ ความรัก (1-2 ประโยค)
4. 🌿 สุขภาพ + อาหารมงคลจากแพทย์แผนจีน/ไทย
5. 🙏 กรรมดีง่ายๆ 1 ข้อ ทำได้จริงวันนี้เลย
6. ⚠️ ระวัง 1 ข้อ (พูดแบบขู่กวนๆ)
ภาษาไทย อ่านสนุก ไม่เกิน 250 คำ"""
    msg = claude_client.messages.create(model="claude-opus-4-5", max_tokens=700,
        messages=[{"role": "user", "content": prompt}])
    return msg.content[0].text

def generate_answer_fortune(question):
    day_info = get_day_info()
    prompt = f"""คุณคือ "บุญดวง" หมอดูขี้บ่นสุดกวน เชี่ยวชาญ I-Ching และเซียมซีไทย
วันนี้วัน{day_info['day']} ธาตุ{day_info['element']}
คำถาม: "{question}"
ตีความแบบกวนๆ:
1. 🎴 ผล: ดีมาก/ดี/กลางๆ/ระวัง (เลือก 1 แล้วบ่นนิดๆ)
2. 📖 คำทำนาย (3-4 ประโยค กวนๆ แต่มีสาระ)
3. 💡 คำแนะนำ
4. 🙏 กรรมดีเสริมดวง 1 ข้อ
ภาษาไทย ไม่เกิน 150 คำ"""
    msg = claude_client.messages.create(model="claude-opus-4-5", max_tokens=400,
        messages=[{"role": "user", "content": prompt}])
    return msg.content[0].text

def generate_karma():
    day_info = get_day_info()
    prompt = f"""คุณคือ "บุญดวง" หมอดูขี้บ่นสุดกวน
วันนี้วัน{day_info['day']} ธาตุ{day_info['element']} อาหารมงคล: {day_info['lucky_food']}
แนะนำกรรมดีง่ายๆ 3 ข้อที่ทำได้วันนี้เลย
- พูดแบบกวนๆ บ่นๆ แต่ใจดี
- แต่ละข้อทำได้จริงใน 5 นาที
- บอกผลดีสั้นๆ
- เชื่อมกับธาตุ{day_info['element']}
ภาษาไทย ไม่เกิน 120 คำ"""
    msg = claude_client.messages.create(model="claude-opus-4-5", max_tokens=300,
        messages=[{"role": "user", "content": prompt}])
    return msg.content[0].text

def build_fortune_flex(fortune_text, day_info):
    bg = day_info["bg"]; btn = day_info["btn"]
    return {
        "type": "bubble", "size": "giga",
        "header": {
            "type": "box", "layout": "vertical", "backgroundColor": bg, "paddingAll": "20px",
            "contents": [
                {"type": "box", "layout": "horizontal", "contents": [
                    {"type": "text", "text": "🔮 ดวงดี ชีวิตดี", "weight": "bold", "size": "xl", "color": "#ffffff", "flex": 1},
                    {"type": "box", "layout": "vertical", "backgroundColor": "#ffffff30", "paddingAll": "6px", "cornerRadius": "12px",
                     "contents": [{"type": "text", "text": f"วัน{day_info['day']}", "size": "sm", "color": "#ffffff", "weight": "bold", "align": "center"}]}
                ]},
                {"type": "text", "text": f"📅 {day_info['date']}  |  ธาตุ {day_info['element']}", "size": "sm", "color": "#ffffffcc", "margin": "sm"},
                {"type": "text", "text": f"🎨 {day_info['lucky_color']}  |  🍽 {day_info['lucky_food']}", "size": "sm", "color": "#ffffffaa"},
            ]
        },
        "body": {
            "type": "box", "layout": "vertical", "paddingAll": "20px",
            "contents": [
                {"type": "text", "text": "✨ คำทำนายจากบุญดวง", "size": "xs", "color": btn, "weight": "bold"},
                {"type": "separator", "margin": "sm"},
                {"type": "text", "text": fortune_text, "wrap": True, "size": "sm", "color": "#333333", "margin": "sm"}
            ]
        },
        "footer": {
            "type": "box", "layout": "vertical", "paddingAll": "16px",
            "contents": [
                {"type": "box", "layout": "horizontal", "contents": [
                    {"type": "button", "action": {"type": "message", "label": "🎴 ถามดวง", "text": "ถามดวง"}, "style": "primary", "color": btn, "flex": 1, "height": "sm"},
                    {"type": "button", "action": {"type": "message", "label": "🙏 กรรมดี", "text": "กรรมดี"}, "style": "primary", "color": "#2E7D32", "flex": 1, "margin": "sm", "height": "sm"}
                ]},
                {"type": "box", "layout": "horizontal", "contents": [
                    {"type": "button", "action": {"type": "message", "label": "🌅 ดวงพรุ่งนี้", "text": "ดวงพรุ่งนี้"}, "style": "secondary", "flex": 1, "height": "sm"},
                    {"type": "button", "action": {"type": "uri", "label": "🔮 เปิดดวง", "uri": "https://web-production-f666c.up.railway.app/liff"}, "style": "primary", "color": "#7B2FBE", "flex": 1, "margin": "sm", "height": "sm"}
                ]},
                {"type": "button", "action": {"type": "uri", "label": "🎴 ไพ่ทาโรต์", "uri": "https://web-production-f666c.up.railway.app/tarot"}, "style": "primary", "color": "#8B4513", "margin": "sm", "height": "sm"}
            ]
        }
    }

def build_karma_flex(karma_text, day_info):
    return {
        "type": "bubble", "size": "giga",
        "header": {
            "type": "box", "layout": "vertical", "backgroundColor": "#2E7D32", "paddingAll": "16px",
            "contents": [
                {"type": "text", "text": "🙏 กรรมดีประจำวัน", "weight": "bold", "size": "lg", "color": "#ffffff"},
                {"type": "text", "text": f"วัน{day_info['day']} | ธาตุ{day_info['element']}", "size": "sm", "color": "#ffffffcc"}
            ]
        },
        "body": {
            "type": "box", "layout": "vertical", "paddingAll": "20px",
            "contents": [{"type": "text", "text": karma_text, "wrap": True, "size": "sm", "color": "#333333"}]
        }
    }

def send_morning_fortune():
    if not GROUP_ID:
        print("⚠️  ยังไม่มี GROUP_ID"); return
    try:
        day_info = get_day_info()
        flex_content = build_fortune_flex(generate_daily_fortune(day_info), day_info)
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).push_message(PushMessageRequest(
                to=GROUP_ID,
                messages=[FlexMessage(alt_text="🔮 ดวงประจำวัน", contents=FlexContainer.from_dict(flex_content))]
            ))
        print(f"✅ ส่งดวงเช้า {datetime.now(THAI_TZ).strftime('%H:%M')}")
    except Exception as e:
        print(f"❌ {e}")

def run_scheduler():
    schedule.every().day.at("07:00").do(send_morning_fortune)
    while True:
        schedule.run_pending()
        time.sleep(30)

@app.route("/liff")
def liff_page():
    return send_from_directory('.', 'liff.html')

@app.route("/tarot")
def tarot_page():
    return send_from_directory('.', 'tarot.html')

@app.route("/api/karma", methods=["POST"])
def api_karma():
    try:
        data = request.get_json()
        day = data.get("day", "")
        element = data.get("element", "")
        prompt = f"""คุณคือ "บุญดวง" หมอดูขี้บ่นสุดกวน แต่ใจดีลึกๆ
วันนี้วัน{day} ธาตุ{element}
สร้างกรรมดีง่ายๆ 1 ข้อ ที่ทำได้วันนี้เลย:
- พูดแบบกวนๆ ประชดประชันนิดๆ แต่ให้คำแนะนำจริง
- เชื่อมกับธาตุ{element}หรือธรรมชาติ
- ทำได้จริงภายใน 5 นาที
- จบด้วยข่มขู่เล็กน้อยว่าถ้าไม่ทำจะเกิดอะไร (กวนๆ ไม่น่ากลัวจริง)
- 2-3 ประโยคเท่านั้น ห้ามยืดยาว
ตอบภาษาไทย ไม่ต้องมีหัวข้อ"""
        msg = claude_client.messages.create(
            model="claude-opus-4-5", max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        return jsonify({"result": msg.content[0].text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/tarot", methods=["POST"])
def api_tarot():
    try:
        data = request.get_json()
        card_name = data.get("card", "")
        card_th = data.get("card_th", "")
        keywords = data.get("keywords", "")
        reversed_card = data.get("reversed", False)
        day = data.get("day", "")
        element = data.get("element", "")

        prompt = f"""คุณคือ "บุญดวง" หมอดูขี้บ่นสุดกวนแต่ใจดี เชี่ยวชาญไพ่ทาโรต์
วันนี้วัน{day} ธาตุ{element}
ไพ่ที่จั่วได้: {card_name} ({card_th}) {"— กลับหัว" if reversed_card else "— ตั้งตรง"}
คีย์เวิร์ด: {keywords}

ทำนายแบบบุญดวง:
1. 🎴 สรุปพลังไพ่ใบนี้ (1 ประโยคกวนๆ)
2. 💼 การงาน/การเงิน (1-2 ประโยค)
3. ❤️ ความรัก (1-2 ประโยค)
4. 🙏 กรรมดีที่ควรทำวันนี้เพื่อเสริมพลังไพ่ (1 ข้อ เป็นรูปธรรม)
5. ⚠️ ข้อควรระวัง (1 ประโยคขู่กวนๆ)
ภาษาไทย ไม่เกิน 200 คำ อ่านสนุก"""

        msg = claude_client.messages.create(
            model="claude-opus-4-5", max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        return jsonify({"result": msg.content[0].text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/webhook", methods=["POST"])
def webhook():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(JoinEvent)
def handle_join(event):
    gid = getattr(event.source, "group_id", None)
    if gid: print(f"📌 GROUP_ID = {gid}")
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=(
                "🔮 สวัสดีครับ! บุญดวงเข้ากลุ่มแล้ว ✨\n\n"
                "📅 ทุกเช้า 07:00 น. จะส่งดวงอัตโนมัติ\n"
                "• 'ดวง' → ดูดวงตอนนี้\n"
                "• 'ดวงพรุ่งนี้' → ดูล่วงหน้า\n"
                "• 'ถามดวง [คำถาม]' → เซียมซี\n"
                "• 'กรรมดี' → กรรมดีประจำวัน\n"
                "• 'help' → เมนูทั้งหมด\n\n"
                f"📌 Group ID: {gid}"
            ))]
        ))

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    text = event.message.text.strip()
    reply_token = event.reply_token
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        if text in ["ดวง", "ดูดวง", "ดวงวันนี้", "fortune"]:
            day_info = get_day_info()
            line_bot_api.reply_message(ReplyMessageRequest(reply_token=reply_token,
                messages=[FlexMessage(alt_text="🔮 ดวงประจำวัน",
                    contents=FlexContainer.from_dict(build_fortune_flex(generate_daily_fortune(day_info), day_info)))]))

        elif text in ["ดวงพรุ่งนี้", "พรุ่งนี้"]:
            day_info = get_day_info(offset_days=1)
            line_bot_api.reply_message(ReplyMessageRequest(reply_token=reply_token,
                messages=[FlexMessage(alt_text="🌅 ดวงพรุ่งนี้",
                    contents=FlexContainer.from_dict(build_fortune_flex(generate_daily_fortune(day_info), day_info)))]))

        elif text.startswith("ถามดวง") or text.startswith("เซียมซี"):
            question = text.replace("ถามดวง", "").replace("เซียมซี", "").strip()
            if not question:
                line_bot_api.reply_message(ReplyMessageRequest(reply_token=reply_token,
                    messages=[TextMessage(text="🎴 พิมพ์คำถามด้วยนะ เช่น:\nถามดวง จะได้งานใหม่ไหม?")]))
                return
            line_bot_api.reply_message(ReplyMessageRequest(reply_token=reply_token,
                messages=[TextMessage(text=generate_answer_fortune(question))]))

        elif text in ["กรรมดี", "ทำดี", "กรรม"]:
            day_info = get_day_info()
            line_bot_api.reply_message(ReplyMessageRequest(reply_token=reply_token,
                messages=[FlexMessage(alt_text="🙏 กรรมดีประจำวัน",
                    contents=FlexContainer.from_dict(build_karma_flex(generate_karma(), day_info)))]))

        elif text in ["ไพ่", "ไพ่ทาโรต์", "ทาโรต์", "tarot"]:
            tarot_url = "https://web-production-f666c.up.railway.app/tarot"
            line_bot_api.reply_message(ReplyMessageRequest(reply_token=reply_token,
                messages=[TextMessage(text=
                    "🎴 ไพ่ทาโรต์ของบุญดวง\n\n"
                    "กดลิงค์ด้านล่างเพื่อสุ่มไพ่ได้เลยครับ 👇\n"
                    f"{tarot_url}\n\n"
                    "🔮 มีไพ่ Major Arcana 22 ใบ\n"
                    "🃏 สุ่มได้ไม่จำกัด พลิกเปิดดูคำทำนายได้เลย!"
                )]))
        elif text in ["help", "ช่วยเหลือ", "เมนู", "วิธีใช้"]:
            line_bot_api.reply_message(ReplyMessageRequest(reply_token=reply_token,
                messages=[TextMessage(text=(
                    "🔮 บุญดวง — วิธีใช้\n\n"
                    "• 'ดวง' → ดูดวงวันนี้\n"
                    "• 'ดวงพรุ่งนี้' → ดูล่วงหน้า\n"
                    "• 'ถามดวง [คำถาม]' → เซียมซี\n"
                    "• 'กรรมดี' → กรรมดีประจำวัน\n"
                    "• 'ไพ่' → สุ่มไพ่ทาโรต์\n"
                    "• 'help' → เมนูนี้\n\n"
                    "📅 ส่งดวงอัตโนมัติทุกเช้า 07:00 น."
                ))]))

if __name__ == "__main__":
    threading.Thread(target=run_scheduler, daemon=True).start()
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
