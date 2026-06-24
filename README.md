# কুবি নিউজ বট — সেটআপ গাইড

## ধাপ ১ — Telegram Bot তৈরি করো

1. Telegram এ @BotFather এ যাও
2. /newbot লিখে পাঠাও
3. বটের নাম দাও (যেমন: KubiNewsBot)
4. যে TOKEN দেবে সেটা কপি করে রাখো

## ধাপ ২ — Channel তৈরি করো (যদি না থাকে)

1. Telegram এ নতুন Channel তৈরি করো
2. তোমার বটকে Channel এ Admin করো
3. Channel username নোট করো (যেমন: @kubinews)

## ধাপ ৩ — Railway তে ফ্রি হোস্ট করো

1. https://railway.app এ যাও (GitHub দিয়ে লগিন)
2. New Project → Deploy from GitHub repo বেছে নাও
3. এই ফোল্ডারের ফাইলগুলো GitHub এ আপলোড করো
4. Railway তে দুটো Environment Variable যোগ করো:
   - BOT_TOKEN = তোমার BotFather থেকে পাওয়া token
   - CHANNEL_ID = @kubinews (বা channel এর numeric id)
5. Deploy করো

## Environment Variables

BOT_TOKEN=your_token_here
CHANNEL_ID=@your_channel

## নিজের PC তে চালাতে চাইলে

pip install -r requirements.txt
python bot.py
