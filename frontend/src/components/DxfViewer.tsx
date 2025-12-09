/**
 * DXF Viewer Component
 * Displays DXF file as interactive SVG
 */
import { useRef, useEffect, useState, useCallback } from 'react';
import './DxfViewer.css';

interface DxfViewerProps {
    svg: string;
    onEntityClick?: (handle: string) => void;
    highlightedHandles?: string[];
}

export function DxfViewer({ svg, onEntityClick, highlightedHandles = [] }: DxfViewerProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const [scale, setScale] = useState(1);
    const [position, setPosition] = useState({ x: 0, y: 0 });
    const [isDragging, setIsDragging] = useState(false);
    const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

    // ハイライト更新
    useEffect(() => {
        if (!containerRef.current) return;

        // 全てのハイライトをリセット
        const highlighted = containerRef.current.querySelectorAll('.highlighted-entity');
        highlighted.forEach(el => {
            el.classList.remove('highlighted-entity');
            // 元のスタイルに戻す（SVGの特性上、classで制御するのが望ましい）
        });

        if (highlightedHandles.length === 0) return;

        // 指定ハンドルをハイライト
        highlightedHandles.forEach(handle => {
            // data-handle属性を持つ要素を検索
            const el = containerRef.current?.querySelector(`[data-handle="${handle}"]`);
            if (el) {
                el.classList.add('highlighted-entity');
            }
        });
    }, [highlightedHandles, svg]); // svgが変わったときも再適用

    // ホイールでズーム
    const handleWheel = useCallback((e: WheelEvent) => {
        e.preventDefault();
        const delta = e.deltaY > 0 ? 0.9 : 1.1;
        setScale(prev => Math.min(Math.max(prev * delta, 0.01), 500));
    }, []);

    // ドラッグ開始
    const handleMouseDown = useCallback((e: React.MouseEvent) => {
        if (e.button !== 0) return; // 左クリックのみ
        setIsDragging(true);
        setDragStart({ x: e.clientX - position.x, y: e.clientY - position.y });
    }, [position]);

    // ドラッグ中
    const handleMouseMove = useCallback((e: React.MouseEvent) => {
        if (!isDragging) return;
        setPosition({
            x: e.clientX - dragStart.x,
            y: e.clientY - dragStart.y,
        });
    }, [isDragging, dragStart]);

    // ドラッグ終了
    const handleMouseUp = useCallback(() => {
        setIsDragging(false);
    }, []);

    // エンティティクリック
    const handleClick = useCallback((e: React.MouseEvent) => {
        const target = e.target as SVGElement;
        const handle = target.dataset?.handle;
        if (handle && onEntityClick) {
            onEntityClick(handle);
        }
    }, [onEntityClick]);

    // ホイールイベントリスナー
    useEffect(() => {
        const container = containerRef.current;
        if (container) {
            container.addEventListener('wheel', handleWheel, { passive: false });
            return () => container.removeEventListener('wheel', handleWheel);
        }
    }, [handleWheel]);

    // リセット
    const handleReset = useCallback(() => {
        setScale(1);
        setPosition({ x: 0, y: 0 });
    }, []);

    return (
        <div className="dxf-viewer">
            <div className="dxf-viewer-toolbar">
                <button onClick={() => setScale(s => Math.min(s * 1.2, 500))} title="ズームイン">
                    🔍+
                </button>
                <button onClick={() => setScale(s => Math.max(s * 0.8, 0.01))} title="ズームアウト">
                    🔍−
                </button>
                <button onClick={handleReset} title="リセット">
                    ↺
                </button>
                <span className="zoom-level">{Math.round(scale * 100)}%</span>
            </div>

            <div
                ref={containerRef}
                className={`dxf-viewer-container ${isDragging ? 'dragging' : ''}`}
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseUp}
                onClick={handleClick}
            >
                <div
                    className="dxf-viewer-content"
                    style={{
                        transform: `translate(${position.x}px, ${position.y}px) scale(${scale})`,
                    }}
                    dangerouslySetInnerHTML={{ __html: svg }}
                />
            </div>
        </div>
    );
}
