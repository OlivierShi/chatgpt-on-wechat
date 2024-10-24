import sys
from pathlib import Path
import os
sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append("..")
from config import load_config
from bot.bot_factory import create_bot
from common import const
from bridge.context import Context, ContextType


load_config()
bot = create_bot(const.LIGHTAGENT)

sess = bot.sessions.build_session(session_id="abcd")

ctx = Context(ContextType.TEXT, kwargs={"session_id": sess.session_id})
res = bot.reply(query="hello", context=ctx)
print(res)

res = bot.reply(query="你是谁", context=ctx)
print(res)