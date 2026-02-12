import io
import json
import os
import zipfile
from datetime import timedelta
from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
from PIL import Image

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
DEFAULT_USERNAME = os.getenv("APP_USERNAME", "admin")
DEFAULT_PASSWORD = os.getenv("APP_PASSWORD", "password")

app = Flask(__name__)
app.secret_key = os.getenv("APP_SECRET_KEY", "change-me")
app.permanent_session_lifetime = timedelta(hours=4)
os.makedirs(app.instance_path, exist_ok=True)
CREDENTIALS_PATH = os.path.join(app.instance_path, "credentials.json")


def load_credentials() -> dict:
    if os.path.exists(CREDENTIALS_PATH):
        try:
            with open(CREDENTIALS_PATH, "r", encoding="utf-8") as file:
                data = json.load(file)
                username = data.get("username") or DEFAULT_USERNAME
                password = data.get("password") or DEFAULT_PASSWORD
                return {"username": username, "password": password}
        except Exception:
            pass
    return {"username": DEFAULT_USERNAME, "password": DEFAULT_PASSWORD}


def save_credentials(username: str, password: str) -> None:
    with open(CREDENTIALS_PATH, "w", encoding="utf-8") as file:
        json.dump({"username": username, "password": password}, file, ensure_ascii=False)


def allowed_file(filename: str) -> bool:
    _, ext = os.path.splitext(filename.lower())
    return ext in ALLOWED_EXTENSIONS


def login_required(view_func):
    def wrapped(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    wrapped.__name__ = view_func.__name__
    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        credentials = load_credentials()
        if username == credentials["username"] and password == credentials["password"]:
            session.permanent = True
            session["logged_in"] = True
            return redirect(url_for("index"))
        flash("IDまたはパスワードが正しくありません。", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    credentials = load_credentials()
    if request.method == "POST":
        current_password = request.form.get("current_password", "").strip()
        new_password = request.form.get("new_password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        if current_password != credentials["password"]:
            flash("現在のパスワードが正しくありません。", "error")
            return redirect(url_for("settings"))

        if not new_password:
            flash("新しいパスワードを入力してください。", "error")
            return redirect(url_for("settings"))

        if new_password != confirm_password:
            flash("新しいパスワードが一致しません。", "error")
            return redirect(url_for("settings"))

        save_credentials(credentials["username"], new_password)
        flash("パスワードを更新しました。", "success")
        return redirect(url_for("settings"))

    return render_template("settings.html", username=credentials["username"])


MAX_FILES = 100


def process_image(file_stream, quality, target_width, target_dpi, output_format):
    """1枚の画像を処理してバイト列と拡張子を返す。"""
    image = Image.open(file_stream)

    if target_width:
        orig_w, orig_h = image.size
        ratio = target_width / orig_w
        new_size = (target_width, int(orig_h * ratio))
        image = image.resize(new_size, Image.LANCZOS)

    if output_format in ("jpeg", "webp"):
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
    elif output_format != "png":
        output_format = "jpeg"
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")

    output = io.BytesIO()
    save_kwargs = {}
    if target_dpi:
        save_kwargs["dpi"] = (target_dpi, target_dpi)

    if output_format == "jpeg":
        save_kwargs.update({"format": "JPEG", "quality": quality, "optimize": True})
        extension = ".jpg"
    elif output_format == "webp":
        save_kwargs.update({"format": "WEBP", "quality": quality, "method": 6})
        extension = ".webp"
    else:
        compress_level = int(round((100 - quality) / 100 * 9))
        save_kwargs.update({"format": "PNG", "optimize": True, "compress_level": compress_level})
        extension = ".png"

    image.save(output, **save_kwargs)
    output.seek(0)
    return output, extension


@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "POST":
        files = request.files.getlist("images")
        files = [f for f in files if f.filename]

        if not files:
            flash("画像ファイルが選択されていません。", "error")
            return redirect(url_for("index"))

        if len(files) > MAX_FILES:
            flash(f"一度にアップロードできるのは最大{MAX_FILES}ファイルです。", "error")
            return redirect(url_for("index"))

        quality = int(request.form.get("quality", 80))
        quality = max(10, min(95, quality))

        width = request.form.get("width", "").strip()
        dpi = request.form.get("dpi", "").strip()
        output_format = request.form.get("output_format", "jpeg").lower()

        target_width = int(width) if width.isdigit() and int(width) > 0 else None
        target_dpi = int(dpi) if dpi.isdigit() and int(dpi) > 0 else None

        # 各ファイルをバリデーション
        for f in files:
            if not allowed_file(f.filename):
                flash(f"対応していないファイル形式です: {f.filename}", "error")
                return redirect(url_for("index"))

        # 1ファイルの場合は直接ダウンロード
        if len(files) == 1:
            f = files[0]
            try:
                output, extension = process_image(
                    f.stream, quality, target_width, target_dpi, output_format
                )
            except Exception:
                flash("画像の読み込みに失敗しました。", "error")
                return redirect(url_for("index"))

            base_name, _ = os.path.splitext(f.filename)
            download_name = f"{base_name}{extension}"
            return send_file(
                output,
                as_attachment=True,
                download_name=download_name,
                mimetype=f"image/{output_format}",
            )

        # 複数ファイルの場合はZIPでダウンロード
        zip_buffer = io.BytesIO()
        used_names = {}
        errors = []

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                try:
                    output, extension = process_image(
                        f.stream, quality, target_width, target_dpi, output_format
                    )
                except Exception:
                    errors.append(f.filename)
                    continue

                base_name, _ = os.path.splitext(f.filename)
                name = f"{base_name}{extension}"

                # 同名ファイルの重複回避
                if name in used_names:
                    used_names[name] += 1
                    name = f"{base_name}_{used_names[name]}{extension}"
                else:
                    used_names[name] = 0

                zf.writestr(name, output.read())

        if errors:
            flash(f"一部の画像を処理できませんでした: {', '.join(errors)}", "error")

        zip_buffer.seek(0)
        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name="images.zip",
            mimetype="application/zip",
        )

    return render_template("index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
