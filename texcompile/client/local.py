import subprocess
import os
import shutil
import tempfile
import re
from io import BytesIO
from typing import Tuple

# --- 環境に合わせて設定する定数 ---
# 【修正箇所】呼び出すべきPerlのフルパスを明示的に指定
PERL_BINARY_PATH = "/usr/bin/perl"
PERL_SCRIPT_PATH = "/TEX/texannotate/texcompile/service/run_autotex.pl"
TEXLIVE_PATH = "/usr/local/texlive/2025"
TEXLIVE_BIN_PATH = "/usr/local/texlive/2025/bin/x86_64-linux"
# ------------------------------------

class LocalCompilationException(Exception):
    """ローカルでのコンパイル失敗を示すカスタム例外"""
    pass

def compile_pdf_locally(sources_dir: str) -> Tuple[str, BytesIO]:
    """
    指定されたソースディレクトリのTeXプロジェクトをローカル環境でコンパイルし、
    結果のPDFの (ファイル名, BytesIOオブジェクト) を返す。
    （関数の他の部分は変更ありません）
    """
    if not os.path.isdir(sources_dir):
        raise FileNotFoundError(f"指定されたソースディレクトリが見つかりません: {sources_dir}")

    with tempfile.TemporaryDirectory() as temp_dir:
        # ... (ソースのコピーと権限変更のコードはそのまま) ...
        for item in os.listdir(sources_dir):
            s = os.path.join(sources_dir, item)
            d = os.path.join(temp_dir, item)
            if os.path.isdir(s):
                shutil.copytree(s, d)
            else:
                shutil.copy2(s, d)
        try:
            subprocess.run(["chmod", "-R", "775", temp_dir], check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            raise LocalCompilationException(f"権限の変更に失敗しました: {e.stderr.decode()}")
        
        # 【修正箇所】コマンドの組み立て部分で、新しい定数を使う
        command = [
            PERL_BINARY_PATH,  # "perl" ではなく、フルパスを指定
            PERL_SCRIPT_PATH,
            temp_dir,
            TEXLIVE_PATH,
            TEXLIVE_BIN_PATH
        ]

        print(f"実行コマンド: {' '.join(command)}")
        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True
            )
        except subprocess.CalledProcessError as e:
            error_message = (
                f"Perlスクリプトの実行に失敗しました。\n"
                f"--- STDOUT ---\n{e.stdout}\n"
                f"--- STDERR ---\n{e.stderr}"
            )
            raise LocalCompilationException(error_message)

        # ... (残りのコードはそのまま) ...
        match = re.search(r"Generated PDF: (.*?)<end of PDF name>", result.stdout)
        if not match:
            error_message = (f"コンパイルは成功しましたが、PDFファイル名の取得に失敗しました。\n--- STDOUT ---\n{result.stdout}\n--- STDERR ---\n{result.stderr}")
            raise LocalCompilationException(error_message)
        pdf_filename = match.group(1)
        pdf_path = os.path.join(temp_dir, pdf_filename)
        if not os.path.exists(pdf_path):
            raise LocalCompilationException(f"生成されたはずのPDFファイルが見つかりません: {pdf_path}")
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        print(f"コンパイル成功: {pdf_filename} ({len(pdf_bytes)} bytes)")
        return (pdf_filename, BytesIO(pdf_bytes))