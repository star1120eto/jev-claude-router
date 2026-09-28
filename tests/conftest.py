from router.env import load_env

# live テストがローカルの .env のキーを使えるようにする。設定済みの環境変数は上書きしない。
load_env()
