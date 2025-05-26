import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters
import yt_dlp
import os
import time
import uuid
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# বট টোকেন এবং চ্যাট আইডি
TOKEN = "8026328919:AAGvqBcVSA3HPT7mmxi-bAXKiPWv-zJ8dvE"
ADMIN_CHAT_ID = "937433961"

# গ্লোবাল ভেরিয়েবল
user_urls = {}
download_progress = {}
url_mapping = {}

# Simple HTTP Server to respond to UptimeRobot pings
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is running!")

def run_http_server():
    server_address = ('', 8080)  # Replit listens on port 8080 by default
    httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)
    print("Starting HTTP server on port 8080...")
    httpd.serve_forever()

def start(update, context):
    update.message.reply_text("Welcome to Multi-Platform Video Downloader Bot! Send a video URL (e.g., YouTube/Facebook link) or use /download <URL1> <URL2> ... to start.")

def get_file_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024**2:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024**3:
        return f"{size_bytes / 1024**2:.2f} MB"
    else:
        return f"{size_bytes / 1024**3:.2f} GB"

def progress_hook(d):
    if d['status'] == 'downloading':
        chat_id = download_progress.get('chat_id')
        message_id = download_progress.get('message_id')
        if chat_id and message_id:
            percent = d.get('_percent_str', '0%').strip('% ')
            try:
                percent = float(percent)
                context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"Downloading: {percent:.1f}%"
                )
            except:
                pass

def download(update, context):
    try:
        user_id = update.message.from_user.id
        if context.args:
            urls = context.args
        else:
            message_text = update.message.text.strip()
            if not message_text or message_text == "/download":
                update.message.reply_text("Please provide a video URL. E.g., https://www.youtube.com/watch?v=51QkwyZo4ec")
                return
            urls = [message_text]

        if not urls:
            update.message.reply_text("Please provide a video URL. E.g., https://www.youtube.com/watch?v=51QkwyZo4ec")
            return

        user_urls[user_id] = urls

        for url in urls:
            ydl_opts = {
                'quiet': True,
                'noplaylist': True,
                'format': 'bestvideo+bestaudio/best',
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                formats = info.get('formats', [])
                title = info.get('title', 'Unknown Title')

            url_id = str(uuid.uuid4())
            url_mapping[url_id] = url

            keyboard = []
            for fmt in formats:
                resolution = fmt.get('resolution', 'Unknown')
                filesize = fmt.get('filesize') or fmt.get('filesize_approx')
                filesize_str = get_file_size(filesize) if filesize else "Unknown"
                if fmt.get('vcodec') != 'none' and fmt.get('ext') == 'mp4':
                    keyboard.append([
                        InlineKeyboardButton(
                            f"Video - {resolution} ({filesize_str})",
                            callback_data=f"video_{fmt['format_id']}_{url_id}"
                        )
                    ])
                elif fmt.get('acodec') != 'none' and fmt.get('vcodec') == 'none':
                    keyboard.append([
                        InlineKeyboardButton(
                            f"Audio - MP4 ({filesize_str})",
                            callback_data=f"audio_{fmt['format_id']}_{url_id}"
                        )
                    ])

            reply_markup = InlineKeyboardMarkup(keyboard)
            update.message.reply_text(f"Choose format for {title}:", reply_markup=reply_markup)
    except Exception as e:
        update.message.reply_text(f"Error: {str(e)}")

def button_callback(update, context):
    try:
        query = update.callback_query
        user_id = query.from_user.id
        data = query.data
        parts = data.split('_', 2)
        if len(parts) != 3:
            query.message.reply_text("Invalid format selection. Please try again.")
            return
        stream_type, format_id, url_id = parts
        url = url_mapping.get(url_id)
        if not url:
            query.message.reply_text("URL not found. Please try again with a new link.")
            return

        progress_message = query.message.reply_text("Downloading: 0%")
        download_progress['chat_id'] = query.message.chat_id
        download_progress['message_id'] = progress_message.message_id

        ydl_opts = {
            'format': format_id,
            'outtmpl': f'{user_id}_{int(time.time())}.%(ext)s',
            'progress_hooks': [progress_hook],
            'quiet': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            video_path = ydl.prepare_filename(ydl.extract_info(url, download=False))

        if stream_type == "video":
            context.bot.send_video(
                chat_id=query.message.chat_id,
                video=open(video_path, 'rb'),
                supports_streaming=True
            )
        else:
            context.bot.send_audio(
                chat_id=query.message.chat_id,
                audio=open(video_path, 'rb')
            )

        query.message.reply_text("Download complete!")
        os.remove(video_path)
    except Exception as e:
        query.message.reply_text(f"Error: {str(e)}")
    finally:
        download_progress.clear()

def main():
    http_thread = threading.Thread(target=run_http_server)
    http_thread.daemon = True
    http_thread.start()

    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("download", download))
    dp.add_handler(CallbackQueryHandler(button_callback))
    dp.add_handler(MessageHandler(Filters.entity("url") | Filters.text, download))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()