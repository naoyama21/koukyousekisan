import re
import json
# 提供されたテキストコンテンツを想定
pdf_text_content = """
--- PAGE 1 ---
公共建築数量積算基準
(令和5年改定)
平成15年3月31日国営計第196号
 最終改定令和5年3月29日国営積第8号
この基準は、国土交通省官庁営繕部及び地方整備局等営繕部が官庁施設の営繕を実施
 するための基準として制定したものです。また、この基準は、官庁営繕関係基準類等の
 統一化に関する関係省庁連絡会議の決定に基づく統一基準です。
利用にあたっては、国土交通省ホームページのリンク・著作権・免責事項に関する利
 用ルール (http://www.mlit.go.jp/link.html) をご確認ください。
国土交通省大臣官房官庁営繕部
技術基準トップページはこちら(関連する基準の確認など)
 http://www.mlit.go.jp/gobuild/gobuild_tk2_000017.html

--- PAGE 2 ---

(目次)
第1編 総則
1 適用
2 基本事項
第2編 仮設
第1章 仮設
第3編
第1節 仮設の定義
第2節 仮設の区分
第3節 共通仮設の計測・計算
1 通則
2 共通仮設の計測・計算
第4節
直接仮設の計測・計算
1 通則
2 直接仮設の計測・計算
第5節専用仮設の計測・計算
1 通則
2 専用仮設の計測・計算
土工・地業
第1章 土工
第1節 土工の定義
第2節 土工の計測・計算
1 通則
2 土の処理の計測・計算
3 山留め壁の計測・計算
4 排水の計測・計算
第2章地業
第1節 地業の定義
第2節 地業の計測・計算
1 通則
2 地業の計測・計算
第4編 躯体
第1章 躯体の定義と区分
第1節 躯体の定義
第2節 躯体の区分
第2章 コンクリート部材
"""

def parse_document(text):
    data = {}
    current_path = [] # 階層を示すパス (例: ["第1編 総則", "1 適用"])
    current_level_data = data # 現在データを追加する辞書参照

    lines = text.split('\n')

    # 正規表現の定義（調整が必要になる可能性があります）
    part_re = re.compile(r"^(第\d+編\s+.*)$")
    chapter_re = re.compile(r"^(第\d+章\s+.*)$")
    section_re = re.compile(r"^(第\d+節\s+.*)$")
    numbered_item_re = re.compile(r"^\s*(\d+)\s+(.*)$") # "1 通則"のようなパターン
    parenthesized_item_re = re.compile(r"^\s*(\(\d+\))\s*(.*)$") # "(1) 仮囲い"のようなパターン
    # 更に細かいサブレベルのパターンもここに追加

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # sourceタグの除去 (必要であれば)
        line = re.sub(r"\\s*", "", line)

        # ページ区切り行のスキップ
        if line.startswith('--- PAGE') and line.endswith('---'):
            continue
            
        # 各階層のパターンをチェック
        match_part = part_re.match(line)
        match_chapter = chapter_re.match(line)
        match_section = section_re.match(line)
        match_numbered_item = numbered_item_re.match(line)
        match_parenthesized_item = parenthesized_item_re.match(line)
        
        if match_part:
            title = match_part.group(1)
            # 新しいPartが始まったら、パスをリセットし、新しいエントリを作成
            current_path = [title]
            current_level_data = data
            current_level_data[title] = {}
        elif match_chapter:
            title = match_chapter.group(1)
            # 現在のPartの下にChapterを追加
            if len(current_path) >= 1: # Partの下にいることを確認
                current_path = current_path[:1] + [title] # Partのパスを維持してChapterを追加
                current_level_data = data
                for p in current_path:
                    if p not in current_level_data:
                        current_level_data[p] = {} # 存在しない場合は作成
                    current_level_data = current_level_data[p]
                
            else: # Partが見つかっていない場合のエラーハンドリング
                print(f"Warning: Chapter '{title}' found without a preceding Part. Skipping.")
                continue
        elif match_section:
            title = match_section.group(1)
            # 現在のChapterの下にSectionを追加
            if len(current_path) >= 2: # Chapterの下にいることを確認
                current_path = current_path[:2] + [title] # Chapterのパスを維持してSectionを追加
                current_level_data = data
                for p in current_path:
                    if p not in current_level_data:
                        current_level_data[p] = {} # 存在しない場合は作成
                    current_level_data = current_level_data[p]
            else:
                print(f"Warning: Section '{title}' found without a preceding Chapter. Skipping.")
                continue
        elif match_numbered_item:
            num = match_numbered_item.group(1)
            title = match_numbered_item.group(2)
            full_title = f"{num} {title}"
            # 現在のSectionまたはChapterの下に番号付き項目を追加
            if current_path:
                current_path = current_path[:] + [full_title]
                current_level_data = data
                for p in current_path[:-1]: # 最後の項目はまだ作成中なので除く
                    if p not in current_level_data:
                        current_level_data[p] = {}
                    current_level_data = current_level_data[p]
                current_level_data[full_title] = {"content": []} # 内容をリストで保持
                current_level_data = current_level_data[full_title]
            else:
                print(f"Warning: Numbered item '{full_title}' found without a preceding section. Skipping.")
                continue

        elif match_parenthesized_item:
            num = match_parenthesized_item.group(1)
            title = match_parenthesized_item.group(2)
            full_title = f"{num} {title}"
            # 現在の番号付き項目などの下にかっこ付き項目を追加
            if current_path:
                current_path = current_path[:] + [full_title]
                current_level_data = data
                for p in current_path[:-1]:
                    if p not in current_level_data:
                        current_level_data[p] = {}
                    current_level_data = current_level_data[p]
                current_level_data[full_title] = {"content": []}
                current_level_data = current_level_data[full_title]
            else:
                print(f"Warning: Parenthesized item '{full_title}' found without a preceding item. Skipping.")
                continue
        else:
            # どの見出しにもマッチしない場合、現在の階層のコンテンツとして追加
            if current_level_data and "content" in current_level_data and isinstance(current_level_data["content"], list):
                current_level_data["content"].append(line)
            else:
                # 最初にcontentが来る場合や、階層が正しく設定されていない場合の処理
                # print(f"Warning: Line '{line}' could not be assigned to a hierarchical level.")
                pass # 目次の"（目次）"や最初のヘッダー"公共建築数量積算基準"などを無視
    
    # リストで保持しているcontentを結合して文字列にする
    def join_content(node):
        if isinstance(node, dict):
            if "content" in node and isinstance(node["content"], list):
                node["content"] = "\n".join(node["content"])
            for key, value in node.items():
                join_content(value)
    
    join_content(data)

    return data

extracted_data = parse_document(pdf_text_content)
print(extracted_data) # 抽出結果をコンソールに出力