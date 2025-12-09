"""
DXF Operations Service
Handles all editing operations on DXF files.
All operations are deterministic - same input always produces same output.
"""
import re
from typing import List, Dict, Any
from ezdxf.document import Drawing
from services.dxf_parser import get_color_name


class DxfOperations:
    """DXFファイル編集操作クラス"""
    
    def __init__(self, doc: Drawing):
        self.doc = doc
        self.msp = doc.modelspace()
        self.operation_log: List[dict] = []
    
    def get_affected_entities(self, operation: str, params: dict) -> List[dict]:
        """操作によって影響を受けるエンティティを取得（プレビュー用）"""
        affected = []
        
        if operation == 'delete_by_color':
            color = params.get('color')
            if color is not None:
                for entity in self.msp:
                    entity_color = self._get_entity_color(entity)
                    if entity_color == color:
                        affected.append({
                            'handle': entity.dxf.handle,
                            'type': entity.dxftype(),
                            'layer': entity.dxf.layer,
                            'color': entity_color
                        })
        
        elif operation == 'delete_by_layer':
            layer = params.get('layer')
            if layer:
                for entity in self.msp:
                    if entity.dxf.layer == layer:
                        affected.append({
                            'handle': entity.dxf.handle,
                            'type': entity.dxftype(),
                            'layer': entity.dxf.layer,
                            'color': self._get_entity_color(entity)
                        })
        
        elif operation == 'delete_by_handles':
            handles = params.get('handles', [])
            handle_set = set(handles)
            for entity in self.msp:
                if entity.dxf.handle in handle_set:
                    affected.append({
                        'handle': entity.dxf.handle,
                        'type': entity.dxftype(),
                        'layer': entity.dxf.layer,
                        'color': self._get_entity_color(entity)
                    })
        
        elif operation == 'rename_text':
            pattern = params.get('pattern', '')
            for entity in self.msp:
                if entity.dxftype() == 'TEXT':
                    if re.search(pattern, entity.dxf.text):
                        affected.append({
                            'handle': entity.dxf.handle,
                            'type': 'TEXT',
                            'layer': entity.dxf.layer,
                            'color': self._get_entity_color(entity),
                            'text': entity.dxf.text
                        })
                elif entity.dxftype() == 'MTEXT':
                    if re.search(pattern, entity.text):
                        affected.append({
                            'handle': entity.dxf.handle,
                            'type': 'MTEXT',
                            'layer': entity.dxf.layer,
                            'color': self._get_entity_color(entity),
                            'text': entity.text
                        })
        
        elif operation == 'change_color':
            # 対象指定方法によって異なる
            target = params.get('target', {})
            if 'layer' in target:
                for entity in self.msp:
                    if entity.dxf.layer == target['layer']:
                        affected.append({
                            'handle': entity.dxf.handle,
                            'type': entity.dxftype(),
                            'layer': entity.dxf.layer,
                            'color': self._get_entity_color(entity)
                        })
            elif 'color' in target:
                for entity in self.msp:
                    if self._get_entity_color(entity) == target['color']:
                        affected.append({
                            'handle': entity.dxf.handle,
                            'type': entity.dxftype(),
                            'layer': entity.dxf.layer,
                            'color': self._get_entity_color(entity)
                        })
        
        return affected
    
    def execute(self, operation: str, params: dict) -> dict:
        """操作を実行"""
        result = {'affected_count': 0, 'message': ''}
        
        if operation == 'delete_by_color':
            result = self._delete_by_color(params)
        elif operation == 'delete_by_layer':
            result = self._delete_by_layer(params)
        elif operation == 'delete_by_handles':
            result = self._delete_by_handles(params)
        elif operation == 'rename_text':
            result = self._rename_text(params)
        elif operation == 'change_color':
            result = self._change_color(params)
        elif operation == 'change_layer':
            result = self._change_layer(params)
        else:
            raise ValueError(f"未知の操作: {operation}")
        
        # 操作ログに記録
        self.operation_log.append({
            'operation': operation,
            'params': params,
            'result': result
        })
        
        return result
    
    def _get_entity_color(self, entity) -> int:
        """エンティティの実際の色を取得"""
        color = entity.dxf.color if hasattr(entity.dxf, 'color') else 256
        
        if color == 256:  # BYLAYER
            layer = self.doc.layers.get(entity.dxf.layer)
            if layer:
                return layer.color
            return 7
        elif color == 0:  # BYBLOCK
            return 7
        return color
    
    def _delete_by_color(self, params: dict) -> dict:
        """指定色のエンティティを削除"""
        color = params.get('color')
        if color is None:
            raise ValueError("colorパラメータが必要です")
        
        to_delete = []
        for entity in self.msp:
            if self._get_entity_color(entity) == color:
                to_delete.append(entity)
        
        for entity in to_delete:
            self.msp.delete_entity(entity)
        
        color_name = get_color_name(color)
        return {
            'affected_count': len(to_delete),
            'message': f"{color_name}（ACI {color}）のエンティティを{len(to_delete)}個削除しました"
        }
    
    def _delete_by_layer(self, params: dict) -> dict:
        """指定レイヤーのエンティティを削除"""
        layer = params.get('layer')
        if not layer:
            raise ValueError("layerパラメータが必要です")
        
        to_delete = []
        for entity in self.msp:
            if entity.dxf.layer == layer:
                to_delete.append(entity)
        
        for entity in to_delete:
            self.msp.delete_entity(entity)
        
        return {
            'affected_count': len(to_delete),
            'message': f"レイヤー「{layer}」のエンティティを{len(to_delete)}個削除しました"
        }
    
    def _delete_by_handles(self, params: dict) -> dict:
        """指定ハンドルのエンティティを削除"""
        handles = params.get('handles', [])
        if not handles:
            raise ValueError("handlesパラメータが必要です")
        
        handle_set = set(handles)
        to_delete = []
        for entity in self.msp:
            if entity.dxf.handle in handle_set:
                to_delete.append(entity)
        
        for entity in to_delete:
            self.msp.delete_entity(entity)
        
        return {
            'affected_count': len(to_delete),
            'message': f"{len(to_delete)}個のエンティティを削除しました"
        }
    
    def _rename_text(self, params: dict) -> dict:
        """テキストを正規表現で置換"""
        pattern = params.get('pattern', '')
        replacement = params.get('replacement', '')
        
        if not pattern:
            raise ValueError("patternパラメータが必要です")
        
        count = 0
        regex = re.compile(pattern)
        
        for entity in self.msp:
            if entity.dxftype() == 'TEXT':
                new_text = regex.sub(replacement, entity.dxf.text)
                if new_text != entity.dxf.text:
                    entity.dxf.text = new_text
                    count += 1
            elif entity.dxftype() == 'MTEXT':
                new_text = regex.sub(replacement, entity.text)
                if new_text != entity.text:
                    entity.text = new_text
                    count += 1
        
        return {
            'affected_count': count,
            'message': f"{count}個のテキストを置換しました"
        }
    
    def _change_color(self, params: dict) -> dict:
        """エンティティの色を変更"""
        new_color = params.get('new_color')
        target = params.get('target', {})
        
        if new_color is None:
            raise ValueError("new_colorパラメータが必要です")
        
        count = 0
        for entity in self.msp:
            match = False
            if 'layer' in target and entity.dxf.layer == target['layer']:
                match = True
            elif 'color' in target and self._get_entity_color(entity) == target['color']:
                match = True
            elif 'handles' in target and entity.dxf.handle in target['handles']:
                match = True
            
            if match:
                entity.dxf.color = new_color
                count += 1
        
        return {
            'affected_count': count,
            'message': f"{count}個のエンティティの色を変更しました"
        }
    
    def _change_layer(self, params: dict) -> dict:
        """エンティティのレイヤーを変更"""
        new_layer = params.get('new_layer')
        target = params.get('target', {})
        
        if not new_layer:
            raise ValueError("new_layerパラメータが必要です")
        
        # レイヤーが存在しない場合は作成
        if new_layer not in self.doc.layers:
            self.doc.layers.add(new_layer)
        
        count = 0
        for entity in self.msp:
            match = False
            if 'layer' in target and entity.dxf.layer == target['layer']:
                match = True
            elif 'handles' in target and entity.dxf.handle in target['handles']:
                match = True
            
            if match:
                entity.dxf.layer = new_layer
                count += 1
        
        return {
            'affected_count': count,
            'message': f"{count}個のエンティティを「{new_layer}」レイヤーに移動しました"
        }
