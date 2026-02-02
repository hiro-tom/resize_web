# 画像圧縮WEBアプリ

Python + Flask で動作する画像圧縮アプリです。ログイン後に画像をアップロードし、圧縮率・サイズ・DPIを指定して変換し、ダウンロードできます。

## 使い方

1. 依存関係をインストール

```
pip install -r requirements.txt
```

2. アプリ起動

```
python app.py
```

3. ブラウザでアクセス

```
http://127.0.0.1:5000
```

## ログイン情報

初期値は以下です。環境変数で変更できます。

- ID: `admin`
- パスワード: `password`

### 環境変数

- `APP_USERNAME`
- `APP_PASSWORD`
- `APP_SECRET_KEY`

## 対応形式

- JPEG
- PNG
- WebP

## 注意点

- PNGをJPEGに変換する場合、透過部分は白で埋められます。
- DPIは画像メタデータとして保存されます。
