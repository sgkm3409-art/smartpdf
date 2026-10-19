
from flask import Flask, request, send_file, render_template
from PIL import Image
from werkzeug.utils import secure_filename
import os
import io

app = Flask(__name__)

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@app.route("/")
def home():
    return render_template("index.html")


# Image to PDF
@app.route("/convert", methods=["POST"])
def convert():
    files = request.files.getlist("images")

    if not files or files[0].filename == "":
        return "Please select at least one image.", 400

    images = []

    try:
        for file in files:
            image = Image.open(file).convert("RGB")
            images.append(image)

        pdf_path = os.path.join(UPLOAD_FOLDER, "converted.pdf")

        images[0].save(
            pdf_path,
            save_all=True,
            append_images=images[1:]
        )

        return send_file(
            pdf_path,
            as_attachment=True,
            download_name="converted.pdf"
        )

    except Exception:
        return "Unable to convert the selected images.", 400

    finally:
        for image in images:
            image.close()


# Image Compressor Page
@app.route("/compress")
def compressor():
    return render_template("compress.html")


# Compress Image and Download as JPG
@app.route("/compress-image", methods=["POST"])
def compress_image():
    file = request.files.get("image")

    if not file or not file.filename:
        return "Please select an image.", 400

    try:
        quality = int(request.form.get("quality", 60))
        quality = max(10, min(95, quality))

        with Image.open(file) as original:
            image = original.copy()

        # JPG does not support transparency.
        # Place transparent areas on a white background.
        if image.mode in ("RGBA", "LA") or (
            image.mode == "P" and "transparency" in image.info
        ):
            image = image.convert("RGBA")
            background = Image.new("RGB", image.size, "white")
            background.paste(image, mask=image.getchannel("A"))
            image.close()
            image = background
        else:
            image = image.convert("RGB")

        output = io.BytesIO()

        image.save(
            output,
            format="JPEG",
            quality=quality,
            optimize=True
        )
        image.close()

        output.seek(0)

        return send_file(
            output,
            mimetype="image/jpeg",
            as_attachment=True,
            download_name="compressed-image.jpg"
        )

    except Exception:
        return "Unable to compress this image. Please select a valid image.", 400


if __name__ == "__main__":
    app.run(debug=True)
