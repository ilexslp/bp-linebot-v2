import os
from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, ImageMessage, TextSendMessage
from PIL import Image
import pytesseract
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

app = Flask(__name__)
line_bot_api = LineBotApi(os.environ['LINE_CHANNEL_ACCESS_TOKEN'])
handler = WebhookHandler(os.environ['LINE_CHANNEL_SECRET'])

def extract_bp_values(image_path):
    text = pytesseract.image_to_string(Image.open(image_path))
    import re
    sys = re.search(r'\b1\d{2}\b', text)
    dia = re.search(r'\b7\d\b', text)
    pulse = re.search(r'\b[5-9]\d\b', text)
    return int(sys.group()) if sys else None, int(dia.group()) if dia else None, int(pulse.group()) if pulse else None

def save_to_sheet(user_id, sys, dia, pulse):
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_url(os.environ['GOOGLE_SHEET_URL']).sheet1
    sheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id, sys, dia, pulse])

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    handler.handle(body, signature)
    return 'OK'

@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    message_content = line_bot_api.get_message_content(event.message.id)
    with open("bp.jpg", "wb") as f:
        for chunk in message_content.iter_content():
            f.write(chunk)
    sys, dia, pulse = extract_bp_values("bp.jpg")
    user_id = event.source.user_id
    if sys and dia and pulse:
        save_to_sheet(user_id, sys, dia, pulse)
        reply = f"✅ บันทึกแล้ว\nSYS: {sys}\nDIA: {dia}\nPULSE: {pulse}"
    else:
        reply = "❌ ไม่สามารถอ่านค่าความดันจากภาพได้"
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
