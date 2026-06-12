from functools import lru_cache
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.messages import HumanMessage, AIMessage
from db.conversation_repo import ConversationRepository
from agent.tool.agent_tools import get_rag_service


@lru_cache(maxsize=1)
def _get_react_agent():
    from agent.react_agent import ReactAgent
    return ReactAgent()


class ChatService:
    def __init__(self, db: AsyncSession):
        self.store = ConversationRepository(db)

    async def process_message(
        self, message: str, chat_id: str | None
    ) -> tuple[str, list[str], str]:
        if not chat_id:
            conv_id = await self.store.create_conversation(
                user_id="anonymous",
                title=message[:30] + ("..." if len(message) > 30 else ""),
            )
            chat_id = str(conv_id)

        conv_uuid = UUID(chat_id)

        history = await self.store.get_recent_messages(conv_uuid)

        agent = _get_react_agent()
        answer = await agent.aexecute(message, history)

        rag_service = get_rag_service()
        sources = rag_service.get_sources(message)

        await self.store.add_messages(conv_uuid, [
            HumanMessage(content=message),
            AIMessage(content=answer),
        ])

        return answer, sources, chat_id
