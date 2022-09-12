from utils import load_config
from sync import Client

config = load_config()
api_id = config['Telegram']['api_id']
api_hash = config['Telegram']['api_hash']
bot_token = config['Telegram']['bot_token']

bot = Client("TG_Download_Bot" , api_id, api_hash , bot_token)
bot.start()
bot.stop()

app = Client("TG_Download_User", api_id, api_hash)
app.start()
app.stop()