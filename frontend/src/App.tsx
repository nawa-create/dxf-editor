import { useState, useEffect } from 'react';
import { useDxf } from './hooks/useDxf';
import { DxfViewer } from './components/DxfViewer';
import { CommandInput } from './components/CommandInput';
import { EntityPanel } from './components/EntityPanel';
import { SuggestedCommands } from './components/SuggestedCommands';
import './App.css';

function App() {
    const {
        state,
        dxfInfo,
        parts,
        svg,
        originalSvg,
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
        pendingCommand,
    } = useDxf();

    // 部材選択状態
    const [selectedParts, setSelectedParts] = useState<string[]>([]);

    // ハイライト管理：選択された部材 + ホバー中の部材
    const [highlightedHandles, setHighlightedHandles] = useState<string[]>([]);
    const [hoverHandles, setHoverHandles] = useState<string[]>([]);

    // 選択された部材のハンドルを常にハイライト
    useEffect(() => {
        const selectedHandles: string[] = [];
        selectedParts.forEach(partName => {
            const part = parts.find(p => p.part_name === partName);
            if (part) {
                selectedHandles.push(part.text_handle);
                if (part.linked_handles) {
                    selectedHandles.push(...part.linked_handles);
                }
            }
        });

        // 選択されたハンドルとホバー中のハンドルをマージ
        const allHandles = [...new Set([...selectedHandles, ...hoverHandles])];
        setHighlightedHandles(allHandles);
    }, [selectedParts, hoverHandles, parts]);

    // 部材削除ハンドラ
    const handleDeletePart = (partName: string) => {
        previewOperation({
            operation: 'delete_part',
            params: { part_name: partName },
            confidence: 1.0,
            explanation: `部材「${partName}」を削除します`
        });
    };

    const handleHoverPart = (partName: string) => {
        const part = parts.find(p => p.part_name === partName);
        if (part && part.linked_handles) {
            // ホバー中のハンドルを設定（選択されたものと自動的にマージされる）
            setHoverHandles([part.text_handle, ...part.linked_handles]);
        } else if (part) {
            setHoverHandles([part.text_handle]);
        }
    };

    const handleLeavePart = () => {
        setHoverHandles([]);
    };

    const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            uploadFile(e.target.files[0]);
        }
    };

    const [isCompareMode, setIsCompareMode] = useState<boolean>(true);

    // 部材選択のトグル
    const handleTogglePartSelection = (partName: string) => {
        setSelectedParts(prev =>
            prev.includes(partName)
                ? prev.filter(p => p !== partName)
                : [...prev, partName]
        );
    };

    // すべて選択
    const handleSelectAll = () => {
        setSelectedParts(parts.map(p => p.part_name));
    };

    // 選択解除
    const handleClearSelection = () => {
        setSelectedParts([]);
    };

    return (
        <div className="app-container">
            <header className="app-header">
                <h1>DXF自然言語編集システム</h1>
                <div className="header-actions">
                    {dxfInfo && (
                        <>
                            <button
                                onClick={() => setIsCompareMode(!isCompareMode)}
                                className={`action-button ${isCompareMode ? 'active' : 'secondary'}`}
                                title="編集前後を比較"
                            >
                                ↔ 比較モード
                            </button>
                            <button
                                onClick={downloadFile}
                                className="action-button primary"
                                title="編集結果をダウンロード"
                            >
                                ダウンロード
                            </button>
                            <button
                                onClick={undo}
                                className="action-button secondary"
                                title="元に戻す"
                            >
                                ↶ Undo
                            </button>
                            <button
                                onClick={redo}
                                className="action-button secondary"
                                title="やり直す"
                            >
                                ↷ Redo
                            </button>
                            <button
                                onClick={reset}
                                className="action-button secondary"
                                title="初期状態に戻す"
                            >
                                リセット
                            </button>
                        </>
                    )}
                </div>
            </header>

            <main className="app-main">
                {state === 'initial' ? (
                    <div className="upload-container">
                        <div className="upload-box">
                            <h2>DXFファイルをアップロード</h2>
                            <p>編集したいDXFファイルをドラッグ&ドロップするか、選択してください</p>
                            <input
                                type="file"
                                accept=".dxf"
                                onChange={handleFileUpload}
                                className="file-input"
                                id="file-upload"
                            />
                            <label htmlFor="file-upload" className="upload-button">
                                ファイルを選択
                            </label>
                        </div>
                    </div>
                ) : (
                    <div className="editor-layout">
                        <div className="left-panel">
                            <EntityPanel
                                dxfInfo={dxfInfo}
                                parts={parts}
                                selectedParts={selectedParts}
                                onToggleSelection={handleTogglePartSelection}
                                onSelectAll={handleSelectAll}
                                onClearSelection={handleClearSelection}
                                onDeletePart={handleDeletePart}
                                onHoverPart={handleHoverPart}
                                onLeavePart={handleLeavePart}
                            />
                        </div>

                        <div className="center-panel">
                            {error && (
                                <div className="error-banner">
                                    {error}
                                </div>
                            )}

                            <div className="viewer-wrapper">
                                {isCompareMode ? (
                                    <div className="split-view">
                                        <div className="viewer-pane original">
                                            <div className="pane-label">編集前</div>
                                            <DxfViewer svg={originalSvg || svg} />
                                        </div>
                                        <div className="viewer-pane edited">
                                            <div className="pane-label">編集後</div>
                                            <DxfViewer
                                                svg={svg}
                                                highlightedHandles={highlightedHandles}
                                            />
                                        </div>
                                    </div>
                                ) : (
                                    <DxfViewer
                                        svg={svg}
                                        highlightedHandles={highlightedHandles}
                                    />
                                )}

                                {state === 'previewing' && (
                                    <div className="preview-overlay large">
                                        <div className="preview-actions large">
                                            <div className="preview-message">
                                                <div className="message-title">この操作を実行しますか？</div>
                                                {pendingCommand?.explanation && (
                                                    <div className="message-detail">
                                                        {pendingCommand.explanation}
                                                    </div>
                                                )}

                                                <div className="additional-instruction-section">
                                                    <label className="instruction-label">追加指示（オプション）</label>
                                                    <textarea
                                                        className="additional-instruction-input"
                                                        placeholder="例：赤色の要素は残してください..."
                                                        rows={3}
                                                    />
                                                </div>

                                                <span className="warning-text">※元に戻せません（Undo機能で戻せる場合があります）</span>
                                            </div>
                                            <div className="button-group">
                                                <button onClick={executeOperation} className="confirm-btn">実行</button>
                                                <button onClick={cancelOperation} className="cancel-btn">キャンセル</button>
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {state === 'loading' && (
                                    <div className="preview-overlay">
                                        <div className="loading-indicator">
                                            <div className="spinner"></div>
                                            <div className="loading-text">AIが考えています...</div>
                                        </div>
                                    </div>
                                )}
                            </div>

                            <div className="command-area">
                                <CommandInput
                                    onExecute={(text) => interpretCommand(text, selectedParts)}
                                    isLoading={state === 'loading' || state === 'executing'}
                                    disabled={state === 'previewing'}
                                    selectedParts={selectedParts}
                                />
                                <SuggestedCommands onSelect={(cmd) => {
                                    // CommandInputのinput要素を見つけて値を設定する簡易的な方法
                                    // 理想的にはCommandInputのrefを使うか、状態を持ち上げる
                                    const input = document.querySelector('.command-input input') as HTMLInputElement;
                                    if (input) {
                                        input.value = cmd;
                                        input.focus();
                                        // Reactの状態更新をトリガーするためにイベント発火
                                        const event = new Event('input', { bubbles: true });
                                        input.dispatchEvent(event);
                                    }
                                }} />
                            </div>
                        </div>
                    </div>
                )}
            </main>
        </div>
    );
}

export default App;
