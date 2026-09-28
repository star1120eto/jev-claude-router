from pathlib import Path

from dotenv import find_dotenv, load_dotenv


def load_env(path: str | Path | None = None) -> bool:
    """ローカルの `.env` を環境変数に読み込む。

    `path` を省略すると、カレントディレクトリから親をたどって `.env` を探す。
    すでに設定されている環境変数は上書きしない。`.env` が見つからなければ何もせず False を返す。
    """
    target = path if path is not None else find_dotenv(usecwd=True)
    if not target:
        return False
    return load_dotenv(target, override=False)
