from datetime import datetime
import os
import uuid
import argparse
from LightAgent.lightagent.prompts.prompt_generator import PromptGenerator
from LightAgent.lightagent.storage.conversation_manager import ConversationManager
from LightAgent.lightagent.storage.logger import Logger
from LightAgent.lightagent.storage.sqlite import SQLiteStorage    
from LightAgent.lightagent.data_schemas import Message, UserProfile
from LightAgent.lightagent.llms import GPT35, Phi3
from LightAgent.lightagent.plugins import PluginRunner
from LightAgent.lightagent.LightAgent import LightAgent

from bot.bot import Bot
import requests
import uuid
import hashlib
from common import const
from bot.bot import Bot
from bot.chatgpt.chat_gpt_session import ChatGPTSession
from bot.session_manager import SessionManager
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
from common.token_bucket import TokenBucket
from config import conf, load_config
from bot.baidu.baidu_wenxin_session import BaiduWenxinSession

current_file_path = os.path.abspath(__file__)
current_directory = os.path.dirname(current_file_path)

class LightAgentBot(Bot):
    def __init__(self):
        super().__init__()
        db_file = os.path.join(current_directory, "la-sqlite.db")
        db = SQLiteStorage(db_file)
        cm = ConversationManager(db)
        logger = Logger(db)
        self.agent = LightAgent(PromptGenerator(), GPT35(), cm, PluginRunner(), logger)
        self.sessions = SessionManager(ChatGPTSession, model=conf().get("model") or "gpt-3.5-turbo")

    def reply(self, query, context=None):
        if context.type == ContextType.TEXT:
            logger.info("[CHATGPT] query={}".format(query))
            session_id = context["session_id"]
            session = self.sessions.session_query(query, session_id)
            logger.info("[CHATGPT] context={}".format(context))
            reply_content = self.reply_text(session, context["receiver"])
            self.sessions.session_reply(reply_content["content"], session_id, reply_content["total_tokens"])
            reply = Reply(ReplyType.TEXT, reply_content["content"])
            return reply

    def reply_text(self, session: ChatGPTSession, receiver: str):
        msg_id = self.gen_uuid()
        user_id = self.gen_uuid(receiver)
        user = UserProfile(user_id, user_id, datetime.now())
        if session.is_beginning():
            logger.info("[CHATGPT] session is beginning")
            conv_id = self.agent.initiate_conversation(user)
        else:
            conv_id = self.gen_uuid(session.session_id)
        
        logger.info("[CHATGPT] conv_id={}".format(conv_id))
        user_query = session.get_latest_user_query()
        if user_query is None or user_query == "":
            user_query = "你好啊"
        
        message = Message(msg_id, user_query, datetime.now(), conv_id, ["web_search", "message_in_a_bottle"])
        reply_message, _metrics = self.agent.chat(message)
        return {
                "total_tokens": _metrics.get("total_tokens", int(len(reply_message.response) / 5) + int(len(user_query) / 5)),
                "completion_tokens": _metrics.get("completion_tokens", int(len(reply_message.response) / 5)),
                "content": reply_message.response,
            }

    def gen_uuid(self, id: str = None) -> str:
        if id is not None and id != "":
            uuid_str = id
        else:
            uuid_str = str(uuid.uuid4())

        hash_object = hashlib.sha256(uuid_str.encode())
        return hash_object.hexdigest()[:8]