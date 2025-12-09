import { useState, useCallback, KeyboardEvent } from 'react';
import './CommandInput.css';

interface CommandInputProps {
    onExecute: (text: string) => void;
    isLoading: boolean;
    disabled?: boolean;
    selectedParts?: string[];
}

const SUGGESTIONS = [
    '黄色い線を消して',
    '枠線レイヤーを削除',
    '部材名に510-を追加',
    'すべてのテキストを赤色に変更',
    'レイヤー「寸法」を削除',
];

export function CommandInput({ onExecute, isLoading, disabled, selectedParts = [] }: CommandInputProps) {
    const [text, setText] = useState('');

    const handleSubmit = useCallback(() => {
        if (text.trim() && !isLoading && !disabled) {
            onExecute(text);
            setText('');
        }
    }, [text, isLoading, disabled, onExecute]);

    const handleKeyDown = useCallback((e: KeyboardEvent<HTMLInputElement>) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit();
        }
    }, [handleSubmit]);

    return (
        <div className="command-input-container">
            {selectedParts.length > 0 && (
                <div className="selected-parts-info">
                    <span className="selected-label">選択中:</span>
                    <div className="selected-chips">
                        {selectedParts.map(part => (
                            <span key={part} className="selected-chip">{part}</span>
                        ))}
                    </div>
                </div>
            )}
            <div className="input-wrapper">
                <input
                    type="text"
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="自然言語で指示を入力してください（例: 黄色い線を消して）"
                    disabled={isLoading || disabled}
                    className="command-input"
                />
                <button
                    onClick={handleSubmit}
                    disabled={!text.trim() || isLoading || disabled}
                    className="send-button"
                >
                    {isLoading ? '...' : '実行'}
                </button>
            </div>

            <div className="suggestions">
                {SUGGESTIONS.map((suggestion) => (
                    <button
                        key={suggestion}
                        onClick={() => setText(suggestion)}
                        disabled={isLoading || disabled}
                        className="suggestion-chip"
                    >
                        {suggestion}
                    </button>
                ))}
            </div>
        </div>
    );
}
