import { useState, useEffect } from 'react';
import { api } from '../services/api';
import './SuggestedCommands.css';

interface SuggestedCommandsProps {
    onSelect: (command: string) => void;
}

interface Rule {
    pattern: string;
    description: string;
}

export function SuggestedCommands({ onSelect }: SuggestedCommandsProps) {
    const [rules, setRules] = useState<Rule[]>([]);

    useEffect(() => {
        const fetchRules = async () => {
            try {
                const response = await api.getRules();
                setRules(response.rules);
            } catch (error) {
                console.error('Failed to load rules:', error);
            }
        };
        fetchRules();
    }, []);

    // 組み込みの推奨コマンド例
    const defaultExamples = [
        { pattern: 'DF-01を削除', description: '部材 "DF-01" を削除' },
        { pattern: '右上の部品を消して', description: '配置から推論して削除 (AI)' },
    ];

    const allCommands = [
        ...rules.map(r => ({ ...r, type: 'rule' })),
        ...defaultExamples.map(e => ({ ...e, type: 'example' }))
    ];

    return (
        <div className="suggested-commands">
            <div className="suggestions-header">
                <span>登録済みルール & 例</span>
            </div>
            <div className="suggestions-list">
                {allCommands.map((cmd, index) => (
                    <button
                        key={index}
                        className={`suggestion-chip ${cmd.type === 'rule' ? 'rule' : 'ai'}`}
                        onClick={() => onSelect(cmd.pattern)}
                        title={cmd.description}
                    >
                        {cmd.description || cmd.pattern}
                    </button>
                ))}
            </div>
        </div>
    );
}
