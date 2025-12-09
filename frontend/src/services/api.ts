/**
 * API Service
 * Backend API communication layer
 */
import type { DxfInfo, OperationResult, InterpretResponse, PartInfo } from '../types';

// API URLを環境変数から読み取り（Viteでは import.meta.env を使用）
// VITE_API_URL が設定されていれば使用、なければ相対パス
const API_BASE = import.meta.env.VITE_API_URL
    ? `${import.meta.env.VITE_API_URL}/api`
    : '/api';

class ApiError extends Error {
    constructor(public status: number, message: string) {
        super(message);
        this.name = 'ApiError';
    }
}

async function handleResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new ApiError(response.status, error.detail || 'Request failed');
    }
    return response.json();
}

export const api = {
    /**
     * DXFファイルをアップロード
     */
    async uploadDxf(file: File): Promise<DxfInfo> {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch(`${API_BASE}/dxf/upload`, {
            method: 'POST',
            body: formData,
        });
        return handleResponse<DxfInfo>(response);
    },

    /**
     * SVGプレビューを取得
     */
    async getPreview(sessionId: string, highlightHandles?: string[]): Promise<{ svg: string }> {
        const params = new URLSearchParams();
        if (highlightHandles?.length) {
            params.set('highlight_handles', highlightHandles.join(','));
        }

        const url = `${API_BASE}/dxf/preview/${sessionId}?${params}`;
        const response = await fetch(url);
        return handleResponse<{ svg: string }>(response);
    },

    /**
     * 部材の紐づけ解析を実行
     */
    async analyzeParts(sessionId: string): Promise<PartInfo[]> {
        const response = await fetch(`${API_BASE}/dxf/analyze-parts/${sessionId}`, {
            method: 'POST',
        });
        return handleResponse<PartInfo[]>(response);
    },

    /**
     * 操作のプレビュー
     */
    async previewOperation(
        sessionId: string,
        operation: string,
        params: Record<string, unknown>
    ): Promise<OperationResult> {
        const response = await fetch(`${API_BASE}/dxf/preview-operation`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId, operation, params }),
        });
        return handleResponse<OperationResult>(response);
    },

    /**
     * 操作を実行
     */
    async executeOperation(
        sessionId: string,
        operation: string,
        params: Record<string, unknown>
    ): Promise<OperationResult> {
        const response = await fetch(`${API_BASE}/dxf/execute`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId, operation, params }),
        });
        return handleResponse<OperationResult>(response);
    },

    /**
     * 編集済みDXFのダウンロードURL取得
     */
    getDownloadUrl(sessionId: string): string {
        return `${API_BASE}/dxf/download/${sessionId}`;
    },

    /**
     * 自然言語コマンドを解釈
     */
    async interpretCommand(
        text: string,
        sessionId: string,
        context?: {
            layers?: any[];
            colors_used?: any[];
            parts?: any[];
            selected_parts?: string[];
        }
    ): Promise<InterpretResponse> {
        const response = await fetch(`${API_BASE}/interpret/parse`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                text,
                session_id: sessionId,
                context,
            }),
        });
        return handleResponse<InterpretResponse>(response);
    },

    /**
     * セッションを削除
     */
    async deleteSession(sessionId: string): Promise<void> {
        await fetch(`${API_BASE}/dxf/session/${sessionId}`, {
            method: 'DELETE',
        });
    },

    /**
     * Undo
     */
    async undo(sessionId: string): Promise<OperationResult> {
        const response = await fetch(`${API_BASE}/dxf/undo`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId, operation: 'undo', params: {} }),
        });
        return handleResponse<OperationResult>(response);
    },

    /**
     * Redo
     */
    async redo(sessionId: string): Promise<OperationResult> {
        const response = await fetch(`${API_BASE}/dxf/redo`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId, operation: 'redo', params: {} }),
        });
        return handleResponse<OperationResult>(response);
    },

    /**
     * 登録済みルールを取得
     */
    async getRules(): Promise<{ rules: Array<{ pattern: string; description: string }> }> {
        const response = await fetch(`${API_BASE}/interpret/rules`);
        return handleResponse<{ rules: Array<{ pattern: string; description: string }> }>(response);
    },
};
