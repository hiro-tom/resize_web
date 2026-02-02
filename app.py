import io
import json
import os
from datetime import timedelta
from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
from werkzeug.utils import secure_filename
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


@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "POST":
        if "image" not in request.files:
            flash("画像ファイルが選択されていません。", "error")
            return redirect(url_for("index"))

        file = request.files["image"]
        if file.filename == "" or not allowed_file(file.filename):
            flash("対応していないファイル形式です。", "error")
            return redirect(url_for("index"))

        filename = secure_filename(file.filename)
        try:
            image = Image.open(file.stream)
        except Exception:
            flash("画像の読み込みに失敗しました。", "error")
            return redirect(url_for("index"))

        quality = int(request.form.get("quality", 80))
        quality = max(10, min(95, quality))

        width = request.form.get("width", "").strip()
        height = request.form.get("height", "").strip()
        dpi = request.form.get("dpi", "").strip()
        output_format = request.form.get("output_format", "jpeg").lower()

        target_width = int(width) if width.isdigit() and int(width) > 0 else None
        target_height = int(height) if height.isdigit() and int(height) > 0 else None
        target_dpi = int(dpi) if dpi.isdigit() and int(dpi) > 0 else None

        if target_width or target_height:
            orig_w, orig_h = image.size
            if target_width and target_height:
                new_size = (target_width, target_height)
            elif target_width:
                ratio = target_width / orig_w
                new_size = (target_width, int(orig_h * ratio))
            else:
                ratio = target_height / orig_h
                new_size = (int(orig_w * ratio), target_height)
            image = image.resize(new_size, Image.LANCZOS)

        if output_format == "jpeg":
            if image.mode in ("RGBA", "P"):
                image = image.convert("RGB")
        elif output_format == "webp":
            if image.mode in ("RGBA", "P"):
                image = image.convert("RGB")
        elif output_format == "png":
            output_format = "png"
        else:
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

        base_name, _ = os.path.splitext(filename)
        download_name = f"{base_name}_compressed{extension}"

        return send_file(
            output,
            as_attachment=True,
            download_name=download_name,
            mimetype=f"image/{output_format}",
        )

    return render_template("index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
