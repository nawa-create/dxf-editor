"""
SVG Renderer Service
Converts DXF entities to SVG for browser display.
"""
import math
from typing import List, Optional, Tuple
from ezdxf.document import Drawing
from services.dxf_parser import get_color_hex


class SvgRenderer:
    """DXFからSVGへの変換クラス"""
    
    def __init__(self, doc: Drawing):
        self.doc = doc
        self.msp = doc.modelspace()
        self.min_x = float('inf')
        self.min_y = float('inf')
        self.max_x = float('-inf')
        self.max_y = float('-inf')
        self._calculate_bounds()
    
    def _calculate_bounds(self):
        """図面の境界を計算"""
        for entity in self.msp:
            bounds = self._get_entity_bounds(entity)
            if bounds:
                self.min_x = min(self.min_x, bounds[0])
                self.min_y = min(self.min_y, bounds[1])
                self.max_x = max(self.max_x, bounds[2])
                self.max_y = max(self.max_y, bounds[3])
        
        # 境界が見つからない場合のデフォルト
        if self.min_x == float('inf'):
            self.min_x, self.min_y = 0, 0
            self.max_x, self.max_y = 1000, 1000
    
    def _get_entity_bounds(self, entity) -> Optional[Tuple[float, float, float, float]]:
        """エンティティの境界ボックスを取得"""
        entity_type = entity.dxftype()
        
        try:
            if entity_type == 'LINE':
                x1, y1 = entity.dxf.start.x, entity.dxf.start.y
                x2, y2 = entity.dxf.end.x, entity.dxf.end.y
                return (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
            
            elif entity_type == 'CIRCLE':
                cx, cy = entity.dxf.center.x, entity.dxf.center.y
                r = entity.dxf.radius
                return (cx - r, cy - r, cx + r, cy + r)
            
            elif entity_type == 'ARC':
                cx, cy = entity.dxf.center.x, entity.dxf.center.y
                r = entity.dxf.radius
                return (cx - r, cy - r, cx + r, cy + r)
            
            elif entity_type in ('TEXT', 'MTEXT'):
                if hasattr(entity.dxf, 'insert'):
                    x, y = entity.dxf.insert.x, entity.dxf.insert.y
                    return (x, y, x + 100, y + 20)  # テキストの近似境界
            
            elif entity_type == 'LWPOLYLINE':
                points = list(entity.get_points())
                if points:
                    xs = [p[0] for p in points]
                    ys = [p[1] for p in points]
                    return (min(xs), min(ys), max(xs), max(ys))
            
            elif entity_type == 'INSERT':
                x, y = entity.dxf.insert.x, entity.dxf.insert.y
                return (x, y, x + 50, y + 50)  # ブロックの近似境界
        except:
            pass
        
        return None
    
    def _get_entity_color(self, entity) -> str:
        """エンティティの色をHEXで取得"""
        color = entity.dxf.color if hasattr(entity.dxf, 'color') else 256
        
        if color == 256:  # BYLAYER
            layer = self.doc.layers.get(entity.dxf.layer)
            if layer:
                return get_color_hex(layer.color)
            return "#FFFFFF"
        elif color == 0:  # BYBLOCK
            return "#FFFFFF"
        return get_color_hex(color)
    
    def render(self, 
               highlight_handles: Optional[List[str]] = None,
               highlight_color: str = "#ff0000",
               width: int = 800,
               height: int = 600) -> str:
        """SVGを生成"""
        highlight_set = set(highlight_handles or [])
        
        # ビューボックス計算（マージン追加）
        margin = 0.1
        dx = self.max_x - self.min_x
        dy = self.max_y - self.min_y
        
        if dx == 0:
            dx = 1
        if dy == 0:
            dy = 1
            
        vb_x = self.min_x - dx * margin
        vb_y = self.min_y - dy * margin
        vb_w = dx * (1 + 2 * margin)
        vb_h = dy * (1 + 2 * margin)
        
        # Y軸反転のためのスケーリング
        svg_parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" ',
            f'width="{width}" height="{height}" ',
            f'viewBox="{vb_x} {-vb_y - vb_h} {vb_w} {vb_h}" ',
            f'style="background-color: #1a1a2e;">',
            '<g transform="scale(1, -1)">'
        ]
        
        # エンティティを描画
        for entity in self.msp:
            handle = entity.dxf.handle
            is_highlighted = handle in highlight_set
            svg_element = self._render_entity(entity, is_highlighted, highlight_color)
            if svg_element:
                svg_parts.append(svg_element)
        
        svg_parts.append('</g></svg>')
        
        return '\n'.join(svg_parts)
    
    def _render_entity(self, entity, highlighted: bool, highlight_color: str) -> Optional[str]:
        """エンティティをSVG要素に変換"""
        entity_type = entity.dxftype()
        color = highlight_color if highlighted else self._get_entity_color(entity)
        stroke_width = 3 if highlighted else 1
        handle = entity.dxf.handle
        
        try:
            if entity_type == 'LINE':
                x1, y1 = entity.dxf.start.x, entity.dxf.start.y
                x2, y2 = entity.dxf.end.x, entity.dxf.end.y
                return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{stroke_width}" data-handle="{handle}"/>'
            
            elif entity_type == 'CIRCLE':
                cx, cy = entity.dxf.center.x, entity.dxf.center.y
                r = entity.dxf.radius
                return f'<circle cx="{cx}" cy="{cy}" r="{r}" stroke="{color}" fill="none" stroke-width="{stroke_width}" data-handle="{handle}"/>'
            
            elif entity_type == 'ARC':
                cx, cy = entity.dxf.center.x, entity.dxf.center.y
                r = entity.dxf.radius
                start_angle = math.radians(entity.dxf.start_angle)
                end_angle = math.radians(entity.dxf.end_angle)
                
                x1 = cx + r * math.cos(start_angle)
                y1 = cy + r * math.sin(start_angle)
                x2 = cx + r * math.cos(end_angle)
                y2 = cy + r * math.sin(end_angle)
                
                # 大きい弧かどうか判定
                angle_diff = end_angle - start_angle
                if angle_diff < 0:
                    angle_diff += 2 * math.pi
                large_arc = 1 if angle_diff > math.pi else 0
                
                return f'<path d="M {x1} {y1} A {r} {r} 0 {large_arc} 1 {x2} {y2}" stroke="{color}" fill="none" stroke-width="{stroke_width}" data-handle="{handle}"/>'
            
            elif entity_type == 'LWPOLYLINE':
                points = list(entity.get_points())
                if not points:
                    return None
                
                d = f"M {points[0][0]} {points[0][1]}"
                for p in points[1:]:
                    d += f" L {p[0]} {p[1]}"
                if entity.closed:
                    d += " Z"
                
                return f'<path d="{d}" stroke="{color}" fill="none" stroke-width="{stroke_width}" data-handle="{handle}"/>'
            
            elif entity_type in ('TEXT', 'MTEXT'):
                if not hasattr(entity.dxf, 'insert'):
                    return None
                x, y = entity.dxf.insert.x, entity.dxf.insert.y
                text = entity.dxf.text if entity_type == 'TEXT' else entity.text
                # テキストはY軸反転を考慮
                return f'<text x="{x}" y="{y}" fill="{color}" font-size="10" transform="scale(1, -1) translate(0, {-2*y})" data-handle="{handle}">{text}</text>'
        
        except Exception as e:
            pass
        
        return None
