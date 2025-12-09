"""
DXF Parser Service
Wrapper around ezdxf for parsing and analyzing DXF files.
"""
import ezdxf
from ezdxf.entities import DXFEntity
from typing import List, Dict, Any, Optional
from collections import defaultdict

# ACI (AutoCAD Color Index) to color name mapping
ACI_COLORS = {
    1: ("赤", "#FF0000"),
    2: ("黄", "#FFFF00"),
    3: ("緑", "#00FF00"),
    4: ("シアン", "#00FFFF"),
    5: ("青", "#0000FF"),
    6: ("マゼンタ", "#FF00FF"),
    7: ("白/黒", "#FFFFFF"),
    8: ("グレー", "#808080"),
    9: ("ライトグレー", "#C0C0C0"),
}


def get_color_name(aci: int) -> str:
    """ACI色番号から色名を取得"""
    if aci in ACI_COLORS:
        return ACI_COLORS[aci][0]
    return f"色{aci}"


def get_color_hex(aci: int) -> str:
    """ACI色番号からHEXカラーを取得"""
    if aci in ACI_COLORS:
        return ACI_COLORS[aci][1]
    # 基本色以外は近似色を計算
    if aci < 10:
        return "#808080"
    # 標準AutoCADカラーパレットの近似
    return f"#{(aci * 37) % 256:02x}{(aci * 73) % 256:02x}{(aci * 113) % 256:02x}"


class DxfParser:
    """DXFファイル解析クラス"""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.doc = ezdxf.readfile(file_path)
        self.msp = self.doc.modelspace()
        self._entity_cache: Optional[List[dict]] = None
    
    def get_info(self) -> Dict[str, Any]:
        """DXFファイルの概要情報を取得"""
        entities = list(self.msp)
        
        # レイヤー情報を収集
        layer_counts = defaultdict(int)
        for entity in entities:
            layer_counts[entity.dxf.layer] += 1
        
        layers = []
        for layer in self.doc.layers:
            color = layer.color if hasattr(layer, 'color') else 7
            layers.append({
                'name': layer.dxf.name,
                'color': color,
                'color_name': get_color_name(color),
                'entity_count': layer_counts.get(layer.dxf.name, 0)
            })
        
        # 使用色を収集
        color_counts = defaultdict(int)
        for entity in entities:
            color = self._get_entity_color(entity)
            color_counts[color] += 1
        
        colors_used = [
            {
                'aci': aci,
                'name': get_color_name(aci),
                'hex': get_color_hex(aci),
                'count': count
            }
            for aci, count in sorted(color_counts.items())
        ]
        
        return {
            'entity_count': len(entities),
            'layers': layers,
            'colors_used': colors_used
        }
    
    def get_entities(self, refresh: bool = False) -> List[dict]:
        """すべてのエンティティ情報を取得"""
        if self._entity_cache is not None and not refresh:
            return self._entity_cache
        
        entities = []
        for entity in self.msp:
            entity_info = self._parse_entity(entity)
            if entity_info:
                entities.append(entity_info)
        
        self._entity_cache = entities
        return entities
    
    def _get_entity_color(self, entity: DXFEntity) -> int:
        """エンティティの実際の色を取得（BYLAYER考慮）"""
        color = entity.dxf.color if hasattr(entity.dxf, 'color') else 256
        
        if color == 256:  # BYLAYER
            layer = self.doc.layers.get(entity.dxf.layer)
            if layer:
                return layer.color
            return 7
        elif color == 0:  # BYBLOCK
            return 7
        return color
    
    def _parse_entity(self, entity: DXFEntity) -> Optional[dict]:
        """エンティティを解析して辞書に変換"""
        entity_type = entity.dxftype()
        color = self._get_entity_color(entity)
        
        base_info = {
            'handle': entity.dxf.handle,
            'entity_type': entity_type,
            'layer': entity.dxf.layer,
            'color': color,
            'color_name': get_color_name(color),
            'color_hex': get_color_hex(color),
        }
        
        # エンティティタイプ別の追加情報
        if entity_type == 'LINE':
            base_info.update({
                'start': (entity.dxf.start.x, entity.dxf.start.y),
                'end': (entity.dxf.end.x, entity.dxf.end.y),
            })
        elif entity_type == 'CIRCLE':
            base_info.update({
                'center': (entity.dxf.center.x, entity.dxf.center.y),
                'radius': entity.dxf.radius,
            })
        elif entity_type == 'ARC':
            base_info.update({
                'center': (entity.dxf.center.x, entity.dxf.center.y),
                'radius': entity.dxf.radius,
                'start_angle': entity.dxf.start_angle,
                'end_angle': entity.dxf.end_angle,
            })
        elif entity_type in ('TEXT', 'MTEXT'):
            text = entity.dxf.text if entity_type == 'TEXT' else entity.text
            base_info.update({
                'text': text,
                'position': (
                    entity.dxf.insert.x if hasattr(entity.dxf, 'insert') else 0,
                    entity.dxf.insert.y if hasattr(entity.dxf, 'insert') else 0,
                ),
            })
        elif entity_type == 'INSERT':
            base_info.update({
                'block_name': entity.dxf.name,
                'position': (entity.dxf.insert.x, entity.dxf.insert.y),
            })
        elif entity_type == 'LWPOLYLINE':
            points = [(p[0], p[1]) for p in entity.get_points()]
            base_info.update({
                'points': points,
                'closed': entity.closed,
            })
        
        return base_info
    
    def get_entities_by_color(self, aci: int) -> List[dict]:
        """指定色のエンティティを取得"""
        return [e for e in self.get_entities() if e['color'] == aci]
    
    def get_entities_by_layer(self, layer_name: str) -> List[dict]:
        """指定レイヤーのエンティティを取得"""
        return [e for e in self.get_entities() if e['layer'] == layer_name]
    
    def get_text_entities(self) -> List[dict]:
        """テキストエンティティを取得"""
        return [e for e in self.get_entities() if e['entity_type'] in ('TEXT', 'MTEXT')]
    
    def find_entities_by_handle(self, handles: List[str]) -> List[DXFEntity]:
        """ハンドルからエンティティを検索"""
        handle_set = set(handles)
        return [e for e in self.msp if e.dxf.handle in handle_set]
