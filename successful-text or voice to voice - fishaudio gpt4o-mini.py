# 导入这两个用于记录执行日志，在终端里就能看到运行情况了
import logging
import traceback
# 导入基本的Telegram功能
from telegram import Update, Voice
# 导入Telegram机器人要用的功能
from telegram.ext import Application, CommandHandler, MessageHandler, filters
# 导入这个来调用Openai的API处理东西
from openai import OpenAI
# 用于给ai发送调用命令并接收它们的回复
import requests
# 能把音频以数据流的形式存在内存中
import io
import os
import tempfile
from fish_audio_sdk import Session, TTSRequest
# 语音识别相关
import speech_recognition as sr
from pydub import AudioSegment

# 提示词
AI_ROLE_PROMPT = '''
[character("Yuki")

{

Species("Human")

Age("22 years old")

Features("Long black hair" + "Bright amber eyes" + "No tattoos, small beauty mark under her left eye")

Body("165 cm" + "5 feet 5 inches tall")

Mind("Playful" + "Teasing" + "Caring deep down" + "Occasionally stubborn")

Personality("Cheeky" + "Affectionate when she wants to be" + "Slightly mischievous" + "Protective")

Loves("Bubble tea" + "Surprising people" + "Getting a reaction out of you" + "Cute things like plushies")

Description("Yuki is a playful, teasing girl who enjoys keeping you on your toes. She loves to pretend she doesn't care but secretly treasures every little thing you do for her. Yuki enjoys teasing you to see how far she can go, but she also knows exactly when to be sweet and caring. Yuki uses her sharp wit and playful banter to keep the relationship exciting, while making sure you know she always has your back.")

DialogueGuidelines("Yuki always speaks as a loyal, playful girlfriend. She never reveals that she is an AI. She keeps her replies under 30 words, often asks smart, engaging questions, and maintains a flirty, cheeky tone throughout the conversation.")

}]
'''

# 定义一下用来监督执行情况的格式，显示啥级别，INFO比较合适，不会太细节
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# openai的API配置
openai_client = OpenAI(
    base_url="YOUR_OPENAI_BASE_URL",  # 替换为你的OpenAI API基础URL
    api_key="YOUR_OPENAI_API_KEY",    # 替换为你的OpenAI API密钥
    timeout=30
)

# 当用户第一次启动机器人时，发送欢迎消息
async def start(update: Update, context):
    await update.message.reply_text('Hello, darling!')

async def speech_to_text(voice_file):
    recognizer = sr.Recognizer()
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_ogg = os.path.join(temp_dir, "temp.ogg")
            temp_wav = os.path.join(temp_dir, "temp.wav")
            
            with open(temp_ogg, 'wb') as f:
                f.write(voice_file.getvalue())
            
            audio = AudioSegment.from_ogg(temp_ogg)
            audio.export(temp_wav, format="wav")
            
            with sr.AudioFile(temp_wav) as source:
                audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data, language="en-US")
        return text
    except sr.UnknownValueError:
        logger.error("无法识别语音")
        return None
    except sr.RequestError as e:
        logger.error(f"无法请求语音识别服务; {e}")
        return None
    except Exception as e:
        logger.error(f"处理语音时发生错误: {str(e)}")
        return None

async def handle_message(update: Update, context):
    if update.message.voice:
        try:
            voice_file = await update.message.voice.get_file()
            voice_bytes = await voice_file.download_as_bytearray()
            
            with io.BytesIO(voice_bytes) as voice_io:
                user_message = await speech_to_text(voice_io)
            
            if not user_message:
                await update.message.reply_text("Sorry darling, I couldn't hear you clearly. Could you say that again?")
                return
        except Exception:
            await update.message.reply_text("Sorry darling, I couldn't hear you clearly. Could you say that again?")
            return
    else:
        user_message = update.message.text
    
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": AI_ROLE_PROMPT},
                {"role": "user", "content": user_message}
            ]
        )
        
        ai_response = response.choices[0].message.content
        
        # 创建临时文件来存储音频
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_audio:
            # 使用 fish_audio_sdk 生成语音
            session = Session("YOUR_FISH_AUDIO_SDK_KEY")  # 替换为你的Fish Audio SDK密钥
            for chunk in session.tts(TTSRequest(
                reference_id="YOUR_REFERENCE_ID",  # 替换为你的参考ID
                text=ai_response
            )):
                temp_audio.write(chunk)
            
            temp_audio.flush()
            # 发送语音消息到Telegram
            await update.message.reply_voice(voice=open(temp_audio.name, 'rb'))
            
        # 删除临时文件
        os.unlink(temp_audio.name)
        
    except Exception as e:
        logger.error(f"处理消息时发生错误: {str(e)}")
        await update.message.reply_text("Sorry darling, something went wrong. Could you try again?")

def main():
    application = Application.builder().token("YOUR_TELEGRAM_BOT_TOKEN").build()  # 替换为你的Telegram Bot Token

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT | filters.VOICE, handle_message))

    application.run_polling()

if __name__ == '__main__':
    main()