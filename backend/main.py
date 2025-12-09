"""
DXF Natural Language Editor - Backend
FastAPI application for DXF file processing and natural language interpretation.
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import dxf, interpret

app = FastAPI(
    title="DXF Natural Language Editor",
    description="自然言語によるDXFファイル編集システム",
    version="0.1.0"
)

# CORS設定（環境変数からも許可オリジンを読み取り）
allowed_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
]

# 環境変数から追加のオリジンを読み取り
extra_origins = os.environ.get("ALLOWED_ORIGINS", "")
if extra_origins:
    allowed_origins.extend([o.strip() for o in extra_origins.split(",") if o.strip()])

# Renderのフロントエンド URL を自動追加
frontend_url = os.environ.get("FRONTEND_URL", "")
if frontend_url:
    allowed_origins.append(frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ルーターを登録
app.include_router(dxf.router, prefix="/api/dxf", tags=["DXF"])
app.include_router(interpret.router, prefix="/api/interpret", tags=["Interpret"])


@app.get("/")
async def root():
    return {"message": "DXF Natural Language Editor API", "version": "0.1.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}

