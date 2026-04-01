import os
import anthropic
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, PushMessageRequest,
    TextMessage, FlexMessage, FlexContainer
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, JoinEvent
from linebot.v3.exceptions import InvalidSignatureError
from datetime import datetime
import json
import threading
import schedule
import time
import pytz

app = Flask(__name__)

# ── Config from environment ──────────────────────────────
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GROUP_ID = os.environ.get("LINE_GROUP_ID", "")   # จะได้มาหลัง bot เข้ากลุ่ม

handler = WebhookHandler(LINE_CHANNEL_SECRET)
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

THAI_TZ = pytz.timezone("Asia/Bangkok")

# ── Helpers ──────────────────────────────────────────────
def get_thai_day_info():
    now = datetime.now(THAI_TZ)
    days_th = ["จันทร์","อังคาร","พุธ","พฤหัสบดี","ศุกร์","เสาร์","อาทิตย์"]
    elements = {
        "จันทร์": ("น้ำ 💧", "ขาว/เงิน", "ปลา/อาหารทะเล"),
        "อังคาร": ("ไฟ 🔥", "แดง/ชมพู", "ขิง/พริก/อาหารร้อน"),
        "พุธ": ("ดิน 🌿", "เขียว", "ผัก/สมุนไพร"),
        "พฤหัสบดี": ("ไม้ 🌳", "ส้ม/เหลือง", "ข้าวโพด/ถั่ว"),
        "ศุกร์": ("โลหะ ✨", "ฟ้า/น้ำเงิน", "ดอกไม้/อาหารหวาน"),
        "เสาร์": ("ดิน 🪨", "ม่วง/ดำ", "เห็ด/ราก/หัว"),
        "อาทิตย์": ("ไฟ ☀️", "ทอง/เหลือง", "น้ำผึ้ง/อาหารสีเหลือง"),
    }
    day_name = days_th[now.weekday()]
    element, color, food = elements[day_name]
    return {
        "date": now.strftime("%d/%m/%Y"),
        "day": day_name,
        "element": element,
        "lucky_color": color,
        "lucky_food": food,
        "hour": now.hour
    }

def generate_daily_fortune(day_info: dict) -> str:
    prompt = f"""คุณคือหมอดูผู้เชี่ยวชาญศาสตร์โบราณทั้งไทย จีน และตะวันตก
วันนี้คือวัน{day_info['day']} ที่ {day_info['date']}
ธาตุประจำวัน: {day_info['element']}
สีมงคล: {day_info['lucky_color']}
อาหารมงคล: {day_info['lucky_food']}

กรุณาสร้างดวงรายวันที่ครอบคลุม:
1. 🔮 ภาพรวมพลังงานวันนี้ (อ้างอิงโหราศาสตร์ไทยหรือจีน 1 ศาสตร์)
2. 💼 การงาน/การเงิน (1-2 ประโยค กระชับ)
3. ❤️ ความรัก/ความสัมพันธ์ (1-2 ประโยค)
4. 🌿 สุขภาพ + อาหารมงคลวันนี้จากแพทย์แผนจีนหรือไทย (พร้อมบอกสรรพคุณ)
5. 🙏 กรรมดีง่ายๆ ที่ทำได้วันนี้ (1 ข้อ เป็นรูปธรรม ทำได้จริง เช่น "เทน้ำให้ต้นไม้ข้างทาง")
6. ✨ คำคมส่งท้าย (จากปรัชญาไทย/จีน/พุทธ 1 ประโยค)
7. ⚠️ สิ่งที่ควรระวัง (1 ข้อสั้นๆ)

ใช้ภาษาไทยที่อ่านสนุก อบอุ่น มีพลัง ไม่ยาวเกินไป รวมทั้งหมดไม่เกิน 300 คำ
เริ่มต้นด้วย emoji และหัวข้อให้ชัดเจน"""

    message = claude_client.messages.create(
        model="claude-opus-4-5",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text

def generate_answer_fortune(question: str) -> str:
    day_info = get_thai_day_info()
    prompt = f"""คุณคือหมอดูที่เชี่ยวชาญ I-Ching (อี้จิง) และเซียมซีไทย
วันนี้วัน{day_info['day']} ธาตุ{day_info['element']}

ผู้ถามมีคำถามว่า: "{question}"

กรุณาตีความแบบ I-Ching หรือเซียมซี:
1. 🎴 เซี่ยมซี/กุ้ย: ดีมาก / ดี / กลางๆ / ระวัง (เลือก 1)
2. 📖 คำทำนาย: ตีความคำถามตรงๆ (3-4 ประโยค)
3. 💡 คำแนะนำ: สิ่งที่ควรทำหรือหลีกเลี่ยง
4. 🙏 กรรมดีเสริมดวง: กรรมดีง่ายๆ 1 ข้อที่ช่วยเสริมเรื่องนี้โดยเฉพาะ

ภาษาไทย อ่านสนุก อบอุ่น ไม่เกิน 150 คำ"""

    message = claude_client.messages.create(
        model="claude-opus-4-5",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text

# ── Flex Message Builder ─────────────────────────────────
def build_fortune_flex(fortune_text: str, day_info: dict) -> dict:
    return {
        "type": "bubble",
        "size": "giga",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "🔮 ดวงดี ชีวิตดี", "weight": "bold", "size": "xl", "color": "#ffffff"},
                {"type": "text", "text": f"วัน{day_info['day']} | {day_info['date']}", "size": "sm", "color": "#ffffffcc"},
                {"type": "text", "text": f"ธาตุ{day_info['element']} | สี{day_info['lucky_color']}", "size": "sm", "color": "#ffffffaa"}
            ],
            "backgroundColor": "#7B2FBE",
            "paddingAll": "20px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": fortune_text, "wrap": True, "size": "sm", "color": "#333333"}
            ],
            "paddingAll": "20px"
        },
        "footer": {
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {
                    "type": "button",
                    "action": {"type": "message", "label": "🎴 ถามเซียมซี", "text": "ถามดวง"},
                    "style": "primary",
                    "color": "#7B2FBE",
                    "flex": 1
                },
                {
                    "type": "button",
                    "action": {"type": "message", "label": "🙏 กรรมดีวันนี้", "text": "กรรมดี"},
                    "style": "secondary",
                    "flex": 1,
                    "margin": "sm"
                }
            ]
        }
    }

def build_karma_flex(karma_text: str) -> dict:
    return {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "🙏 กรรมดีประจำวัน", "weight": "bold", "size": "lg", "color": "#ffffff"}
            ],
            "backgroundColor": "#2E7D32",
            "paddingAll": "16px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": karma_text, "wrap": True, "size": "sm", "color": "#333333"}
            ],
            "paddingAll": "20px"
        }
    }

# ── Send morning fortune to group ───────────────────────
def send_morning_fortune():
    if not GROUP_ID:
        print("⚠️  ยังไม่มี GROUP_ID — เพิ่ม bot เข้ากลุ่มก่อน")
        return
    try:
        day_info = get_thai_day_info()
        fortune_text = generate_daily_fortune(day_info)
        flex_content = build_fortune_flex(fortune_text, day_info)
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.push_message(PushMessageRequest(
                to=GROUP_ID,
                messages=[FlexMessage(alt_text="🔮 ดวงประจำวัน", contents=FlexContainer.from_dict(flex_content))]
            ))
        print(f"✅ ส่งดวงเช้าแล้ว {datetime.now(THAI_TZ).strftime('%H:%M')}")
    except Exception as e:
        print(f"❌ Error sending fortune: {e}")

# ── Scheduler (runs in background thread) ───────────────
def run_scheduler():
    schedule.every().day.at("07:00").do(send_morning_fortune)
    while True:
        schedule.run_pending()
        time.sleep(30)

# ── Webhook ──────────────────────────────────────────────
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
    """บอท join กลุ่ม → บันทึก group id และทักทาย"""
    source = event.source
    gid = getattr(source, "group_id", None)
    if gid:
        print(f"📌 GROUP_ID = {gid}")   # copy ค่านี้ไปใส่ใน Railway env
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=(
                "🔮 สวัสดีครับ! บอท 'ดวงดี ชีวิตดี' เข้ากลุ่มแล้ว ✨\n\n"
                "📅 ทุกเช้า 07:00 น. จะส่งดวงประจำวันให้อัตโนมัติ\n"
                "🎴 พิมพ์ 'ดวง' เพื่อดูดวงตอนนี้\n"
                "🔮 พิมพ์ 'ถามดวง [คำถาม]' เพื่อถามเซียมซี\n"
                "🙏 พิมพ์ 'กรรมดี' เพื่อรับกรรมดีประจำวัน\n\n"
                f"📌 Group ID: {gid}\n(แอดมินบันทึกค่านี้ใน Railway env ด้วยนะครับ)"
            ))]
        ))

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    text = event.message.text.strip()
    reply_token = event.reply_token

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        # ดูดวงวันนี้
        if text in ["ดวง", "ดูดวง", "ดวงวันนี้", "fortune"]:
            day_info = get_thai_day_info()
            fortune_text = generate_daily_fortune(day_info)
            flex_content = build_fortune_flex(fortune_text, day_info)
            line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=reply_token,
                messages=[FlexMessage(alt_text="🔮 ดวงประจำวัน", contents=FlexContainer.from_dict(flex_content))]
            ))

        # ถามดวง
        elif text.startswith("ถามดวง") or text.startswith("เซียมซี"):
            question = text.replace("ถามดวง", "").replace("เซียมซี", "").strip()
            if not question:
                line_bot_api.reply_message(ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="🎴 กรุณาพิมพ์คำถามด้วยครับ\nเช่น: ถามดวง งานใหม่จะเป็นอย่างไร?")]
                ))
                return
            answer = generate_answer_fortune(question)
            line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=answer)]
            ))

        # กรรมดี
        elif text in ["กรรมดี", "ทำดี", "กรรม"]:
            day_info = get_thai_day_info()
            prompt = f"""แนะนำกรรมดี 3 ข้อที่ทำได้ง่ายๆ วันนี้ (วัน{day_info['day']})
ให้เชื่อมกับ:
- ธาตุประจำวัน: {day_info['element']}
- อาหารมงคล: {day_info['lucky_food']}
แต่ละข้อต้องเป็นรูปธรรม ทำได้จริง บอกผลดีที่จะได้รับสั้นๆ
ภาษาไทย อ่านง่าย อบอุ่น ไม่เกิน 120 คำ"""
            msg = claude_client.messages.create(
                model="claude-opus-4-5", max_tokens=300,
                messages=[{"role": "user", "content": prompt}]
            )
            karma_text = msg.content[0].text
            flex_content = build_karma_flex(karma_text)
            line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=reply_token,
                messages=[FlexMessage(alt_text="🙏 กรรมดีประจำวัน", contents=FlexContainer.from_dict(flex_content))]
            ))

        # help
        elif text in ["help", "ช่วยเหลือ", "เมนู", "วิธีใช้"]:
            line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=(
                    "🔮 วิธีใช้บอท 'ดวงดี ชีวิตดี'\n\n"
                    "📅 ดวงรายวัน — ส่งอัตโนมัติ 07:00 น.\n\n"
                    "💬 พิมพ์ได้เลย:\n"
                    "• 'ดวง' → ดูดวงตอนนี้\n"
                    "• 'ถามดวง [คำถาม]' → เซียมซีส่วนตัว\n"
                    "• 'กรรมดี' → กรรมดีประจำวัน\n"
                    "• 'help' → เมนูนี้"
                ))]
            ))

# ── Start ────────────────────────────────────────────────
if __name__ == "__main__":
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
