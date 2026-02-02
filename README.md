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

## AWS EC2へのデプロイ

AWS CLIを使用してEC2インスタンスを作成し、アプリをデプロイする手順です。

### 前提条件

- AWS CLIがインストール・設定済み
- 適切なIAM権限（EC2, VPC関連）

### 1. セキュリティグループの作成

```bash
# セキュリティグループを作成
aws ec2 create-security-group \
  --group-name resize-web-sg \
  --description "Security group for resize-web app" \
  --vpc-id <your-vpc-id>

# SSH (22), HTTP (80), アプリ (5000) ポートを開放
aws ec2 authorize-security-group-ingress \
  --group-name resize-web-sg \
  --protocol tcp --port 22 --cidr 0.0.0.0/0

aws ec2 authorize-security-group-ingress \
  --group-name resize-web-sg \
  --protocol tcp --port 80 --cidr 0.0.0.0/0

aws ec2 authorize-security-group-ingress \
  --group-name resize-web-sg \
  --protocol tcp --port 5000 --cidr 0.0.0.0/0
```

### 2. キーペアの作成

```bash
aws ec2 create-key-pair \
  --key-name resize-web-key \
  --query "KeyMaterial" \
  --output text > resize-web-key.pem

# 権限設定 (Linux/Mac)
chmod 400 resize-web-key.pem
```

### 3. ユーザーデータスクリプトの作成

`userdata.sh` を作成:

```bash
#!/bin/bash
yum update -y
yum install -y python3 python3-pip git

cd /tmp
git clone https://github.com/hiro-tom/resize_web.git
cd resize_web

python3 -m pip install -r requirements.txt

# バックグラウンドでアプリを起動
nohup python3 app.py > /var/log/resize-web.log 2>&1 &
```

### 4. EC2インスタンスの起動

```bash
# 最新のAmazon Linux 2023 AMIを取得
AMI_ID=$(aws ec2 describe-images \
  --owners amazon \
  --filters "Name=name,Values=al2023-ami-2023*-x86_64" "Name=state,Values=available" \
  --query "Images | sort_by(@, &CreationDate) | [-1].ImageId" \
  --output text)

# EC2インスタンスを起動
aws ec2 run-instances \
  --image-id $AMI_ID \
  --instance-type t2.micro \
  --key-name resize-web-key \
  --security-group-ids <your-sg-id> \
  --subnet-id <your-subnet-id> \
  --associate-public-ip-address \
  --user-data file://userdata.sh \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=resize-web-app}]"
```

### 5. アクセス確認

```bash
# パブリックIPを取得
aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=resize-web-app" "Name=instance-state-name,Values=running" \
  --query "Reservations[0].Instances[0].PublicIpAddress" \
  --output text
```

ブラウザで `http://<Public-IP>:5000` にアクセス

### SSH接続

```bash
ssh -i resize-web-key.pem ec2-user@<Public-IP>
```

### インスタンスの停止・削除

```bash
# 停止
aws ec2 stop-instances --instance-ids <instance-id>

# 削除
aws ec2 terminate-instances --instance-ids <instance-id>
```
