"""
Natural Language Interpreter Service
Handles rule matching and AI interpretation of natural language commands.
"""
import re
import json
import os
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from anthropic import Anthropic

# ルールファイルのパス
RULES_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'rules.json')

# 色名からACI番号へのマッピング
COLOR_NAME_TO_ACI = {
    '赤': 1, 'あか': 1, 'red': 1,
    '黄': 2, 'きいろ': 2, '黄色': 2, 'yellow': 2,
    '緑': 3, 'みどり': 3, 'green': 3,
    'シアン': 4, 'cyan': 4, '水色': 4,
    '青': 5, 'あお': 5, 'blue': 5,
    'マゼンタ': 6, 'magenta': 6, 'ピンク': 6,
    '白': 7, 'しろ': 7, 'white': 7,
    '黒': 7, 'くろ': 7, 'black': 7,  # CADでは白と黒は同じ
    'グレー': 8, 'gray': 8, 'grey': 8, '灰色': 8,
}


class Interpreter:
    """自然言語コマンド解釈クラス"""
    
    def __init__(self):
        load_dotenv()
        try:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                self.client = Anthropic(api_key=api_key)
            else:
                self.client = None
                print("Warning: ANTHROPIC_API_KEY not set.")
        except Exception as e:
            self.client = None
            print(f"Failed to init Anthropic client: {e}")

        self.rules = self._load_rules()
        self.builtin_patterns = self._init_builtin_patterns()
    
    def _load_rules(self) -> List[dict]:
        """ルールファイルを読み込み"""
        if os.path.exists(RULES_FILE):
            with open(RULES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    
    def _save_rules(self):
        """ルールファイルを保存"""
        os.makedirs(os.path.dirname(RULES_FILE), exist_ok=True)
        with open(RULES_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.rules, f, ensure_ascii=False, indent=2)
    
    def _init_builtin_patterns(self) -> List[dict]:
        """組み込みパターンを初期化"""
        return [
            # 色指定削除
            {
                'pattern': r'(.+?)(?:色)?(?:の)?(?:線|エンティティ)?を?(?:消して|削除|消す|除去)',
                'handler': self._handle_delete_by_color,
                'description': '色指定削除'
            },
            # レイヤー削除 (レイヤーという言葉が必須)
            {
                'pattern': r'(?:レイヤー)[「「]?(.+?)[」」]?を?(?:消して|削除|消す|除去)',
                'handler': self._handle_delete_by_layer,
                'description': 'レイヤー削除'
            },
            # テキスト置換（プレフィックス追加）
            {
                'pattern': r'(?:部材名|テキスト)に[「「]?(.+?)[」」]?を?(?:追加|付けて|付加)',
                'handler': self._handle_add_prefix,
                'description': 'プレフィックス追加'
            },
            # テキスト置換（一般）
            {
                'pattern': r'[「「]?(.+?)[」」]?を[「「]?(.+?)[」」]?に(?:置換|変更|置き換え)',
                'handler': self._handle_replace_text,
                'description': 'テキスト置換'
            },

            # 部材削除 (コメントアウト: 空間的クエリをAIに処理させるため)
            # {
            #     'pattern': r'(?:部材|部品|パーツ)[「「]?(.+?)[」」]?(?:を|の)?(?:消して|削除|消す|除去)',
            #     'handler': self._handle_delete_part,
            #     'description': '部材削除'
            # },
        ]
    
    async def interpret(self, text: str, session_id: str, context: Optional[dict] = None) -> Dict[str, Any]:
        """自然言語コマンドを解釈"""
        text = text.strip()
        
        # 1. 登録済みルールを優先的にマッチング
        for rule in self.rules:
            if re.search(rule['pattern'], text, re.IGNORECASE):
                return {
                    'commands': [{
                        'operation': rule['operation'],
                        'params': rule['params'],
                        'confidence': 1.0,
                        'explanation': f"ルール「{rule['description']}」にマッチしました"
                    }],
                    'message': f"ルールを適用: {rule['description']}",
                    'used_ai': False
                }
        
        # 2. 組み込みパターンでマッチング
        for pattern in self.builtin_patterns:
            match = re.search(pattern['pattern'], text, re.IGNORECASE)
            if match:
                result = pattern['handler'](match, text)
                if result:
                    return {
                        'commands': [result],
                        'message': f"パターンを検出: {pattern['description']}",
                        'used_ai': False
                    }
        
        # 3. AI解釈（Claude API）
        if self.client:
            try:
                return await self._interpret_with_ai(text, context)
            except Exception as e:
                print(f"AI Error: {e}")
                return {
                    'commands': [],
                    'message': f"AIによる解釈中にエラーが発生しました: {str(e)}",
                    'used_ai': True
                }
        else:
             return {
                'commands': [],
                'message': "AI機能を使用するには `.env` ファイルに `ANTHROPIC_API_KEY` を設定してください。\n"
                           "設定後、サーバーを再起動する必要があります。",
                'used_ai': False
            }

    async def _interpret_with_ai(self, text: str, context: Optional[dict] = None) -> Dict[str, Any]:
        """Claude APIで自然言語を解釈"""
        if not self.client:
            return {
                "success": False,
                "commands": [],
                "message": "AI機能を使用するには `.env` ファイルに `ANTHROPIC_API_KEY` を設定してください。設定後、サーバーを再起動する必要があります。"
            }

        context_str = ""
        if context:
            if 'layers' in context:
                layers = [l['name'] for l in context['layers']]
                context_str += f"Existing Layers (Reference only): {', '.join(layers)}\n"
            if 'colors_used' in context:
                colors = [f"{c['name']}(ACI:{c['aci']})" for c in context['colors_used']]
                context_str += f"Used Colors (Reference only): {', '.join(colors)}\n"
            if 'parts' in context:
                # 部材情報は量が多いので先頭の一部だけ
                parts_info = []
                for p in context['parts'][:30]:
                    info = f"{p['part_name']}"
                    if 'center' in p and p['center']:
                        # 座標情報を付与 (X, Y)
                        info += f"(Pos:{int(p['center'][0])},{int(p['center'][1])})"
                    parts_info.append(info)
                context_str += f"Detected Parts (Sample with Pos): {', '.join(parts_info)}\n"
            if 'selected_parts' in context and context['selected_parts']:
                selected = context['selected_parts']
                context_str += f"\n⚠️ USER SELECTED PARTS: {', '.join(selected)}\n(PRIORITY: User explicitly selected these parts. Focus operations on them unless told otherwise.)\n"

        system_prompt = """
You are an expert CAD operator assistant.
Your task is to translate user's natural language instructions into a list of specific operations for a DXF editor system.

Available Operations (Schema):
- delete_by_color(color: int)
  * Remove all entities of a specific color.
  * color is ACI (AutoCAD Color Index) 1-255.
  * Common: 1:Red, 2:Yellow, 3:Green, 4:Cyan, 5:Blue, 6:Magenta, 7:White/Black
- delete_by_layer(layer: str)
  * Remove all entities on a specific layer.
- delete_part(part_name: str)
  * Remove a specific part (text + linked geometry) by its name (e.g., "DF-01").
- rename_text(pattern: str, replacement: str)
  * Regex text replacement.

Rules:
1. Return ONLY a valid JSON object. No explanation, no markdown fence.
2. The JSON must follow this structure:
{
  "commands": [
    {
      "operation": "operation_name",
      "params": { ... },
      "confidence": 0.0-1.0,
      "explanation": "Reasoning must be included here. Example: 'I compared the Y coordinates of all parts. DF-03 has Y=10, which is the lowest, so I selected it.'"
    }
  ],
  "message": "Polite response to the user in Japanese"
}
3. STRICTLY FORBIDDEN: Do not invent Layer names or Color names that are not in the Context.
   - WRONG: delete_by_layer("Bottom Part") -> No such layer.
   - CORRECT: Calculate which part is at the bottom using coordinates, then use delete_part("DF-01").
4. IMPORTANT: If the user asks to delete a "part" (部材/部品) with spatial terms (top/bottom/right/left/upper/lower):
   - IGNORE layers.
   - DO NOT assume the words "bottom (一番下)" or "part (部材)" are the NAME of the part.
   - Look at 'Detected Parts' positions.
   - Identify the part name (e.g., DF-01) based on X/Y coordinates (Y-axis: often Top is High, Bottom is Low, but check relative values).
   - Use `delete_part` with the specific part_name found (e.g. "DF-01").
   - WRONG: delete_part("一番下")
   - CORRECT: delete_part("DF-01") (after verifying DF-01 is at the bottom)
5. If the user's request is ambiguous or impossible, return empty commands and ask for clarification.
6. SELECTED PARTS PRIORITY: If the context includes "USER SELECTED PARTS", prioritize operations on those parts.
   - Example: User selected [DF-01, DF-02] and says "delete these" → delete only DF-01 and DF-02
   - If user says "delete all parts except selected", delete everything EXCEPT the selected ones
"""

        user_message = f"""
Context Information:
{context_str}

User Instruction:
{text}
"""

        print(f"DEBUG: System Prompt:\n{system_prompt}")
        print(f"DEBUG: User Message:\n{user_message}")

        response = self.client.messages.create(
            model="claude-opus-4-5-20251101",
            max_tokens=1000,
            temperature=0,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_message}
            ]
        )

        content = response.content[0].text
        print(f"DEBUG: AI Raw Response:\n{content}")
        
        # JSON抽出（Markdown対策）
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            result = json.loads(json_str)
            result['used_ai'] = True
            return result
        
        raise ValueError("No JSON found in AI response")
    
    def _handle_delete_by_color(self, match, text: str) -> Optional[dict]:
        """色指定削除コマンドを処理"""
        color_text = match.group(1).strip()
        
        # 色名からACI番号を取得
        aci = None
        for name, code in COLOR_NAME_TO_ACI.items():
            if name in color_text:
                aci = code
                break
        
        if aci is None:
            # 数値として解釈を試みる
            numbers = re.findall(r'\d+', color_text)
            if numbers:
                aci = int(numbers[0])
        
        if aci is not None:
            return {
                'operation': 'delete_by_color',
                'params': {'color': aci},
                'confidence': 0.9,
                'explanation': f"ACI色番号 {aci} のエンティティを削除します"
            }
        
        return None
    
    def _handle_delete_by_layer(self, match, text: str) -> Optional[dict]:
        """レイヤー削除コマンドを処理"""
        layer_name = match.group(1).strip()
        
        # 「〜レイヤー」という表現を除去
        layer_name = re.sub(r'レイヤー$', '', layer_name).strip()
        
        if layer_name:
            return {
                'operation': 'delete_by_layer',
                'params': {'layer': layer_name},
                'confidence': 0.85,
                'explanation': f"レイヤー「{layer_name}」のエンティティを削除します"
            }
        
        return None
    
    def _handle_add_prefix(self, match, text: str) -> Optional[dict]:
        """プレフィックス追加コマンドを処理"""
        prefix = match.group(1).strip()
        
        if prefix:
            # 部材名パターン: DF-xx, D1890番 など
            return {
                'operation': 'rename_text',
                'params': {
                    'pattern': r'^(DF-\d+|D\d+番?)',
                    'replacement': f'{prefix}\\1'
                },
                'confidence': 0.8,
                'explanation': f"部材名に「{prefix}」を追加します"
            }
        
        return None
    
    def _handle_replace_text(self, match, text: str) -> Optional[dict]:
        """テキスト置換コマンドを処理"""
        old_text = match.group(1).strip()
        new_text = match.group(2).strip()
        
        if old_text:
            return {
                'operation': 'rename_text',
                'params': {
                    'pattern': re.escape(old_text),
                    'replacement': new_text
                },
                'confidence': 0.9,
                'explanation': f"「{old_text}」を「{new_text}」に置換します"
            }
        
        
        return None
    
    def _handle_delete_part(self, match, text: str) -> Optional[dict]:
        """部材削除コマンドを処理"""
        part_name = match.group(1).strip()
        
        if part_name:
            return {
                'operation': 'delete_part',
                'params': {'part_name': part_name},
                'confidence': 0.85,
                'explanation': f"部材「{part_name}」とその構成要素を削除します"
            }
        
        return None
    
    def add_rule(self, pattern: str, operation: str, params: dict, description: str):
        """新しいルールを追加"""
        self.rules.append({
            'pattern': pattern,
            'operation': operation,
            'params': params,
            'description': description
        })
        self._save_rules()
    
    def get_rules(self) -> List[dict]:
        """登録済みルールを取得"""
        return self.rules
