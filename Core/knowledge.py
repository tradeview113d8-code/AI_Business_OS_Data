from datetime import datetime
from Core.mongo import db


class KnowledgeType:
    MARKET_ANALYSIS     = "market_analysis"
    IMPLEMENTATION_PLAN = "implementation_plan"
    COMPETITIVE_REPORT  = "competitive_report"
    TECHNICAL_SPEC      = "technical_spec"
    RAW_IMPORT          = "raw_import"


def save_knowledge(
    source,
    knowledge_type,
    content,
    tags        = None,
    request_id  = None,
    metadata    = None
):
    """
    Lưu tri thức vào Knowledge Bus.
    Dùng Mongo Text Search — không cần Vector DB.

    Mọi repo đều import vào đây.
    """
    doc_id = db.knowledge.insert_one({
        "source":      source,
        "type":        knowledge_type,
        "request_id":  request_id,
        "content":     content,
        "tags":        tags or [],
        "metadata":    metadata or {},
        "created_at":  datetime.utcnow(),
        "updated_at":  datetime.utcnow()
    }).inserted_id

    from Core.event_bus import publish, EventType
    publish(EventType.KNOWLEDGE_READY, source, {
        "knowledge_id": str(doc_id),
        "type":         knowledge_type,
        "tags":         tags or []
    })

    return doc_id


def search_knowledge(query, knowledge_type=None, limit=10):
    """Text search trên knowledge base."""
    filter_q = {"$text": {"$search": query}}
    if knowledge_type:
        filter_q["type"] = knowledge_type
    return list(
        db.knowledge.find(filter_q, {"score": {"$meta": "textScore"}})
                    .sort([("score", {"$meta": "textScore"})])
                    .limit(limit)
    )


def get_knowledge(knowledge_id):
    from bson import ObjectId
    return db.knowledge.find_one({"_id": ObjectId(knowledge_id)})
