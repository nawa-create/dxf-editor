"""
Entity Linker Service
Links text entities (part names) to geometric entities based on spatial proximity.
Optimized with Spatial Hashing.
"""
import re
import math
from typing import List, Dict, Any, Tuple, Optional, Set
from collections import defaultdict
from ezdxf.document import Drawing
from ezdxf.math import BoundingBox2d, Vec3
from ezdxf.entities import DXFEntity

# 部材名の正規表現パターン
PART_NAME_PATTERNS = [
    r'DF-\d+',       # 例: DF-01
    r'D\d+番',       # 例: D1890番
    r'\d+-\d+',      # 例: 510-1
    r'[A-Z0-9]+-[A-Z0-9]+' # 汎用的な記号-番号パターン
]

# 部材が配置されるレイヤー名（優先度順）
PART_LAYERS = ['板情報']

# 矩形検出の設定
MIN_BOUNDARY_LINE_LENGTH = 150.0  # 境界線とみなす最小長さ
ENDPOINT_TOLERANCE = 5.0  # 端点の一致判定の許容誤差

class SpatialIndex:
    """
    簡易的な空間ハッシュインデックス
    2D空間をグリッドに分割し、高速な近傍探索を実現する
    """
    def __init__(self, cell_size: float = 100.0):
        self.cell_size = cell_size
        self.grid: Dict[Tuple[int, int], List[DXFEntity]] = defaultdict(list)
        self.entity_bboxes: Dict[str, BoundingBox2d] = {}

    def _get_cell_coords(self, x: float, y: float) -> Tuple[int, int]:
        return (int(x // self.cell_size), int(y // self.cell_size))

    def _get_cells_for_bbox(self, bbox: BoundingBox2d) -> List[Tuple[int, int]]:
        min_cell = self._get_cell_coords(bbox.extmin.x, bbox.extmin.y)
        max_cell = self._get_cell_coords(bbox.extmax.x, bbox.extmax.y)
        
        cells = []
        for x in range(min_cell[0], max_cell[0] + 1):
            for y in range(min_cell[1], max_cell[1] + 1):
                cells.append((x, y))
        return cells

    def insert(self, entity: DXFEntity, bbox: BoundingBox2d):
        """エンティティをインデックスに追加"""
        self.entity_bboxes[entity.dxf.handle] = bbox
        for cell in self._get_cells_for_bbox(bbox):
            self.grid[cell].append(entity)

    def query_radius(self, center: Tuple[float, float], radius: float) -> List[DXFEntity]:
        """中心点から半径radius以内のエンティティ候補を取得（粗い判定）"""
        cx, cy = center
        search_bbox = BoundingBox2d([
            (cx - radius, cy - radius),
            (cx + radius, cy + radius)
        ])
        
        cells = self._get_cells_for_bbox(search_bbox)
        seen_handles = set()
        candidates = []
        
        for cell in cells:
            for entity in self.grid[cell]:
                if entity.dxf.handle in seen_handles:
                    continue
                seen_handles.add(entity.dxf.handle)
                candidates.append(entity)
                
        return candidates

class EntityLinker:
    """部材紐づけクラス"""
    
    def __init__(self, doc: Drawing):
        self.doc = doc
        self.msp = doc.modelspace()
        self.parts: List[Dict[str, Any]] = []
        self.spatial_index = SpatialIndex(cell_size=500.0)
        self.drawing_bounds: Optional[BoundingBox2d] = None
    
    def link_entities(self) -> List[Dict[str, Any]]:
        """
        部材紐づけを実行（レイヤー＋矩形ベースアプローチ）
        
        戦略:
        1. 対象レイヤー（板情報など）を特定
        2. 独立したLINEから矩形境界を検出
        3. 各部材名テキストに最も近い矩形を割り当て
        4. その矩形内のエンティティを部材に紐づける
        5. 矩形がない場合は従来のフォールバック
        """
        # 0. 図面境界を計算
        self.drawing_bounds = self._calculate_drawing_bounds()
        
        # 1. 空間インデックス構築
        self._build_index()
        
        # 2. 対象レイヤーを決定
        target_layer = self._detect_part_layer()
        print(f"=== Layer + Rectangle-Based Matching ===")
        print(f"Target layer: {target_layer}")
        
        # 3. 部材名テキストを検出（レイヤーフィルタ付き）
        part_texts = self._find_part_texts(target_layer=target_layer)
        print(f"Detected {len(part_texts)} part texts")
        
        # 4. 矩形境界を検出
        rectangles = self._find_rectangles_from_lines(target_layer=target_layer)
        
        # 5. 従来の閉じたポリラインも収集（フォールバック用）
        closed_polylines = self._find_closed_polylines()
        print(f"Detected {len(closed_polylines)} closed polylines (fallback)")
        
        # 結果格納用
        text_to_entities = defaultdict(list)
        entity_assignment: Dict[str, Tuple[str, float]] = {}
        used_rectangles: Set[int] = set()  # 使用済み矩形のインデックス
        used_boundaries: Set[str] = set()  # 使用済みポリライン

        for text_entity in part_texts:
            text_handle = text_entity.dxf.handle
            text_center = self._get_entity_center(text_entity)
            if not text_center:
                continue
            
            # 戦略1: テキストを含む矩形を探す
            best_rect = None
            best_rect_idx = None
            
            for idx, rect in enumerate(rectangles):
                if idx in used_rectangles:
                    continue
                if self._point_in_rectangle(text_center, rect['bbox']):
                    best_rect = rect
                    best_rect_idx = idx
                    break
            
            # 戦略2: 最も近い矩形を探す
            if not best_rect:
                min_distance = float('inf')
                for idx, rect in enumerate(rectangles):
                    if idx in used_rectangles:
                        continue
                    dist = math.sqrt((text_center[0] - rect['center'][0])**2 + 
                                   (text_center[1] - rect['center'][1])**2)
                    if dist < min_distance and dist < 300:  # 近接閾値
                        min_distance = dist
                        best_rect = rect
                        best_rect_idx = idx
            
            if best_rect:
                used_rectangles.add(best_rect_idx)
                matched = self._collect_entities_in_rectangle(
                    best_rect['bbox'], text_handle, entity_assignment, target_layer
                )
                print(f"Part '{self._get_text_content(text_entity)}': matched {matched} entities using rectangle")
                continue
            
            # 戦略3: 従来のポリラインベース（フォールバック）
            best_boundary = None
            best_boundary_handle = None
            min_distance = float('inf')
            
            for pline in closed_polylines:
                if pline.dxf.handle in used_boundaries:
                    continue
                    
                if self._point_in_polyline(text_center, pline):
                    best_boundary = pline
                    best_boundary_handle = pline.dxf.handle
                    break
                
                pline_center = self._get_polyline_center(pline)
                if pline_center:
                    dist = math.sqrt((text_center[0] - pline_center[0])**2 + 
                                   (text_center[1] - pline_center[1])**2)
                    if dist < min_distance and dist < 500:
                        min_distance = dist
                        best_boundary = pline
                        best_boundary_handle = pline.dxf.handle
            
            if best_boundary:
                used_boundaries.add(best_boundary_handle)
                matched = self._collect_entities_in_boundary(best_boundary, text_handle, entity_assignment)
                print(f"Part '{self._get_text_content(text_entity)}': matched {matched} entities using polyline")
            else:
                # 戦略4: 距離ベースのフォールバック
                matched = self._fallback_proximity_match(text_entity, text_handle, entity_assignment)
                print(f"Part '{self._get_text_content(text_entity)}': matched {matched} entities using fallback")

        total_matched = len(entity_assignment)
        print(f"Total matched entities: {total_matched}")

        # 結果をまとめる
        text_to_entity_scores: Dict[str, List[float]] = defaultdict(list)
        for entity_handle, (text_handle, score) in entity_assignment.items():
            text_to_entities[text_handle].append(entity_handle)
            text_to_entity_scores[text_handle].append(score)

        results = []
        for text_entity in part_texts:
            text_handle = text_entity.dxf.handle
            linked_handles = text_to_entities.get(text_handle, [])
            scores = text_to_entity_scores.get(text_handle, [])
            
            results.append({
                'part_name': self._get_text_content(text_entity),
                'text_handle': text_handle,
                'position': self._get_entity_center(text_entity),
                'center': self._get_entity_center(text_entity),
                'linked_handles': linked_handles,
                'confidence': self._calculate_confidence(len(linked_handles), scores)
            })
        
        self.parts = results
        return results

    def _detect_part_layer(self) -> Optional[str]:
        """部材が配置されているレイヤーを検出する"""
        # 設定されたレイヤーが存在するか確認
        layer_names = [layer.dxf.name for layer in self.doc.layers]
        for target in PART_LAYERS:
            if target in layer_names:
                # そのレイヤーにエンティティがあるか確認
                count = sum(1 for e in self.msp if e.dxf.layer == target)
                if count > 0:
                    print(f"Found target layer '{target}' with {count} entities")
                    return target
        return None
    
    def _get_text_content(self, entity) -> str:
        if entity.dxftype() == 'TEXT':
            return entity.dxf.text
        elif entity.dxftype() == 'MTEXT':
            return entity.text
        return ""

    def _get_text_height(self, entity) -> float:
        """テキストの高さを取得（探索半径の計算用）"""
        try:
            if entity.dxftype() == 'TEXT':
                return entity.dxf.height
            elif entity.dxftype() == 'MTEXT':
                return entity.dxf.char_height
        except:
            pass
        return 100.0  # デフォルト高さ

    def _find_closed_polylines(self) -> List[Any]:
        """閉じたLWPOLYLINE（外形線候補）を収集"""
        closed_plines = []
        for entity in self.msp:
            if entity.dxftype() == 'LWPOLYLINE':
                # 閉じているかチェック
                if entity.closed or entity.dxf.flags & 1:  # 1 = closed flag
                    closed_plines.append(entity)
        return closed_plines

    def _find_rectangles_from_lines(self, target_layer: str = None) -> List[Dict[str, Any]]:
        """
        独立したLINEエンティティから矩形を検出する
        
        Args:
            target_layer: 対象レイヤー名（Noneの場合は全レイヤー）
        
        Returns:
            検出された矩形のリスト。各矩形は以下の情報を持つ:
            - bbox: (min_x, min_y, max_x, max_y)
            - center: (cx, cy)
            - lines: 構成するLINEエンティティのリスト
        """
        # 1. 対象レイヤーから長いLINEを抽出
        h_lines = []  # 水平線
        v_lines = []  # 垂直線
        
        for entity in self.msp:
            if entity.dxftype() != 'LINE':
                continue
            if target_layer and entity.dxf.layer != target_layer:
                continue
            
            sx, sy = entity.dxf.start.x, entity.dxf.start.y
            ex, ey = entity.dxf.end.x, entity.dxf.end.y
            length = math.sqrt((ex - sx)**2 + (ey - sy)**2)
            
            if length < MIN_BOUNDARY_LINE_LENGTH:
                continue
            
            is_horizontal = abs(ey - sy) < ENDPOINT_TOLERANCE
            is_vertical = abs(ex - sx) < ENDPOINT_TOLERANCE
            
            if is_horizontal:
                # 水平線: X座標でソート
                x_min, x_max = min(sx, ex), max(sx, ex)
                h_lines.append({
                    'entity': entity,
                    'y': (sy + ey) / 2,
                    'x_min': x_min,
                    'x_max': x_max,
                    'length': length
                })
            elif is_vertical:
                # 垂直線: Y座標でソート
                y_min, y_max = min(sy, ey), max(sy, ey)
                v_lines.append({
                    'entity': entity,
                    'x': (sx + ex) / 2,
                    'y_min': y_min,
                    'y_max': y_max,
                    'length': length
                })
        
        print(f"[Rectangle Detection] Found {len(h_lines)} horizontal, {len(v_lines)} vertical lines")
        
        # 2. 矩形を検出
        rectangles = []
        used_lines = set()
        
        # 水平線をY座標でグループ化
        h_by_y = defaultdict(list)
        for h in h_lines:
            y_key = round(h['y'] / ENDPOINT_TOLERANCE) * ENDPOINT_TOLERANCE
            h_by_y[y_key].append(h)
        
        # 垂直線をX座標でグループ化
        v_by_x = defaultdict(list)
        for v in v_lines:
            x_key = round(v['x'] / ENDPOINT_TOLERANCE) * ENDPOINT_TOLERANCE
            v_by_x[x_key].append(v)
        
        # 矩形を構成する線を探す
        for y_top, top_lines in sorted(h_by_y.items(), reverse=True):
            for y_bottom, bottom_lines in sorted(h_by_y.items()):
                if y_bottom >= y_top - ENDPOINT_TOLERANCE:
                    continue
                
                for top_line in top_lines:
                    for bottom_line in bottom_lines:
                        # X範囲が重なっているか確認
                        x_min = max(top_line['x_min'], bottom_line['x_min'])
                        x_max = min(top_line['x_max'], bottom_line['x_max'])
                        
                        if x_max - x_min < MIN_BOUNDARY_LINE_LENGTH * 0.5:
                            continue
                        
                        # 対応する垂直線を探す
                        left_v = None
                        right_v = None
                        
                        for x_key, v_list in v_by_x.items():
                            for v in v_list:
                                # 左辺候補
                                if abs(v['x'] - x_min) < ENDPOINT_TOLERANCE * 2:
                                    if v['y_min'] <= y_bottom + ENDPOINT_TOLERANCE and v['y_max'] >= y_top - ENDPOINT_TOLERANCE:
                                        left_v = v
                                # 右辺候補
                                if abs(v['x'] - x_max) < ENDPOINT_TOLERANCE * 2:
                                    if v['y_min'] <= y_bottom + ENDPOINT_TOLERANCE and v['y_max'] >= y_top - ENDPOINT_TOLERANCE:
                                        right_v = v
                        
                        if left_v and right_v:
                            # 矩形を構成
                            line_ids = frozenset([
                                top_line['entity'].dxf.handle,
                                bottom_line['entity'].dxf.handle,
                                left_v['entity'].dxf.handle,
                                right_v['entity'].dxf.handle
                            ])
                            
                            if line_ids in used_lines:
                                continue
                            used_lines.add(line_ids)
                            
                            rect = {
                                'bbox': (x_min, y_bottom, x_max, y_top),
                                'center': ((x_min + x_max) / 2, (y_bottom + y_top) / 2),
                                'width': x_max - x_min,
                                'height': y_top - y_bottom,
                                'lines': [
                                    top_line['entity'],
                                    bottom_line['entity'],
                                    left_v['entity'],
                                    right_v['entity']
                                ]
                            }
                            rectangles.append(rect)
        
        print(f"[Rectangle Detection] Found {len(rectangles)} rectangles")
        return rectangles

    def _point_in_rectangle(self, point: Tuple[float, float], 
                            bbox: Tuple[float, float, float, float]) -> bool:
        """点が矩形内にあるかを判定"""
        x, y = point
        min_x, min_y, max_x, max_y = bbox
        return min_x <= x <= max_x and min_y <= y <= max_y

    def _collect_entities_in_rectangle(self, bbox: Tuple[float, float, float, float],
                                       text_handle: str,
                                       entity_assignment: Dict[str, Tuple[str, float]],
                                       target_layer: str = None) -> int:
        """矩形内のエンティティを収集してtext_handleに割り当て"""
        min_x, min_y, max_x, max_y = bbox
        matched = 0
        
        for entity in self.msp:
            if entity.dxf.handle == text_handle:
                continue
            if entity.dxf.handle in entity_assignment:
                continue
            if target_layer and entity.dxf.layer != target_layer:
                continue
            if entity.dxftype() in ('TEXT', 'MTEXT'):
                continue  # テキストは除外（部材名以外のテキスト）
            
            center = self._get_entity_center(entity)
            if not center:
                continue
            
            if self._point_in_rectangle(center, bbox):
                entity_assignment[entity.dxf.handle] = (text_handle, 0.95)
                matched += 1
        
        return matched

    def _point_in_polyline(self, point: Tuple[float, float], pline) -> bool:
        """点がポリライン内にあるかを判定（Ray casting algorithm）"""
        try:
            vertices = list(pline.get_points(format='xy'))
            if len(vertices) < 3:
                return False
            
            x, y = point
            n = len(vertices)
            inside = False
            
            j = n - 1
            for i in range(n):
                xi, yi = vertices[i]
                xj, yj = vertices[j]
                
                if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                    inside = not inside
                j = i
            
            return inside
        except:
            return False

    def _get_polyline_center(self, pline) -> Optional[Tuple[float, float]]:
        """ポリラインの中心座標を取得"""
        try:
            vertices = list(pline.get_points(format='xy'))
            if not vertices:
                return None
            xs = [v[0] for v in vertices]
            ys = [v[1] for v in vertices]
            return ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
        except:
            return None

    def _get_polyline_bbox(self, pline) -> Optional[Tuple[float, float, float, float]]:
        """ポリラインのバウンディングボックスを取得 (min_x, min_y, max_x, max_y)"""
        try:
            vertices = list(pline.get_points(format='xy'))
            if not vertices:
                return None
            xs = [v[0] for v in vertices]
            ys = [v[1] for v in vertices]
            return (min(xs), min(ys), max(xs), max(ys))
        except:
            return None

    def _collect_entities_in_boundary(self, boundary, text_handle: str, 
                                       entity_assignment: Dict[str, Tuple[str, float]]) -> int:
        """境界内のエンティティを収集してtext_handleに割り当て"""
        bbox = self._get_polyline_bbox(boundary)
        if not bbox:
            return 0
        
        min_x, min_y, max_x, max_y = bbox
        matched = 0
        
        # バウンディングボックス内のエンティティを探索
        for entity in self.msp:
            if entity.dxf.handle == text_handle:
                continue
            if entity.dxf.handle == boundary.dxf.handle:
                continue
            if entity.dxf.handle in entity_assignment:
                continue
            if entity.dxftype() in ('TEXT', 'MTEXT'):
                continue  # テキストは除外
            
            center = self._get_entity_center(entity)
            if not center:
                continue
            
            # バウンディングボックス内にあるかチェック
            if min_x <= center[0] <= max_x and min_y <= center[1] <= max_y:
                # より厳密にポリライン内部かチェック
                if self._point_in_polyline(center, boundary):
                    entity_assignment[entity.dxf.handle] = (text_handle, 0.95)  # 高信頼度
                    matched += 1
        
        return matched

    def _fallback_proximity_match(self, text_entity, text_handle: str,
                                   entity_assignment: Dict[str, Tuple[str, float]]) -> int:
        """フォールバック: 距離ベースのマッチング（小さい半径）"""
        text_center = self._get_entity_center(text_entity)
        if not text_center:
            return 0
        
        FALLBACK_RADIUS = 300.0  # 小さめの半径
        matched = 0
        
        candidates = self.spatial_index.query_radius(text_center, FALLBACK_RADIUS)
        for entity in candidates:
            if entity.dxf.handle == text_handle:
                continue
            if entity.dxf.handle in entity_assignment:
                continue
            
            entity_center = self._get_entity_center(entity)
            if not entity_center:
                continue
            
            dist = math.sqrt((text_center[0] - entity_center[0])**2 + 
                           (text_center[1] - entity_center[1])**2)
            
            if dist <= FALLBACK_RADIUS:
                score = 0.7 - (dist / FALLBACK_RADIUS) * 0.2
                entity_assignment[entity.dxf.handle] = (text_handle, score)
                matched += 1
        
        return matched

    def _build_index(self):
        """空間インデックスを構築"""
        count = 0
        for entity in self.msp:
            # テキスト以外の幾何学エンティティをインデックス化
            dxftype = entity.dxftype()
            # 対象とするエンティティタイプ
            if dxftype in ('LINE', 'CIRCLE', 'ARC', 'LWPOLYLINE', 'INSERT'):
                bbox = self._get_bbox(entity)
                if bbox and bbox.has_data:
                    self.spatial_index.insert(entity, bbox)
                    count += 1
        # print(f"Indexed {count} entities")

    def _calculate_drawing_bounds(self) -> Optional[BoundingBox2d]:
        """図面全体のバウンディングボックスを計算"""
        try:
            import ezdxf.bbox
            entities = [e for e in self.msp if e.dxftype() in ('LINE', 'CIRCLE', 'ARC', 'LWPOLYLINE', 'INSERT', 'TEXT', 'MTEXT')]
            if entities:
                return ezdxf.bbox.extents(entities)
        except Exception as e:
            print(f"Error calculating drawing bounds: {e}")
        return None

    def _get_adaptive_search_radius(self) -> float:
        """図面サイズに応じた適応的な探索半径を計算"""
        if not self.drawing_bounds or not self.drawing_bounds.has_data:
            return 1000.0  # デフォルト値
        
        # 図面の幅と高さの平均の12%を基本とする
        width = self.drawing_bounds.size.x
        height = self.drawing_bounds.size.y
        avg_dimension = (width + height) / 2
        
        adaptive_radius = avg_dimension * 0.12
        
        # 最小値と最大値で制限
        MIN_RADIUS = 100.0
        MAX_RADIUS = 3000.0
        
        return max(MIN_RADIUS, min(MAX_RADIUS, adaptive_radius))

    def _calculate_match_score(
        self,
        text_center: Tuple[float, float],
        entity_center: Tuple[float, float],
        distance: float,
        search_radius: float
    ) -> float:
        """距離と方向を考慮したマッチングスコアを計算
        
        Returns:
            0.0-1.0のスコア（高いほど関連性が高い）
        """
        # 1. 距離スコア（指数関数的減衰）
        # 距離が0なら1.0、search_radiusなら約0.05
        distance_score = math.exp(-3.0 * distance / search_radius)
        
        # 2. 方向スコア（建築図面の慣例: テキストは上、ジオメトリは下）
        dy = entity_center[1] - text_center[1]  # Y軸の差
        
        # テキストがエンティティより上にある場合（dy < 0）はボーナス
        if dy < 0:
            # テキストが上にある = 望ましい配置
            direction_bonus = 1.1  # 10%ボーナス
        elif abs(dy) < search_radius * 0.1:
            # ほぼ同じ高さ = ニュートラル
            direction_bonus = 1.0
        else:
            # テキストが下にある = やや不自然
            direction_bonus = 0.9  # 10%ペナルティ
        
        # 総合スコア
        total_score = distance_score * direction_bonus
        
        # 0.0-1.0に正規化
        return min(1.0, max(0.0, total_score))

    def _get_bbox(self, entity) -> Optional[BoundingBox2d]:
        """エンティティのバウンディングボックスを取得"""
        try:
            import ezdxf.bbox
            if entity.dxftype() in ('INSERT', 'LWPOLYLINE', 'LINE', 'CIRCLE', 'ARC'):
                 return ezdxf.bbox.extents([entity])
        except Exception:
            pass
        return None

    def _find_part_texts(self, target_layer: str = None) -> List[Any]:
        """部材名と思われるテキストエンティティを抽出
        
        Args:
            target_layer: 対象レイヤー名（Noneの場合は全レイヤー）
        """
        candidates = []
        for entity in self.msp:
            if entity.dxftype() in ('TEXT', 'MTEXT'):
                if target_layer and entity.dxf.layer != target_layer:
                    continue
                text = self._get_text_content(entity)
                if self._is_part_name(text):
                    candidates.append(entity)
        return candidates
    
    def _is_part_name(self, text: str) -> bool:
        """テキストが部材名パターンに一致するか判定"""
        for pattern in PART_NAME_PATTERNS:
            if re.search(pattern, text):
                return True
        return False

    def _calculate_confidence(self, linked_count: int, scores: List[float] = None) -> float:
        """紐づけの信頼度を計算
        
        Args:
            linked_count: 紐づいたエンティティ数
            scores: 各マッチングのスコアリスト
        
        Returns:
            0.0-1.0の信頼度
        """
        if linked_count == 0:
            return 0.0
        
        # 基本信頼度（エンティティ数ベース）
        if 1 <= linked_count <= 50:
            base_confidence = 0.9
        elif linked_count > 50:
            base_confidence = 0.5  # 多すぎる（ノイズの可能性）
        else:
            base_confidence = 0.7
        
        # スコアの平均値で調整
        if scores and len(scores) > 0:
            avg_score = sum(scores) / len(scores)
            # スコアが高いほど信頼度を上げる
            score_bonus = (avg_score - 0.5) * 0.2  # -0.1 ~ +0.1の範囲
            confidence = base_confidence + score_bonus
        else:
            confidence = base_confidence
        
        # 0.0-1.0に制限
        return max(0.0, min(1.0, confidence))

    def _get_entity_center(self, entity) -> Optional[Tuple[float, float]]:
        """エンティティの中心座標を計算"""
        try:
            dxftype = entity.dxftype()
            if dxftype in ('TEXT', 'MTEXT', 'INSERT'):
                return (entity.dxf.insert.x, entity.dxf.insert.y)
            elif dxftype == 'LINE':
                return (
                    (entity.dxf.start.x + entity.dxf.end.x) / 2,
                    (entity.dxf.start.y + entity.dxf.end.y) / 2
                )
            elif dxftype in ('CIRCLE', 'ARC'):
                return (entity.dxf.center.x, entity.dxf.center.y)
            elif dxftype == 'LWPOLYLINE':
                # BBoxの中心を使う
                if entity.dxf.handle in self.spatial_index.entity_bboxes:
                     return self.spatial_index.entity_bboxes[entity.dxf.handle].center
                else:
                    # インデックスにない場合は計算（あまりないはず）
                    bbox = self._get_bbox(entity)
                    if bbox: return bbox.center
        except:
            pass
        return None
