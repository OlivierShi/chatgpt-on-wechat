from datetime import datetime
import os
import uuid
import argparse
from LightAgent.lightagent.prompts.prompt_generator import PromptGenerator
from LightAgent.lightagent.storage.conversation_manager import ConversationManager
from LightAgent.lightagent.storage.logger import Logger
from LightAgent.lightagent.storage.sqlite import SQLiteStorage    
from LightAgent.lightagent.data_schemas import Message, UserProfile
from LightAgent.lightagent.data_schemas import ReplyType as LA_ReplyType
from LightAgent.lightagent.llms import GPT35, Phi3
from LightAgent.lightagent.plugins import PluginRunner
from LightAgent.lightagent.LightAgent import LightAgent

from bot.bot import Bot
import requests
import io
import uuid
from typing import Tuple
import hashlib
from common import const
from bot.bot import Bot
from bot.chatgpt.chat_gpt_session import ChatGPTSession
from bot.session_manager import SessionManager
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger as common_logger
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
        common_logger.info("LightAgentBot init")

    def reply(self, query, context=None):
        if context.type == ContextType.TEXT:
            common_logger.info("[LightAgent] query={}".format(query))
            session_id = context["session_id"]
            session = self.sessions.session_query(query, session_id)
            common_logger.info("[LightAgent] context={}".format(context))
            # reply_content = self.reply_text(session, context["receiver"])
            reply_by_agent, _metrics = self.agent_reply(session, context["receiver"])
            self.sessions.session_reply(reply_by_agent.content, session_id, _metrics.get("total_tokens", int(len(reply_by_agent.content) / 5) + int(len(query) / 5)))
            if reply_by_agent.reply.rtype == LA_ReplyType.IMAGE and reply_by_agent.reply.image_path is not None:
                common_logger.info("[LightAgent] reply image={}".format(reply_by_agent.reply.image_path))
                with open(reply_by_agent.reply.image_path, "rb") as f:
                    reply = Reply(ReplyType.IMAGE, io.BytesIO(f.read()))
            else:
                reply = Reply(ReplyType.TEXT, reply_by_agent.reply.content)
            return reply

    def agent_reply(self, session: ChatGPTSession, receiver: str) -> Tuple[Message, dict]:
        msg_id = self.gen_uuid()
        user_id = self.gen_uuid(receiver)
        user = UserProfile(user_id, user_id, datetime.now())
        if session.is_beginning():
            common_logger.info("[LightAgent] session is beginning")
            conv_id = self.agent.initiate_conversation(user)
        else:
            conv_id = self.gen_uuid(session.session_id)
        
        common_logger.info("[LightAgent] conv_id={}".format(conv_id))
        user_query = session.get_latest_user_query()
        if user_query is None or user_query == "":
            user_query = "你好啊"
        
        message = Message(msg_id, user_query, datetime.now(), conv_id, ["web_search", "message_in_a_bottle", "image_generator"])
        reply_message, _metrics = self.agent.chat(message)
        return reply_message, _metrics

    def gen_uuid(self, id: str = None) -> str:
        if id is not None and id != "":
            uuid_str = id
        else:
            uuid_str = str(uuid.uuid4())

        hash_object = hashlib.sha256(uuid_str.encode())
        return hash_object.hexdigest()[:8]