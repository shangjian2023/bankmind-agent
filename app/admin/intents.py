"""意图定义管理"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.data import database
from app.admin.auth import get_current_admin

router = APIRouter(prefix="/admin/intents", tags=["admin-intents"])


class IntentDefinition(BaseModel):
    intent_name: str
    description: str
    examples: List[str]
    enabled: bool = True
    priority: int = 0


class IntentDefinitionUpdate(BaseModel):
    description: Optional[str]
    examples: Optional[List[str]]
    enabled: Optional[bool]
    priority: Optional[int]


class IntentDefinitionResponse(BaseModel):
    id: int
    intent_name: str
    description: str
    examples: List[str]
    enabled: bool
    priority: int
    created_at: str
    updated_at: str


class IntentDefinitionListResponse(BaseModel):
    intents: List[IntentDefinitionResponse]
    total: int


@router.get("", response_model=IntentDefinitionListResponse)
async def list_intents(
    enabled_only: bool = False,
    current_admin: dict = Depends(get_current_admin)
):
    """获取意图定义列表"""
    query = "SELECT * FROM intent_definitions"
    params = []

    if enabled_only:
        query += " WHERE enabled = 1"

    query += " ORDER BY priority DESC, intent_name"

    with database.connect() as conn:
        intents = [dict(row) for row in conn.execute(query, params).fetchall()]

    # 解析 examples JSON
    for intent in intents:
        if intent["examples"]:
            try:
                intent["examples"] = json.loads(intent["examples"])
            except:
                intent["examples"] = []
        else:
            intent["examples"] = []

    return IntentDefinitionListResponse(
        intents=[IntentDefinitionResponse(**intent) for intent in intents],
        total=len(intents)
    )


@router.post("", response_model=IntentDefinitionResponse, status_code=status.HTTP_201_CREATED)
async def create_intent(
    intent_data: IntentDefinition,
    current_admin: dict = Depends(get_current_admin)
):
    """创建意图定义"""
    import json
    now = datetime.now().isoformat()

    with database.connect() as conn:
        # 检查是否已存在
        existing = conn.execute(
            "SELECT id FROM intent_definitions WHERE intent_name = ?",
            (intent_data.intent_name,)
        ).fetchone()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Intent already exists"
            )

        cursor = conn.execute(
            """INSERT INTO intent_definitions
               (intent_name, description, examples, enabled, priority, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (intent_data.intent_name, intent_data.description,
             json.dumps(intent_data.examples, ensure_ascii=False),
             intent_data.enabled, intent_data.priority, now, now)
        )

        intent_id = cursor.lastrowid

        # 记录操作日志
        conn.execute(
            """INSERT INTO admin_logs
               (admin_id, action, target_type, target_id, details, created_at)
               VALUES (?, 'create_intent', 'intent', ?, ?, ?)""",
            (current_admin["user_id"], str(intent_id),
             f'{{"intent_name": "{intent_data.intent_name}"}}', now)
        )

        intent = conn.execute(
            "SELECT * FROM intent_definitions WHERE id = ?",
            (intent_id,)
        ).fetchone()

    intent_dict = dict(intent)
    intent_dict["examples"] = json.loads(intent_dict["examples"]) if intent_dict["examples"] else []

    return IntentDefinitionResponse(**intent_dict)


@router.get("/{intent_name}", response_model=IntentDefinitionResponse)
async def get_intent(
    intent_name: str,
    current_admin: dict = Depends(get_current_admin)
):
    """获取意图详情"""
    import json

    with database.connect() as conn:
        intent = conn.execute(
            "SELECT * FROM intent_definitions WHERE intent_name = ?",
            (intent_name,)
        ).fetchone()

        if not intent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Intent not found"
            )

    intent_dict = dict(intent)
    intent_dict["examples"] = json.loads(intent_dict["examples"]) if intent_dict["examples"] else []

    return IntentDefinitionResponse(**intent_dict)


@router.put("/{intent_name}", response_model=IntentDefinitionResponse)
async def update_intent(
    intent_name: str,
    intent_data: IntentDefinitionUpdate,
    current_admin: dict = Depends(get_current_admin)
):
    """更新意图定义"""
    import json

    with database.connect() as conn:
        intent = conn.execute(
            "SELECT * FROM intent_definitions WHERE intent_name = ?",
            (intent_name,)
        ).fetchone()

        if not intent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Intent not found"
            )

        updates = []
        params = []

        if intent_data.description is not None:
            updates.append("description = ?")
            params.append(intent_data.description)
        if intent_data.examples is not None:
            updates.append("examples = ?")
            params.append(json.dumps(intent_data.examples, ensure_ascii=False))
        if intent_data.enabled is not None:
            updates.append("enabled = ?")
            params.append(intent_data.enabled)
        if intent_data.priority is not None:
            updates.append("priority = ?")
            params.append(intent_data.priority)

        if updates:
            updates.append("updated_at = ?")
            params.append(datetime.now().isoformat())
            params.append(intent_name)

            conn.execute(
                f"UPDATE intent_definitions SET {', '.join(updates)} WHERE intent_name = ?",
                params
            )

            # 记录操作日志
            conn.execute(
                """INSERT INTO admin_logs
                   (admin_id, action, target_type, target_id, details, created_at)
                   VALUES (?, 'update_intent', 'intent', ?, ?, ?)""",
                (current_admin["user_id"], str(intent["id"]),
                 str({k: v for k, v in intent_data.dict().items() if v is not None}),
                 datetime.now().isoformat())
            )

        updated_intent = conn.execute(
            "SELECT * FROM intent_definitions WHERE intent_name = ?",
            (intent_name,)
        ).fetchone()

    intent_dict = dict(updated_intent)
    intent_dict["examples"] = json.loads(intent_dict["examples"]) if intent_dict["examples"] else []

    return IntentDefinitionResponse(**intent_dict)


@router.delete("/{intent_name}")
async def delete_intent(
    intent_name: str,
    current_admin: dict = Depends(get_current_admin)
):
    """删除意图定义"""
    with database.connect() as conn:
        intent = conn.execute(
            "SELECT * FROM intent_definitions WHERE intent_name = ?",
            (intent_name,)
        ).fetchone()

        if not intent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Intent not found"
            )

        conn.execute(
            "DELETE FROM intent_definitions WHERE intent_name = ?",
            (intent_name,)
        )

        # 记录操作日志
        conn.execute(
            """INSERT INTO admin_logs
               (admin_id, action, target_type, target_id, details, created_at)
               VALUES (?, 'delete_intent', 'intent', ?, ?, ?)""",
            (current_admin["user_id"], str(intent["id"]),
             f'{{"intent_name": "{intent_name}"}}', datetime.now().isoformat())
        )

    return {"message": "Intent deleted successfully"}


@router.post("/init-defaults")
async def init_default_intents(
    current_admin: dict = Depends(get_current_admin)
):
    """初始化默认意图定义"""
    import json
    now = datetime.now().isoformat()

    # 默认意图定义
    default_intents = [
        {
            "intent_name": "transfer",
            "description": "转账汇款",
            "examples": [
                "我要转账给张三",
                "给李四转500元",
                "汇款到王五的账户",
                "帮我转账"
            ],
            "enabled": True,
            "priority": 10
        },
        {
            "intent_name": "balance_query",
            "description": "查询余额",
            "examples": [
                "我的余额是多少",
                "查一下账户余额",
                "看看还有多少钱",
                "余额查询"
            ],
            "enabled": True,
            "priority": 10
        },
        {
            "intent_name": "bill_analysis",
            "description": "账单分析",
            "examples": [
                "分析一下我的账单",
                "这个月花了多少钱",
                "查看消费记录",
                "账单明细"
            ],
            "enabled": True,
            "priority": 8
        },
        {
            "intent_name": "card_query",
            "description": "查询卡片信息",
            "examples": [
                "我的银行卡信息",
                "查看卡片状态",
                "卡片限额是多少",
                "有哪些卡"
            ],
            "enabled": True,
            "priority": 8
        },
        {
            "intent_name": "card_apply",
            "description": "申请新卡",
            "examples": [
                "我想申请一张新卡",
                "办一张银行卡",
                "申请信用卡",
                "开卡"
            ],
            "enabled": True,
            "priority": 7
        },
        {
            "intent_name": "card_freeze",
            "description": "冻结卡片",
            "examples": [
                "冻结我的卡",
                "卡片丢了，帮我冻结",
                "临时锁卡",
                "挂失卡片"
            ],
            "enabled": True,
            "priority": 9
        }
    ]

    created_count = 0

    with database.connect() as conn:
        for intent in default_intents:
            existing = conn.execute(
                "SELECT id FROM intent_definitions WHERE intent_name = ?",
                (intent["intent_name"],)
            ).fetchone()

            if not existing:
                conn.execute(
                    """INSERT INTO intent_definitions
                       (intent_name, description, examples, enabled, priority, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (intent["intent_name"], intent["description"],
                     json.dumps(intent["examples"], ensure_ascii=False),
                     intent["enabled"], intent["priority"], now, now)
                )
                created_count += 1

    return {
        "message": f"Initialized {created_count} default intents",
        "created_count": created_count
    }
