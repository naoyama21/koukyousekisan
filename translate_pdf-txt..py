import re
import json
import PyPDF2

def extract_text_from_pdf(pdf_path, max_pages=None):
    """
    指定されたPDFファイルからテキストを抽出します。
    max_pagesで読み込む最大ページ数を制限できます (Noneの場合は全ページ)。
    """
    text = ""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            pages_to_read = len(reader.pages) if max_pages is None else min(max_pages, len(reader.pages))
            
            for page_num in range(pages_to_read):
                page = reader.pages[page_num]
                extracted_page_text = page.extract_text()
                
                # ページフッターなどをここで除去
                extracted_page_text = re.sub(r'-\s*\d+\s*-', '', extracted_page_text) # 例: - 1 -
                
                # 特定のヘッダー/フッター、あるいは複数行にわたる文書情報も除去
                extracted_page_text = re.sub(r'公共建築数量積算基準\(令和\d+年改定\)', '', extracted_page_text)
                extracted_page_text = re.sub(r'^\s*最終改定令和\d+年\d+月\d+日国営積第\d+号\s*$', '', extracted_page_text, flags=re.MULTILINE)
                extracted_page_text = re.sub(r'^\s*平成\d+年\d+月\d+日国営計第\d+号\s*$', '', extracted_page_text, flags=re.MULTILINE)
                extracted_page_text = re.sub(r'^\s*この基準は、国土交通省官庁営繕部及び地方整備局等営繕部が官庁施設の営繕を実施.*?\s*統一基準です。\s*$', '', extracted_page_text, flags=re.MULTILINE | re.DOTALL)
                extracted_page_text = re.sub(r'^\s*利用にあたっては、国土交通省ホームページのリンク・著作権・免責事項に関する利.*?\s*ご確認ください。\s*$', '', extracted_page_text, flags=re.MULTILINE | re.DOTALL)
                extracted_page_text = re.sub(r'^\s*国土交通省大臣官房官庁営繕部\s*$', '', extracted_page_text, flags=re.MULTILINE)
                extracted_page_text = re.sub(r'^\s*技術基準トップページはこちら.*?\s*html\s*$', '', extracted_page_text, flags=re.MULTILINE | re.DOTALL)
                
                text += extracted_page_text + "\n--- PAGE_BREAK ---\n" # ページ間の区切りを明示的に追加
    except FileNotFoundError:
        print(f"エラー: 指定されたPDFファイル '{pdf_path}' が見つかりません。")
        return None
    except Exception as e:
        print(f"PDFの読み込み中にエラーが発生しました: {e}")
        return None
    return text

def parse_document(text):
    """
    抽出されたテキストから階層構造を解析し、辞書形式で返します。
    （全角数字の項目「１）」などに対応するよう修正済み）
    """
    data = {}
    current_level_refs = [data] # 各階層の辞書オブジェクトをスタックのように保持
    current_path_keys = [] # 各階層のキー名を保持

    # --- 正規表現の定義 ---
    part_re = re.compile(r"^(第\d+編\s+.*)$")
    chapter_re = re.compile(r"^(第\d+章\s+.*)$")
    section_re = re.compile(r"^(第\d+節\s+.*)$")
    sub_sub_sub_item_re = re.compile(r"^\s*(ア|イ|ウ|エ|オ|カ|キ|ク|ケ|コ)\)\s*(.*)$")
    sub_sub_item_re = re.compile(r"^\s*(①|②|③|④|⑤|⑥|⑦|⑧|⑨|⑩)\s+(.*)$")
    full_width_sub_item_re = re.compile(r"^\s*([１２３４５６７８９０]+）)\s*(.*)$") # 全角数字「１）」に対応
    sub_numbered_item_re = re.compile(r"^\s*(\d+)\)\s*(.*)$")
    parenthesized_item_re = re.compile(r"^\s*（(\d+)）\s*(.*)$")
    numbered_item_re = re.compile(r"^\s*(\d+)\s+(.*)$")

    # --- パターンリストの定義 ---
    re_patterns = [
        ('part', part_re, 0),
        ('chapter', chapter_re, 1),
        ('section', section_re, 2),
        ('sub_sub_sub_item', sub_sub_sub_item_re, 6),
        ('sub_sub_item', sub_sub_item_re, 5),
        ('full_width_sub_item', full_width_sub_item_re, 4), # 全角パターンを追加
        ('sub_numbered_item', sub_numbered_item_re, 4),
        ('parenthesized_item', parenthesized_item_re, 3),
        ('numbered_item', numbered_item_re, 3),
    ]

    # 除外する行のパターン
    exclusion_re = re.compile(r"^\s*\(目次\)$|--- PAGE_BREAK ---")

    lines = text.split('\n')

    for line_raw in lines:
        line = line_raw.strip()
        if not line or exclusion_re.match(line):
            continue
        
        line = re.sub(r"\\s*", "", line)

        matched_type = None
        matched_title = None
        current_matched_level = -1

        for item_type, pattern_obj, level in re_patterns:
            match = pattern_obj.match(line)
            if match:
                matched_type = item_type
                current_matched_level = level
                
                if item_type == 'parenthesized_item':
                    num = match.group(1).translate(str.maketrans('０１２３４５６７８９', '0123456789'))
                    matched_title = f"({num}){match.group(2).strip()}"
                elif item_type == 'sub_sub_sub_item':
                    matched_title = f"{match.group(1)}){match.group(2).strip()}"
                elif item_type in ['sub_numbered_item', 'sub_sub_item', 'full_width_sub_item']:
                    matched_title = f"{match.group(1)}{match.group(2).strip()}"
                else:
                    matched_title = match.group(1).strip()
                break

        if matched_type:
            target_level = current_matched_level
            last_key_in_path = current_path_keys[-1] if current_path_keys else None
            
            if matched_type == 'parenthesized_item' and last_key_in_path and numbered_item_re.match(last_key_in_path):
                target_level = len(current_path_keys)
            
            elif matched_type in ['sub_numbered_item', 'full_width_sub_item'] and last_key_in_path and \
                 (numbered_item_re.match(last_key_in_path) or parenthesized_item_re.match(last_key_in_path)):
                target_level = len(current_path_keys)
            
            elif matched_type == 'sub_sub_item' and last_key_in_path and \
                 (sub_numbered_item_re.match(last_key_in_path) or full_width_sub_item_re.match(last_key_in_path)):
                target_level = len(current_path_keys)

            elif matched_type == 'sub_sub_sub_item' and last_key_in_path and sub_sub_item_re.match(last_key_in_path):
                target_level = len(current_path_keys)

            while len(current_path_keys) > target_level:
                current_path_keys.pop()
                current_level_refs.pop()

            current_path_keys.append(matched_title)
            
            current_parent_dict = current_level_refs[-1]
            current_parent_dict[matched_title] = {}
            current_level_refs.append(current_parent_dict[matched_title])
            
            current_parent_dict[matched_title]["content"] = []

        else:
            if current_level_refs and "content" in current_level_refs[-1]:
                current_level_refs[-1]["content"].append(line)

    def clean_and_join_content(node):
        if isinstance(node, dict):
            if "content" in node and isinstance(node["content"], list):
                joined_content = " ".join(node["content"]).strip()
                joined_content = re.sub(r'([、。])\s+', r'\1', joined_content)
                joined_content = re.sub(r'\s+', ' ', joined_content)

                if joined_content:
                    node["content"] = joined_content
                else:
                    del node["content"]
            
            for key, value in list(node.items()):
                if isinstance(value, dict) and not value:
                    del node[key]
                else:
                    clean_and_join_content(value)
    
    clean_and_join_content(data)
    return data

# --- メイン処理 ---
if __name__ == "__main__":
    # 1. 入力と出力のファイルパスを指定
    pdf_path = "001178206.pdf"  # 解析したいPDFファイル
    output_filename = "public_building_standards.json"  # 出力するJSONファイル名

    print(f"'{pdf_path}' からテキストを抽出しています...")
    extracted_text = extract_text_from_pdf(pdf_path)

    if extracted_text:
        print("テキストの抽出が完了しました。構造を解析しています...")
        extracted_structured_data = parse_document(extracted_text)
        print("解析が完了しました。")

        # 2. 構造化されたデータをJSONとして出力
        try:
            with open(output_filename, "w", encoding="utf-8") as f:
                json.dump(extracted_structured_data, f, ensure_ascii=False, indent=4)
            print(f"✅ データが '{output_filename}' に正常に保存されました。")
        except IOError as e:
            print(f"❌ ファイルの保存中にエラーが発生しました: {e}")