import json
import requests
import psycopg2
import logging
import datetime
import re
import asyncio
import locale
import time
import random
from bs4 import BeautifulSoup
from telegram import Bot

# Random delay
delay = random.randint(0,900)
time.sleep(delay)

# Set locale for finnish dates
locale.setlocale(locale.LC_TIME, "fi_FI.UTF-8")

# Load configuration
with open("/etc/wilmakoeilmo.json") as f:
    config = json.load(f)

WILMA_URL          = config["wilma_url"]
LOGIN_URL          = f"{WILMA_URL}/login"
LOGOUT_URL         = f"{WILMA_URL}/logout"
EXAM_URL_TEMPLATE  = f"{WILMA_URL}/!{{id}}/exams/calendar"
TELEGRAM_BOT_TOKEN = config["telegram_bot_token"]
TELEGRAM_CHAT_ID   = config["telegram_chat_id"]

# Database connection
conn = psycopg2.connect(**config["database"])
cur = conn.cursor()

# Logger setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def login():
    """Logs in to Wilma and returns a session."""
    logger.info("Logging in")
    session = requests.Session()
    
    # Get CSRF token
    login_page = session.get(LOGIN_URL)
    soup = BeautifulSoup(login_page.text, "html.parser")
    csrf_token = soup.find("input", {"name": "SESSIONID"})["value"]

    # Perform login
    payload = {
        "Login": config["username"],
        "Password": config["password"],
        "SESSIONID": csrf_token
    }

    headers = {
        "Origin": WILMA_URL,
        "Referer": LOGIN_URL,
        "User-Agent": "WilmaKoeIlmo/1.0 (github.com/angs/wilmakoeilmo)"
    }
    
    resp = session.post(LOGIN_URL, data=payload, headers=headers)
    if "Istunnon tunniste ei kelpaa" in resp.text:
        logger.error("Login failed: Invalid session identifier")
        return None
    
    return session

def logout(session):
    logger.info("Logging out")
    session.get(LOGOUT_URL)

def extract_names(text):
    pattern = r'\([^()]*\)'
    matches = re.findall(pattern, text)
    names = [match.strip('()') for match in matches]

def parse_exam_page(html):
    logger.info("Parsing html")
    """Parses the exam page and returns a list of exam details."""
    soup = BeautifulSoup(html, "html.parser")
    main_content = soup.find("main", id="main-content")
    assignee = soup.find_all("span", {"class":"teacher"})[0].text.strip().split(" ")[0]
    
    if not main_content:
        logger.warning("No main content found!")
        return []

    exams = []
    for div in main_content.find_all("div", class_="table-responsive margin-bottom"):
        table = div.find("table", class_="table table-grey")
        if not table:
            continue

        rows = table.find_all("tr")
        if len(rows) < 3:
            continue
        
        date = datetime.datetime.strptime(rows[0].find("strong").text.strip().split(" ")[1], "%d.%m.%Y")
        topic = re.sub(r'\s+', ' ', rows[0].find_all("td")[1].text).strip()
        teacher = rows[1].find("td").text.strip().split("(")[-1].strip(")")
        additional_info = rows[2].find("td").text.strip()

        exams.append({
            "examdate": date,
            "topic": topic,
            "teacher": teacher,
            "additional_info": additional_info,
            "assignee": assignee
        })

    return exams

def fetch_exams(session):
    """Fetches exams for each ID in the config."""
    logger.info("Fetching exams")
    all_exams = []

    for exam_id in config["exam_ids"]:
        url = EXAM_URL_TEMPLATE.format(id=exam_id)
        response = session.get(url)
        if response.status_code == 200:
            exams = parse_exam_page(response.text)
            all_exams.extend(exams)
        else:
            logger.warning(f"Failed to fetch {url}")

    return all_exams

def store_exams(exams):
    """Stores new exams in the database and returns new ones."""
    logger.info("Storing exams")
    new_exams = []
    
    for exam in exams:
        cur.execute(
            "SELECT 1 FROM exams WHERE examdate = %s AND topic = %s AND teacher = %s",
            (exam["examdate"], exam["topic"], exam["teacher"])
        )
        if cur.fetchone() is None:
            cur.execute(
                "INSERT INTO exams (examdate, topic, teacher, additional_info, assignee, date_added) VALUES (%s, %s, %s, %s, %s, %s)",
                (exam["examdate"], exam["topic"], exam["teacher"], exam["additional_info"], exam["assignee"], datetime.datetime.now())
            )
            new_exams.append(exam)

    conn.commit()
    return new_exams

async def send_telegram_notification(exams):
    """Sends new exams to Telegram."""
    logger.info("Sending notifications")
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    
    for exam in exams:
        message = ( 
            f"{exam['assignee']}\n"
            f"📅 {datetime.datetime.strftime(exam['examdate'], '%a %d.%m.%Y')}\n'"
            f"📝 {exam['topic']}\n"
            f"👨‍🏫 {exam['teacher']}\n"
            f"ℹ️ {exam['additional_info']}"
        )

        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode="Markdown", read_timeout=60, write_timeout=60)
        time.sleep(1)

async def main():
    session = login()
    if not session:
        return
    
    try:
        exams = fetch_exams(session)
        new_exams = store_exams(exams)

        if new_exams:
            await send_telegram_notification(new_exams)
        else:
            logger.info("No new exams found.")
    finally:
        logout(session)
    
if __name__ == "__main__":
    asyncio.run(main())