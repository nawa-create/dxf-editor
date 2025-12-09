"""
Natural Language Interpretation Router
Handles natural language command parsing and rule matching.
"""
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.interpreter import Interpreter

router = APIRouter()

interpreter = Interpreter()


class InterpretRequest(BaseModel):
    text: str
    session_id: str
    context: Optional[dict] = None


class OperationCommand(BaseModel):
    operation: str
    params: dict
    confidence: float
    explanation: str


class InterpretResponse(BaseModel):
    success: bool
    commands: List[OperationCommand]
    message: str
    used_ai: bool


@router.post("/parse", response_model=InterpretResponse)
async def parse_command(request: InterpretRequest):
    """自然言語コマンドを解釈"""
    try:
        result = await interpreter.interpret(
            request.text,
            request.session_id,
            request.context
        )
        
        return InterpretResponse(
            success=True,
            commands=[OperationCommand(**cmd) for cmd in result['commands']],
            message=result['message'],
            used_ai=result['used_ai']
        )
    except Exception as e:
        return InterpretResponse(
            success=False,
            commands=[],
            message=f"解釈エラー: {str(e)}",
            used_ai=False
        )


class RuleCreate(BaseModel):
    pattern: str
    operation: str
    params: dict
    description: str


@router.post("/rules")
async def add_rule(rule: RuleCreate):
    """新しいルールを追加"""
    try:
        interpreter.add_rule(
            pattern=rule.pattern,
            operation=rule.operation,
            params=rule.params,
            description=rule.description
        )
        return {"message": "ルールを追加しました"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/rules")
async def list_rules():
    """登録済みルールを一覧"""
    return {"rules": interpreter.get_rules()}
