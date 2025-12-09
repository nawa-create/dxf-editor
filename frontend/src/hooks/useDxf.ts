import { useState, useCallback, useRef, useEffect } from 'react';
import type { DxfInfo, OperationCommand, OperationResult, AppState, PartInfo } from '../types';
import { api } from '../services/api';

interface UseDxfReturn {
    // 状態
    state: AppState;
    dxfInfo: DxfInfo | null;
    parts: PartInfo[];
    svg: string;
    originalSvg: string;
    pendingCommand: OperationCommand | null;
    operationHistory: OperationResult[];
    error: string | null;

    // アクション
    uploadFile: (file: File) => Promise<void>;
    interpretCommand: (text: string) => Promise<void>;
    previewOperation: (command: OperationCommand) => Promise<void>;
    executeOperation: () => Promise<void>;
    cancelOperation: () => void;
    downloadFile: () => void;
    reset: () => void;
    undo: () => Promise<void>;
    redo: () => Promise<void>;
}

export function useDxf(): UseDxfReturn {
    const [state, setState] = useState<AppState>('initial');
    const [dxfInfo, setDxfInfo] = useState<DxfInfo | null>(null);
    const [parts, setParts] = useState<PartInfo[]>([]);
    const [svg, setSvg] = useState<string>('');
    const [originalSvg, setOriginalSvg] = useState<string>('');
    const [pendingCommand, setPendingCommand] = useState<OperationCommand | null>(null);
    const [operationHistory, setOperationHistory] = useState<OperationResult[]>([]);
    const [error, setError] = useState<string | null>(null);

    const sessionIdRef = useRef<string | null>(null);

    // クリーンアップ
    useEffect(() => {
        return () => {
            if (sessionIdRef.current) {
                api.deleteSession(sessionIdRef.current).catch(() => { });
            }
        };
    }, []);

    const uploadFile = useCallback(async (file: File) => {
        setState('loading');
        setError(null);

        try {
            const info = await api.uploadDxf(file);
            setDxfInfo(info);
            sessionIdRef.current = info.session_id;

            // 初期プレビュー取得
            const preview = await api.getPreview(info.session_id);
            setSvg(preview.svg);
            setOriginalSvg(preview.svg);

            // 自動で部材解析を実行
            api.analyzeParts(info.session_id)
                .then(partsdata => setParts(partsdata))
                .catch(console.error);

            setState('ready');
        } catch (e) {
            setError(e instanceof Error ? e.message : 'ファイルのアップロードに失敗しました');
            setState('error');
        }
    }, []);

    const interpretCommand = useCallback(async (text: string, selectedParts: string[] = []) => {
        if (!sessionIdRef.current) {
            setError('ファイルが読み込まれていません');
            return;
        }

        setState('loading');
        setError(null);

        try {
            // コンテキスト情報の構築
            const context = {
                layers: dxfInfo?.layers || [],
                colors_used: dxfInfo?.colors_used || [],
                parts: parts || [],
                selected_parts: selectedParts  // 選択された部材を追加
            };

            const result = await api.interpretCommand(text, sessionIdRef.current, context);

            if (!result.success || result.commands.length === 0) {
                setError(result.message);
                setState('ready');
                return;
            }

            // 最初のコマンドをプレビュー
            const command = result.commands[0];
            setPendingCommand(command);

            await previewOperation(command);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'コマンドの解釈に失敗しました');
            setState('ready');
        }
    }, [dxfInfo, parts]);

    const previewOperation = useCallback(async (command: OperationCommand) => {
        if (!sessionIdRef.current) return;

        setPendingCommand(command);
        setState('previewing');
        setError(null);

        try {
            const result = await api.previewOperation(
                sessionIdRef.current,
                command.operation,
                command.params as Record<string, unknown>
            );

            if (result.preview_svg) {
                setSvg(result.preview_svg);
            }

            setError(`${result.affected_count}個のエンティティが影響を受けます`);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'プレビューの生成に失敗しました');
            setState('ready');
        }
    }, []);

    const executeOperation = useCallback(async () => {
        if (!sessionIdRef.current || !pendingCommand) return;

        setState('executing');
        setError(null);

        try {
            const result = await api.executeOperation(
                sessionIdRef.current,
                pendingCommand.operation,
                pendingCommand.params as Record<string, unknown>
            );

            if (result.preview_svg) {
                setSvg(result.preview_svg);
            }

            setOperationHistory(prev => [...prev, result]);
            setPendingCommand(null);
            setError(null);
            setState('ready');
        } catch (e) {
            setError(e instanceof Error ? e.message : '操作の実行に失敗しました');
            setState('ready');
        }
    }, [pendingCommand]);

    const cancelOperation = useCallback(async () => {
        if (!sessionIdRef.current) return;

        setPendingCommand(null);
        setError(null);

        // 元のプレビューに戻す
        try {
            const preview = await api.getPreview(sessionIdRef.current);
            setSvg(preview.svg);
        } catch (e) {
            // ignore
        }

        setState('ready');
    }, []);

    const downloadFile = useCallback(() => {
        if (!sessionIdRef.current) return;

        const url = api.getDownloadUrl(sessionIdRef.current);
        window.open(url, '_blank');
    }, []);

    const undo = useCallback(async () => {
        if (!sessionIdRef.current) return;
        setState('executing');
        try {
            const result = await api.undo(sessionIdRef.current);
            setSvg(result.preview_svg || '');
            setOperationHistory(prev => [...prev, result]);
            setError('元に戻しました');
            setState('ready');
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Undoに失敗しました');
            setState('ready');
        }
    }, []);

    const redo = useCallback(async () => {
        if (!sessionIdRef.current) return;
        setState('executing');
        try {
            const result = await api.redo(sessionIdRef.current);
            setSvg(result.preview_svg || '');
            setOperationHistory(prev => [...prev, result]);
            setError('やり直しました');
            setState('ready');
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Redoに失敗しました');
            setState('ready');
        }
    }, []);

    const reset = useCallback(async () => {
        if (sessionIdRef.current) {
            await api.deleteSession(sessionIdRef.current).catch(() => { });
        }

        sessionIdRef.current = null;
        setDxfInfo(null);
        setParts([]);
        setSvg('');
        setPendingCommand(null);
        setOperationHistory([]);
        setError(null);
        setState('initial');
    }, []);

    return {
        state,
        dxfInfo,
        parts,
        svg,
        originalSvg,
        pendingCommand,
        operationHistory,
        error,
        uploadFile,
        interpretCommand,
        previewOperation,
        executeOperation,
        cancelOperation,
        downloadFile,
        reset,
        undo,
        redo,
    };
}
