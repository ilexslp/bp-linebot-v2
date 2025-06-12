import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, ImageMessage, TextSendMessage
from PIL import Image
import pytesseract
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import tempfile
import re

app = Flask(__name__)
line_bot_api = LineBotApi(os.environ['LINE_CHANNEL_ACCESS_TOKEN'])
handler = WebhookHandler(os.environ['LINE_CHANNEL_SECRET'])

def extract_bp_values(image_path):
    text = pytesseract.image_to_string(Image.open(image_path))
    print("📄 OCR text output:")
    print(text)  # <--- ดูข้อความที่ได้จาก OCR

    numbers = list(map(int, re.findall(r'\b\d{2,3}\b', text)))
    print("🔢 Extracted numbers:", numbers)

    if len(numbers) >= 3:
        sys, dia, pulse = numbers[:3]
        if 90 <= sys <= 200 and 50 <= dia <= 130 and 40 <= pulse <= 180:
            return sys, dia, pulse

    return None, None, None

def save_to_sheet(user_id, sys, dia, pulse):
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_url(os.environ['GOOGLE_SHEET_URL']).sheet1
        sheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id, sys, dia, pulse])
    except Exception as e:
        print("❌ ERROR saving to Google Sheet:", e)

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    message_content = line_bot_api.get_message_content(event.message.id)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tf:
        for chunk in message_content.iter_content():
            tf.write(chunk)
        temp_path = tf.name

    sys, dia, pulse = extract_bp_values(temp_path)
    user_id = event.source.user_id

    if sys and dia and pulse:
        save_to_sheet(user_id, sys, dia, pulse)
        reply = f"✅ บันทึกแล้ว\\nSYS: {sys}\\nDIA: {dia}\\nPULSE: {pulse}"
    else:
        reply = "❌ ไม่สามารถอ่านค่าความดันจากภาพได้"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
