import time
import pystray
import threading
from pystray import MenuItem as item
from PIL import Image
import imaplib
import email
import toml

import os
import sys
import schedule
from datetime import datetime
import subprocess
import signal

import json
from typing import List, Dict
import requests

threads = []
mail_accounts = []
batch_file_path = "restart.bat"

def handle_termination(signal, frame):
    print("Termination signal received. Exiting...")
    sys.exit(0)

signal.signal(signal.SIGINT, handle_termination)

def restart_prog (icon, item):
    icon.stop()
    print("restarting....", datetime.now())
    subprocess.Popen(batch_file_path, shell=True, stdin=None, stdout=None, stderr=None, close_fds=True)
    os.kill(os.getpid(), signal.SIGINT)
    # os.execv(sys.executable, ['python'] + sys.argv)

# Read configuration from TOML file
def read_config(file_path):
    try:
        with open(file_path, "r") as file:
            config = toml.load(file)
            return config
    except Exception as e:
        print("Error occurred while reading the configuration file:", str(e))
        return None

def post_block_message_to_slack(blocks: List[Dict[str, str]] = None):
    return requests.post('https://slack.com/api/chat.postMessage', {
        'token': slack_token,
        'channel': channel,
        'blocks': json.dumps(blocks) if blocks else None,
    }).json()

def post_text_message_to_slack(text: str):
    return requests.post('https://slack.com/api/chat.postMessage', {
        'token': slack_token,
        'channel': channel,
        'text': text
    }).json()


def send_unread_notification_mail(mail_account):
    try:
        # Search for unseen messages
        _, data = mail_account.search(None, "UNSEEN")
        email_ids = data[0].split()

        if email_ids:
            for email_id in email_ids:
                # Fetch the email details
                _, msg_data = mail_account.fetch(email_id, "(RFC822)")
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])

                        # Retrieve email details
                        receiver = msg["To"]
                        subject = msg["Subject"]

                        # Check if the email has multiple parts (such as plain text and HTML)
                        if msg.is_multipart():
                            # Iterate over each part of the email
                            for part in msg.get_payload():
                                # Check if the part is plain text
                                if part.get_content_type() == 'text/plain':
                                    # Get the body/text of the email
                                    body = part.get_payload()
                        else:
                            # If the email is not multipart, it means it's a single part (e.g., plain text)
                            body = msg.get_payload()

                        account_mail_block = {
                            "type": "header",
                            "text": {
                                "type": "plain_text",
                                "text": receiver,
                                "emoji": True
                            }
                        }

                        subject_block = {
                            "type": "section",
                            "text": {
                                "type": "plain_text",
                                "text": subject,
                                "emoji": True
                            },
                            
                        }
                        body_block = {
                            "type": "section",
                            "text": {
                                "type": "plain_text",
                                "text": body,
                                "emoji": True
                            },
                            
                        }

                        block_data = [account_mail_block, subject_block,body_block ]
                        post_text_message_to_slack("Hi, <@" + user_id + "> <!channel>")
                        post_block_message_to_slack(block_data)
                        time.sleep(1)

                # Mark each unread message as read
                mail_account.store(email_id, "+FLAGS", "\\Seen")

    except Exception as e:
        print("Error occurred while checking inbox:", str(e))


def run_checker(mail_account):
    while True:
        send_unread_notification_mail(mail_account)
        time.sleep(180)
        schedule.run_pending()

# Function to exit the system tray application
def exit_action(icon, item):
    print("exiting by command.....")
    icon.stop()
    os.kill(os.getpid(), signal.SIGINT)


# Read configuration from TOML file
config_file_path = "./config.toml"
config = read_config(config_file_path)

if config:
    # Set up the system tray icon
    image = Image.open("./icon.ico")
    icon = pystray.Icon("name", image, "upw alert")

    # Create the system tray menu
    menu = []
    
    user_id = config.get("owner").get("user_id")
    name = config.get("owner").get("name")
    slack_token = config.get("slack").get("slack_token")
    channel = config.get("slack").get("channel")

    i = 0
    for account in config.get("source_email_accounts"):
        imap_server = account.get("imap_server")
        imap_port = account.get("imap_port")
        email_address = account.get("email_address")
        email_password = account.get("email_password")

        # Connect to the IMAP server
        mail_accounts.append(imaplib.IMAP4_SSL(imap_server, imap_port))
        mail_accounts[i].login(email_address, email_password)
        mail_accounts[i].select("INBOX")
        
        # Start a separate thread for each email account
        threads.append(threading.Thread(target=run_checker, args=(mail_accounts[i],)))
        threads[i].daemon = True
        threads[i].start()

        # Add menu item for each email account
        menu.append(item(email_address, lambda email_address: None))
        i += 1
        
    # Add exit menu item
    menu.append(item('Exit', exit_action))
    menu.append(item('Restart', restart_prog))

    # Set the system tray menu
    icon.menu = pystray.Menu(*menu)
    
    fk_item = None
    schedule.every(1).hours.do(lambda: restart_prog(icon=icon, item=fk_item))
    print("started at", datetime.now(), "...")
    
    # Run the system tray application
    icon.run()