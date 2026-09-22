import asyncio
from dataclasses import dataclass
from functools import lru_cache
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from core.config import db_conf
from core.logger import logger
from db.conversation_repo import ConversationRepository
from rag.rag_service import (
    _sources_ctx,
    collect_sources,
    reset_topic_context,
    start_sources_collection,
    start_topic_context,
)
from schemas.topic import TopicDecision
from services.context_builder import ContextBuilder
from services.guard_service import get_guard_service
from services.memory_service import MemoryService
from services.summary_service import get_summary_service
from services.topic_router import get_topic_router


_REFUSAL_MARKER = "暂无法回答该问题"
_DEFAULT_CLARIFICATION = "请补充您指的是哪件服装或哪个商品？"


class ConversationNotFoundError(LookupError):
    """请求继续一个不存在的会话。"""


@dataclass(slots=True)
class ChatResult:
    answer: str
    sources: list[str]
    chat_id: str
    topic_id: str | None
    topic_action: str


@lru_cache(maxsize=1)
def _get_react_agent():
    from agent.react_agent import ReactAgent

    return ReactAgent()


class ChatService:
    def __init__(self, db: AsyncSession):
        self.store = ConversationRepository(db)
        self.context_builder = ContextBuilder()
        self.memory_enabled = bool(db_conf.get("conversation_memory_enabled", True))
        self.router_enabled = bool(db_conf.get("topic_router_enabled", True))
        self.long_term_memory_enabled = bool(
            db_conf.get("long_term_memory_enabled", True)
        )
        self.summary_enabled = bool(db_conf.get("summary_enabled", True))
        self.topic_router = get_topic_router() if self.router_enabled else None
        self.memory_service = (
            MemoryService(self.store.memories)
            if self.memory_enabled and self.long_term_memory_enabled
            else None
        )

    async def process_message(
        self,
        message: str,
        chat_id: UUID | None,
        user_id: str = "anonymous",
    ) -> ChatResult:
        message = message.strip()
        user_id = (user_id or "anonymous").strip()[:64] or "anonymous"
        conv_uuid = chat_id
        active_topic = None
        recent_records = []
        memories = []

        if conv_uuid is not None and await self.store.get_conversation(conv_uuid) is None:
            raise ConversationNotFoundError(str(conv_uuid))

        if self.memory_enabled:
            if conv_uuid is not None:
                active_topic = await self.store.topics.get_active(conv_uuid)
                if active_topic is not None:
                    recent_records = await self.store.get_recent_topic_records(active_topic.id)
            if self.memory_service is not None:
                # 长期偏好属于用户，不依赖当前是否已经创建会话。
                memories = await self.memory_service.list_for_prompt(user_id)

        decision = await self._route(
            message,
            active_topic=active_topic,
            recent_records=recent_records,
            memories=memories,
        )

        if decision.action == "CLARIFY":
            return await self._handle_clarify(
                message,
                conv_uuid,
                user_id,
                active_topic,
                decision,
            )

        in_segments = [
            segment
            for segment in decision.segments
            if segment.scope == "IN" and segment.query.strip()
        ]
        out_segments = [
            segment
            for segment in decision.segments
            if segment.scope == "OUT" and segment.query.strip()
        ]

        if decision.action == "MIXED":
            if not in_segments:
                return await self._handle_out_of_scope(
                    message,
                    conv_uuid,
                    active_topic,
                    decision,
                )
            effective_query = "；".join(segment.query.strip() for segment in in_segments)
        else:
            effective_query = decision.canonical_query.strip() or message

        if decision.action == "OUT_OF_SCOPE" or decision.scope == "OUT":
            return await self._handle_out_of_scope(
                message,
                conv_uuid,
                active_topic,
                decision,
            )

        # 主题路由是上下文控制层，旧 Guard 仍保留作为代码级域边界兜底。
        guard_service = get_guard_service()
        in_scope = await asyncio.to_thread(
            guard_service.check_question_scope, effective_query
        )
        if not in_scope:
            decision.action = "OUT_OF_SCOPE"
            decision.scope = "OUT"
            return await self._handle_out_of_scope(
                message,
                conv_uuid,
                active_topic,
                decision,
            )

        if self.memory_enabled:
            active_topic = await self._prepare_topic(
                conv_uuid,
                active_topic,
                decision,
            )
            if active_topic is not None and decision.action != "NEW_TOPIC":
                recent_records = await self.store.get_recent_topic_records(active_topic.id)
        else:
            recent_records = []
            memories = []

        topic_label = (
            active_topic.topic_label
            if active_topic is not None
            else decision.topic_label or "服装咨询"
        )
        prompt_memories = (
            self.memory_service.select_for_query(
                memories,
                effective_query,
                intent=decision.intent,
            )
            if self.memory_service is not None
            else []
        )
        context = self.context_builder.build(
            current_message=effective_query,
            topic=active_topic,
            recent_messages=recent_records,
            memories=prompt_memories,
        )

        answer, sources = await self._execute_agent(
            effective_query,
            context,
            topic_label,
        )
        ok, guarded_answer = await asyncio.to_thread(
            guard_service.check, effective_query, answer
        )
        if not ok:
            return await self._handle_refusal(
                message,
                guarded_answer,
                conv_uuid,
                active_topic,
                decision,
            )

        answer = guarded_answer
        is_refusal = _REFUSAL_MARKER in answer
        mixed_has_out = decision.action == "MIXED" and bool(out_segments)
        display_answer = answer
        if mixed_has_out and not is_refusal:
            display_answer = f"{answer}\n\n{guard_service.refusal_text}"

        # 没有有效知识回答时只保留审计记录，不将拒答内容写入新的会话上下文。
        if is_refusal:
            return await self._handle_refusal(
                message,
                display_answer,
                conv_uuid,
                active_topic,
                decision,
            )

        if conv_uuid is None:
            conv_uuid = await self.store.create_conversation(
                user_id=user_id,
                title=message[:15] + ("..." if len(message) > 15 else ""),
                create_topic=self.memory_enabled,
            )
            if self.memory_enabled:
                active_topic = await self.store.topics.get_active(conv_uuid)

        if self.memory_enabled and active_topic is None:
            active_topic = await self.store.topics.create(
                conv_uuid,
                decision.topic_label or "服装咨询",
                intent=decision.intent,
                scope_label="IN",
                confidence=decision.confidence,
            )
        elif self.memory_enabled:
            await self.store.topics.update_metadata(
                active_topic.id,
                topic_label=decision.topic_label or None,
                intent=decision.intent,
                scope_label="IN",
                confidence=decision.confidence,
            )

        human_record, _ = await self.store.add_turn(
            conv_uuid,
            active_topic.id if active_topic is not None else None,
            message,
            display_answer,
            intent=decision.intent,
            scope_label="IN",
            is_refusal=False,
            memory_eligible=not mixed_has_out,
        )

        if self.summary_enabled and active_topic is not None:
            await self._update_summary(
                active_topic,
                effective_query,
                answer,
            )
        if self.memory_enabled and self.memory_service is not None:
            await self.memory_service.extract_and_save(
                user_id=user_id,
                user_message=message,
                source_message=human_record,
            )

        return ChatResult(
            answer=display_answer,
            sources=sources,
            chat_id=str(conv_uuid),
            topic_id=str(active_topic.id) if active_topic else None,
            topic_action=decision.action,
        )

    async def _route(
        self,
        message: str,
        *,
        active_topic,
        recent_records,
        memories,
    ) -> TopicDecision:
        if not self.memory_enabled or self.topic_router is None:
            return TopicDecision(
                action="CONTINUE",
                topic_label=active_topic.topic_label if active_topic else "服装咨询",
                intent=active_topic.last_intent if active_topic else "general",
                canonical_query=message,
                scope="IN",
            )
        return await asyncio.to_thread(
            self.topic_router.route,
            message,
            topic=active_topic,
            recent_messages=recent_records,
            memories=memories,
        )

    async def _prepare_topic(self, conv_uuid, active_topic, decision):
        if conv_uuid is None:
            return active_topic
        if decision.action == "NEW_TOPIC":
            return await self.store.topics.switch_topic(
                conv_uuid,
                decision.topic_label or "服装咨询",
                intent=decision.intent,
                scope_label="IN",
                confidence=decision.confidence,
            )
        if active_topic is None:
            return await self.store.topics.create(
                conv_uuid,
                decision.topic_label or "服装咨询",
                intent=decision.intent,
                scope_label="IN",
                confidence=decision.confidence,
            )
        return active_topic

    async def _execute_agent(
        self,
        query: str,
        context: str,
        topic_label: str,
    ) -> tuple[str, list[str]]:
        agent = _get_react_agent()
        source_token = start_sources_collection()
        topic_token = start_topic_context(topic_label)
        try:
            answer = await agent.aexecute(query, context)
            return answer, collect_sources()
        finally:
            _sources_ctx.reset(source_token)
            reset_topic_context(topic_token)

    async def _handle_clarify(
        self,
        message: str,
        conv_uuid,
        user_id: str,
        active_topic,
        decision: TopicDecision,
    ) -> ChatResult:
        answer = decision.clarification_question.strip() or _DEFAULT_CLARIFICATION
        if conv_uuid is None:
            conv_uuid = await self.store.create_conversation(
                user_id=user_id,
                title=message[:15] + ("..." if len(message) > 15 else ""),
                create_topic=self.memory_enabled,
            )
            if self.memory_enabled:
                active_topic = await self.store.topics.get_active(conv_uuid)
        if self.memory_enabled and active_topic is None:
            active_topic = await self.store.topics.create(conv_uuid)
        await self.store.add_turn(
            conv_uuid,
            active_topic.id if active_topic is not None else None,
            message,
            answer,
            intent="clarification",
            scope_label="IN",
            is_refusal=False,
            memory_eligible=False,
        )
        return ChatResult(
            answer=answer,
            sources=[],
            chat_id=str(conv_uuid),
            topic_id=str(active_topic.id) if active_topic else None,
            topic_action="CLARIFY",
        )

    async def _handle_out_of_scope(
        self,
        message: str,
        conv_uuid,
        active_topic,
        decision: TopicDecision,
    ) -> ChatResult:
        guard_service = get_guard_service()
        answer = guard_service.refusal_text
        if conv_uuid is not None:
            active_topic = await self._ensure_existing_topic(conv_uuid, active_topic)
            if active_topic is not None:
                await self.store.add_turn(
                    conv_uuid,
                    active_topic.id,
                    message,
                    answer,
                    intent=decision.intent or "out_of_scope",
                    scope_label="OUT",
                    is_refusal=True,
                    memory_eligible=False,
                )
        return ChatResult(
            answer=answer,
            sources=[],
            chat_id=str(conv_uuid) if conv_uuid else "",
            topic_id=str(active_topic.id) if active_topic else None,
            topic_action="OUT_OF_SCOPE",
        )

    async def _handle_refusal(
        self,
        message: str,
        answer: str,
        conv_uuid,
        active_topic,
        decision: TopicDecision,
    ) -> ChatResult:
        if conv_uuid is not None:
            active_topic = await self._ensure_existing_topic(conv_uuid, active_topic)
            if active_topic is not None:
                await self.store.add_turn(
                    conv_uuid,
                    active_topic.id,
                    message,
                    answer,
                    intent=decision.intent or "refusal",
                    scope_label="IN",
                    is_refusal=True,
                    memory_eligible=False,
                )
        return ChatResult(
            answer=answer,
            sources=[],
            chat_id=str(conv_uuid) if conv_uuid else "",
            topic_id=str(active_topic.id) if active_topic else None,
            topic_action=decision.action,
        )

    async def _ensure_existing_topic(self, conv_uuid, active_topic):
        if not self.memory_enabled:
            return None
        if active_topic is not None:
            return active_topic
        return await self.store.topics.create(conv_uuid)

    async def _update_summary(self, topic, query: str, answer: str) -> None:
        summary_service = get_summary_service()
        try:
            summary = await asyncio.to_thread(
                summary_service.summarize,
                topic,
                query,
                answer,
            )
        except Exception as exc:
            logger.warning("[SummaryService] 摘要更新失败，保留旧摘要: %s", exc)
            return
        if summary:
            await self.store.topics.update_summary(
                topic.id,
                summary,
                topic.summary_version,
            )
