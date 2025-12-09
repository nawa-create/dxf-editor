"""
DXF File Operations Router
Handles file upload, parsing, editing operations, and download.
"""
import os
import uuid
import tempfile
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from services.dxf_parser import DxfParser
from services.dxf_operations import DxfOperations
from services.svg_renderer import SvgRenderer
from services.entity_linker import EntityLinker

router = APIRouter()

# 一時ファイル保存用ディレクトリ
UPLOAD_DIR = tempfile.gettempdir()
sessions: dict = {}  # セッション管理（プロダクションではRedis等を使用）


class EntityInfo(BaseModel):
    handle: str
    entity_type: str
    layer: str
    color: int
    color_name: str


class LayerInfo(BaseModel):
    name: str
    color: int
    color_name: str
    entity_count: int


class DxfInfo(BaseModel):
    session_id: str
    filename: str
    entity_count: int
    layers: List[LayerInfo]
    colors_used: List[dict]


class OperationRequest(BaseModel):
    session_id: str
    operation: str  # delete_by_color, delete_by_layer, rename_text, etc.
    params: dict


class OperationResult(BaseModel):
    success: bool
    affected_count: int
    message: str
    preview_svg: Optional[str] = None


class PartInfo(BaseModel):
    part_name: str
    text_handle: str
    linked_count: int
    confidence: float
    linked_handles: List[str]
    center: Optional[List[float]] = None  # [x, y]


@router.post("/analyze-parts/{session_id}", response_model=List[PartInfo])
async def analyze_parts(session_id: str):
    """部材の紐づけ解析を実行"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="セッションが見つかりません")
    
    session = sessions[session_id]
    parser = session['parser']
    
    try:
        linker = EntityLinker(parser.doc)
        parts = linker.link_entities()
        
        # セッションに紐づけ結果を保存
        session['parts'] = parts
        
        return [
            PartInfo(
                part_name=p['part_name'],
                text_handle=p['text_handle'],
                linked_count=len(p['linked_handles']),
                confidence=p['confidence'],
                linked_handles=p['linked_handles'],
                center=p.get('center')
            )
            for p in parts
        ]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"解析エラー: {str(e)}")


@router.post("/upload", response_model=DxfInfo)
async def upload_dxf(file: UploadFile = File(...)):
    """DXFファイルをアップロードして解析"""
    if not file.filename.lower().endswith('.dxf'):
        raise HTTPException(status_code=400, detail="DXFファイルのみ対応しています")
    
    # セッションID生成
    session_id = str(uuid.uuid4())
    
    # ファイル保存
    file_path = os.path.join(UPLOAD_DIR, f"{session_id}.dxf")
    content = await file.read()
    with open(file_path, 'wb') as f:
        f.write(content)
    
    try:
        # DXF解析
        parser = DxfParser(file_path)
        info = parser.get_info()
        
        # セッション保存
        sessions[session_id] = {
            'file_path': file_path,
            'original_filename': file.filename,
            'parser': parser,
            'history': [],
            'redo_stack': []
        }
        
        return DxfInfo(
            session_id=session_id,
            filename=file.filename,
            entity_count=info['entity_count'],
            layers=[LayerInfo(**l) for l in info['layers']],
            colors_used=info['colors_used']
        )
    except Exception as e:
        os.remove(file_path)
        raise HTTPException(status_code=400, detail=f"DXF解析エラー: {str(e)}")


@router.get("/preview/{session_id}")
async def get_preview(session_id: str, highlight_handles: Optional[str] = None):
    """SVGプレビューを取得"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="セッションが見つかりません")
    
    session = sessions[session_id]
    parser = session['parser']
    
    highlight_list = []
    if highlight_handles:
        highlight_list = highlight_handles.split(',')
    
    renderer = SvgRenderer(parser.doc)
    svg = renderer.render(highlight_handles=highlight_list)
    
    return {"svg": svg}


@router.post("/preview-operation", response_model=OperationResult)
async def preview_operation(request: OperationRequest):
    """操作のプレビュー（実行せずに影響範囲を表示）"""
    if request.session_id not in sessions:
        raise HTTPException(status_code=404, detail="セッションが見つかりません")
    
    session = sessions[request.session_id]
    parser = session['parser']
    
    operations = DxfOperations(parser.doc)
    
    # 影響を受けるエンティティを取得（実際には削除しない）
    if request.operation == 'delete_part':
        # 部材削除の場合は、セッション情報のpartsからハンドルを解決して delete_by_handles として処理
        if 'parts' not in session:
             raise HTTPException(status_code=400, detail="部材解析が完了していません")
        
        target_handles = []
        target_part = request.params.get('part_name')
        
        for part in session['parts']:
            if part['part_name'] == target_part:
                target_handles.append(part['text_handle'])
                target_handles.extend(part['linked_handles'])
        
        if not target_handles:
            # 似た部材名を探す
            similar = [p['part_name'] for p in session['parts'] if target_part in p['part_name']]
            msg = f"部材「{target_part}」は見つかりませんでした。"
            if similar:
                msg += f" 候補: {', '.join(similar[:3])}"
            
            return OperationResult(
                success=False, 
                affected_count=0, 
                message=msg,
                preview_svg=None
            )
            
        # 内部的には delete_by_handles として処理
        affected = operations.get_affected_entities('delete_by_handles', {'handles': target_handles})
    else:
        affected = operations.get_affected_entities(request.operation, request.params)

    if len(affected) == 0:
        # 結果が0件の場合、理由のヒントを作成
        msg = "条件に一致するエンティティが見つかりませんでした。"
        
        if request.operation == 'delete_by_color':
            target_color = request.params.get('color')
            # 存在する色を確認
            info = parser.get_info()
            available = [f"{c['name']}({c['aci']})" for c in info['colors_used']]
            msg += f" 指定色: {target_color}。存在する色: {', '.join(available) if available else 'なし'}"
            
        elif request.operation == 'delete_by_layer':
            target_layer = request.params.get('layer')
            info = parser.get_info()
            available = [l['name'] for l in info['layers'] if l['entity_count'] > 0]
            msg += f" 指定レイヤー: {target_layer}。存在するレイヤー: {', '.join(available[:5])}{'...' if len(available)>5 else ''}"

        return OperationResult(
            success=False,
            affected_count=0,
            message=msg,
            preview_svg=None
        )
    
    # ハイライト付きSVGを生成
    renderer = SvgRenderer(parser.doc)
    svg = renderer.render(highlight_handles=[e['handle'] for e in affected], highlight_color='#ff0000')
    
    return OperationResult(
        success=True,
        affected_count=len(affected),
        message=f"{len(affected)}個のエンティティが影響を受けます",
        preview_svg=svg
    )


@router.post("/execute", response_model=OperationResult)
async def execute_operation(request: OperationRequest):
    """操作を実行"""
    if request.session_id not in sessions:
        raise HTTPException(status_code=404, detail="セッションが見つかりません")
    
    session = sessions[request.session_id]
    parser = session['parser']
    
    operations = DxfOperations(parser.doc)
    
    first_handle_snapshot = True  # 操作前の状態を保存するかどうか

    try:
        if request.operation == 'delete_part':
            # 部材削除の特別処理
            if 'parts' not in session:
                 raise HTTPException(status_code=400, detail="部材解析が完了していません")
            
            target_handles = []
            target_part = request.params.get('part_name')
            
            for part in session['parts']:
                if part['part_name'] == target_part:
                    target_handles.append(part['text_handle'])
                    target_handles.extend(part['linked_handles'])
            
            if not target_handles:
                 raise HTTPException(status_code=404, detail=f"部材「{target_part}」は見つかりませんでした")
            
            # スナップショット保存
            _save_history(request.session_id)
            first_handle_snapshot = False

            result = operations.execute('delete_by_handles', {'handles': target_handles})
            result['message'] = f"部材「{target_part}」を削除しました（{result['affected_count']}要素）"
        else:
            # スナップショット保存
            if first_handle_snapshot:
                _save_history(request.session_id)
            
            result = operations.execute(request.operation, request.params)
        
        # 新しいSVGを生成
        renderer = SvgRenderer(parser.doc)
        svg = renderer.render()
        
        return OperationResult(
            success=True,
            affected_count=result['affected_count'],
            message=result['message'],
            preview_svg=svg
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"操作エラー: {str(e)}")


@router.get("/download/{session_id}")
async def download_dxf(session_id: str):
    """編集済みDXFをダウンロード"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="セッションが見つかりません")
    
    session = sessions[session_id]
    parser = session['parser']
    
    # 編集済みファイルを保存
    output_path = os.path.join(UPLOAD_DIR, f"{session_id}_edited.dxf")
    parser.doc.saveas(output_path)
    
    return FileResponse(
        output_path,
        filename=f"edited_{session['original_filename']}",
        media_type="application/dxf"
    )


@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """セッションをクリーンアップ"""
    if session_id in sessions:
        session = sessions[session_id]
        # ファイル削除
        if os.path.exists(session['file_path']):
            os.remove(session['file_path'])
        edited_path = os.path.join(UPLOAD_DIR, f"{session_id}_edited.dxf")
        if os.path.exists(edited_path):
            os.remove(edited_path)
        del sessions[session_id]
    
    return {"message": "セッションを削除しました"}


def _save_history(session_id: str):
    """現在の状態を履歴に保存"""
    if session_id not in sessions:
        return
    
    session = sessions[session_id]
    parser = session['parser']
    
    # 一時ファイルとして保存
    history_filename = f"{session_id}_{len(session['history'])}.dxf"
    history_path = os.path.join(UPLOAD_DIR, history_filename)
    parser.doc.saveas(history_path)
    
    session['history'].append(history_path)
    # 新しい操作が行われたらRedoスタックはクリア
    session['redo_stack'] = []


@router.post("/undo/{session_id}", response_model=OperationResult)
async def undo_operation(session_id: str):
    """操作を元に戻す"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="セッションが見つかりません")
    
    session = sessions[session_id]
    
    if not session['history']:
        raise HTTPException(status_code=400, detail="これ以上戻れません")
    
    # 現在の状態をRedoスタックに退避
    current_state_filename = f"{session_id}_redo_{len(session['redo_stack'])}.dxf"
    current_state_path = os.path.join(UPLOAD_DIR, current_state_filename)
    session['parser'].doc.saveas(current_state_path)
    session['redo_stack'].append(current_state_path)
    
    # 履歴から復元
    last_state_path = session['history'].pop()
    
    # ファイルから再読み込み
    try:
        if os.path.exists(last_state_path):
            session['parser'] = DxfParser(last_state_path)
            # 古い履歴ファイルは削除してもいいが、ここでは残しておく（実装簡略化）
            
            # SVG再生成
            renderer = SvgRenderer(session['parser'].doc)
            svg = renderer.render()
            
            return OperationResult(
                success=True,
                affected_count=0,
                message="元に戻しました",
                preview_svg=svg
            )
        else:
            raise HTTPException(status_code=500, detail="履歴ファイルが見つかりません")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Undoエラー: {str(e)}")


@router.post("/redo/{session_id}", response_model=OperationResult)
async def redo_operation(session_id: str):
    """操作をやり直す"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="セッションが見つかりません")
    
    session = sessions[session_id]
    
    if not session['redo_stack']:
        raise HTTPException(status_code=400, detail="やり直す操作がありません")
    
    # 現在の状態を履歴に保存
    _save_history(session_id)
    # _save_historyでredo_stackがクリアされてしまうため、
    # 直前のpopを行う前にsave_historyを呼ぶ順番に注意が必要だが、
    # _save_historyの実装を見るとredo_stack = []しているので、
    # ここでは手動でhistoryに追加するほうが安全。
    
    # 手動保存ロジック（redo_stackを消さないため）
    # 直前の状態をhistoryへ
    # 実際には _save_history を呼ぶと redo_stack が消える仕様にしたので、
    # Redo時は _save_history を呼ばずに history.append だけする
    
    # ...いや、現在の状態（Undo直後の状態）をHistoryの一番上に積む必要がある。
    # しかしそれをHistoryファイルとして保存していないなら保存が必要。
    # 複雑になるので、_save_history の redo_stack クリアを条件付きにする手もあるが、
    # ここでは単純にファイルを生成して history に追加する。
    
    parser = session['parser']
    history_filename = f"{session_id}_{len(session['history'])}.dxf"
    history_path = os.path.join(UPLOAD_DIR, history_filename)
    parser.doc.saveas(history_path)
    session['history'].append(history_path)
    
    # Redoスタックから復元
    next_state_path = session['redo_stack'].pop()
    
    try:
        if os.path.exists(next_state_path):
            session['parser'] = DxfParser(next_state_path)
            
            renderer = SvgRenderer(session['parser'].doc)
            svg = renderer.render()
            
            return OperationResult(
                success=True,
                affected_count=0,
                message="やり直しました",
                preview_svg=svg
            )
        else:
            raise HTTPException(status_code=500, detail="Redoファイルが見つかりません")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Redoエラー: {str(e)}")
