import urllib.request
import json
import time
import os

def get_chat_id(bot_token, channel_name):
    print(f"\n👉 Please open your Telegram app.")
    print(f"👉 Send the message 'Hello' inside the '{channel_name}' channel.")
    input("Press ENTER here after you have sent the message...")
    
    print(f"Fetching Chat ID for {channel_name}...")
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    
    for _ in range(3):
        try:
            with urllib.request.urlopen(url) as response:
                data = json.loads(response.read().decode())
                for update in data.get('result', []):
                    message = update.get('message') or update.get('channel_post')
                    if message:
                        chat_id = message['chat']['id']
                        print(f"✅ Found {channel_name} Chat ID: {chat_id}")
                        return str(chat_id)
        except Exception as e:
            print(f"Error fetching updates: {e}")
            
        print("Still searching... Please make sure you sent a message in the channel.")
        time.sleep(3)
        
    print(f"❌ Could not find Chat ID. Are you sure you sent a message and the Bot is an Admin?")
    return None

def main():
    print("="*50)
    print("🤖 AUTOMATIC TELEGRAM CHAT ID FINDER 🤖")
    print("="*50)
    
    bot_1 = "8107047216:AAGjA6eV0jVZkl_xJGNtM6WZoe-lMbYZJhY"
    bot_2 = "8836776786:AAFd5lwWkqHlbMLPZFs3jleCrD51U1RG7AY"
    bot_3 = "8357076737:AAGuQqQwOXJ02dUQH_Fzzz7QuBC32RqJPLQ"
    
    queue_1_id = get_chat_id(bot_1, "Queue 1 (Raw Videos)")
    queue_2_id = get_chat_id(bot_3, "Queue 2 (Edited Videos)")
    
    print("\n" + "="*50)
    print("🎉 SETUP COMPLETE! 🎉")
    print("Please copy these values into your GitHub Secrets:")
    print(f"TELEGRAM_QUEUE_1_CHAT_ID = {queue_1_id or '-100xxxxxxxxxx'}")
    print(f"TELEGRAM_QUEUE_2_CHAT_ID = {queue_2_id or '-100xxxxxxxxxx'}")
    print("="*50)

if __name__ == "__main__":
    main()
