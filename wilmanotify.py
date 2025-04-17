import json
import psycopg2
import logging
import datetime
import asyncio
import locale
from telegram import Bot

# Load configuration
with open("config.json") as f:
    config = json.load(f)

locale.setlocale(locale.LC_TIME, "fi_FI.UTF-8")

TELEGRAM_BOT_TOKEN = config["telegram_bot_token"]
TELEGRAM_CHAT_ID = config["notify_chat_id"]

# Database connection
conn = psycopg2.connect(**config["database"])
cur = conn.cursor()

# Logger setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def getExamsForTomorrow():
    cur.execute("SELECT * FROM exams WHERE examdate = CURRENT_DATE + interval '1 day';")
    huomiset = cur.fetchall()
    return huomiset

def getExamsForNextWeek():
    cur.execute("""
SELECT * 
FROM exams 
WHERE examdate >= CURRENT_DATE + (8 - EXTRACT(DOW FROM CURRENT_DATE)) * INTERVAL '1 day'
AND examdate < CURRENT_DATE + (15 - EXTRACT(DOW FROM CURRENT_DATE)) * INTERVAL '1 day'
order by examdate asc;
""")
    kokeet = cur.fetchall()
    return kokeet

def examday_string(exam_date):
    today = datetime.datetime.today().date()
    delta_days = (exam_date - today).days

    if delta_days == 1:
        return "huomenna"
    elif delta_days == 2:
        return "ylihuomenna"
    elif delta_days == 3 and today.weekday() in {4, 5, 6}:  # Perjantai, lauantai tai sunnuntai
        return "maanantaina"
    else:
        return f"{delta_days} päivän päästä"

async def send_telegram_notification(exam):
    """Sends new exams to Telegram."""
    logger.info("Sending notifications")
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    message = (
        f"😱 {exam[5]}! Sinulla on koe {examday_string(exam[1])}! ({exam[2]})"
    )
    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode="Markdown", read_timeout=60, write_timeout=60)

async def send_nextweek_notifications(exams):
    """Sends new exams to Telegram."""
    logger.info("Sending notifications")
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    viestit = ["Ensi viikon kokeet! ❤️"]
    if exams:
        for exam in exams:
            viestit.append(f"*{datetime.datetime.strftime(exam[1], '%A').capitalize()}* {exam[5]}: {exam[2]}")
        viesti = "\n".join(viestit)
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=viesti, parse_mode="Markdown", read_timeout=60, write_timeout=60)
    else:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="Ei kokeita ensi viikolla! ❤️", parse_mode="Markdown", read_timeout=60, write_timeout=60)

async def main():
    match datetime.datetime.today().weekday():
        case 4:
            logger.info("Perjantai, ei raportoida")
        case 5:
            logger.info("Lauantain viikkoraportti")
            exams = getExamsForNextWeek()
            await send_nextweek_notifications(exams)
        case _:
            exams = getExamsForTomorrow()
            if exams:
                logger.info("Exams for tomorrow found!")
                for exam in exams:
                    await send_telegram_notification(exam)
            else:
                logger.info("No exams for tomorrow.")
    
if __name__ == "__main__":
    asyncio.run(main())