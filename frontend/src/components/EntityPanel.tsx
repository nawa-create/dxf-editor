import type { DxfInfo, PartInfo } from '../types';
import './EntityPanel.css';

interface EntityPanelProps {
    dxfInfo: DxfInfo | null;
    parts?: PartInfo[];
    selectedParts?: string[];
    onToggleSelection?: (partName: string) => void;
    onSelectAll?: () => void;
    onClearSelection?: () => void;
    onDeletePart?: (partName: string) => void;
    onHoverPart?: (partName: string) => void;
    onLeavePart?: () => void;
}

export function EntityPanel({
    dxfInfo,
    parts = [],
    selectedParts = [],
    onToggleSelection,
    onSelectAll,
    onClearSelection,
    onDeletePart,
    onHoverPart,
    onLeavePart
}: EntityPanelProps) {
    if (!dxfInfo) {
        return (
            <div className="entity-panel empty">
                <p>ファイルが読み込まれていません</p>
            </div>
        );
    }

    return (
        <div className="entity-panel">
            <div className="panel-section">
                <h3>ファイル情報</h3>
                <div className="info-grid">
                    <div className="label">ファイル名</div>
                    <div className="value">{dxfInfo.filename}</div>
                    <div className="label">総エンティティ数</div>
                    <div className="value">{dxfInfo.entity_count.toLocaleString()}</div>
                    <div className="label">検出部材数</div>
                    <div className="value">{parts.length}</div>
                </div>
            </div>

            {parts.length > 0 && (
                <div className="panel-section">
                    <div className="parts-header">
                        <h3>検出された部材 ({parts.length})</h3>
                        <div className="selection-controls">
                            <span className="selection-count">
                                選択中: {selectedParts.length}件
                            </span>
                            <button
                                className="selection-btn"
                                onClick={onSelectAll}
                                title="すべて選択"
                            >
                                すべて
                            </button>
                            <button
                                className="selection-btn"
                                onClick={onClearSelection}
                                title="選択解除"
                            >
                                解除
                            </button>
                        </div>
                    </div>
                    <div className="parts-list">
                        {parts.map((part) => {
                            const isSelected = selectedParts.includes(part.part_name);
                            return (
                                <div
                                    key={part.text_handle}
                                    className={`part-item ${isSelected ? 'selected' : ''}`}
                                    onMouseEnter={() => onHoverPart && onHoverPart(part.part_name)}
                                    onMouseLeave={() => onLeavePart && onLeavePart()}
                                >
                                    <input
                                        type="checkbox"
                                        className="part-checkbox"
                                        checked={isSelected}
                                        onChange={() => onToggleSelection && onToggleSelection(part.part_name)}
                                        onClick={(e) => e.stopPropagation()}
                                    />
                                    <div className="part-info">
                                        <span className="part-name">{part.part_name}</span>
                                        <div className="part-meta">
                                            <span className="badge linked">
                                                紐づけ: {part.linked_count}
                                            </span>
                                            <span className="badge confidence">
                                                {(part.confidence * 100).toFixed(0)}% Match
                                            </span>
                                        </div>
                                    </div>
                                    {onDeletePart && (
                                        <button
                                            className="part-delete-btn"
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                onDeletePart(part.part_name);
                                            }}
                                            title="この部材を削除"
                                        >
                                            ×
                                        </button>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

            <div className="panel-section">
                <h3>レイヤー情報 ({dxfInfo.layers ? dxfInfo.layers.length : 0})</h3>
                <div className="layer-list">
                    {dxfInfo.layers && dxfInfo.layers.map((layer) => (
                        <div key={layer.name} className="layer-item">
                            <span
                                className="color-indicator"
                                style={{ backgroundColor: layer.color === 7 ? '#fff' : getColorHex(layer.color) }}
                            />
                            <span className="layer-name">{layer.name}</span>
                            <span className="entity-count">{layer.entity_count}</span>
                        </div>
                    ))}
                </div>
            </div>

            <div className="panel-section">
                <h3>使用色 ({dxfInfo.colors_used ? dxfInfo.colors_used.length : 0})</h3>
                <div className="color-list">
                    {dxfInfo.colors_used && dxfInfo.colors_used.map((color) => (
                        <div key={color.aci} className="color-item">
                            <span
                                className="color-indicator"
                                style={{ backgroundColor: color.hex }}
                            />
                            <span className="color-name">{color.name} (ACI:{color.aci})</span>
                            <span className="entity-count">{color.count}</span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}

// 簡易的な色変換（APIからhexが来るが、念のため）
function getColorHex(aci: number): string {
    // 基本色のみマッピング
    const colors: Record<number, string> = {
        1: '#FF0000', 2: '#FFFF00', 3: '#00FF00', 4: '#00FFFF',
        5: '#0000FF', 6: '#FF00FF', 7: '#FFFFFF', 8: '#808080', 9: '#C0C0C0'
    };
    return colors[aci] || '#808080';
}
