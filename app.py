
from flask import Flask, request, send_file, render_template, Response
from PIL import Image, ImageOps, ImageDraw
from werkzeug.utils import secure_filename
import os, io

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024
os.makedirs('static/uploads', exist_ok=True)

ALLOWED = {'.jpg', '.jpeg', '.jfif', '.png', '.webp'}
SITE_URL = 'https://smartpdf-3qpk.onrender.com'


# Google Search Console Sitemap
@app.route('/sitemap.xml')
def sitemap():
    pages = [
        ('/', '1.0'),
        ('/convert-page', '0.9'),
        ('/compress', '0.9'),
        ('/passport', '0.9'),
        ('/enhancer', '0.9'),
    ]

    xml = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    ]

    for path, priority in pages:
        xml.append(
            f'<url><loc>{SITE_URL}{path}</loc>'
            f'<changefreq>monthly</changefreq>'
            f'<priority>{priority}</priority></url>'
        )

    xml.append('</urlset>')
    return Response('\n'.join(xml), mimetype='application/xml')


# Search engine crawler instructions
@app.route('/robots.txt')
def robots():
    content = (
        'User-agent: *\n'
        'Allow: /\n'
        f'Sitemap: {SITE_URL}/sitemap.xml\n'
    )
    return Response(content, mimetype='text/plain')


def open_image(file):
    ext = os.path.splitext(
        secure_filename(file.filename or '')
    )[1].lower()

    if ext not in ALLOWED:
        raise ValueError('Please use a JPG, PNG, or WEBP image.')

    im = Image.open(file.stream)
    im = ImageOps.exif_transpose(im)
    im.load()
    return im


@app.errorhandler(413)
def too_large(_):
    return 'File is too large. Please upload a file under 20 MB.', 413


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/convert-page')
def convert_page():
    return render_template('convert.html')


@app.route('/convert', methods=['POST'])
def convert():
    files = request.files.getlist('images')

    if not files or not any(f.filename for f in files):
        return 'Please select at least one image.', 400

    images = []

    try:
        for f in files:
            if f.filename:
                with open_image(f) as im:
                    images.append(im.convert('RGB'))

        if not images:
            return 'Please select at least one valid image.', 400

        out = io.BytesIO()
        images[0].save(
            out,
            format='PDF',
            save_all=True,
            append_images=images[1:]
        )
        out.seek(0)

        return send_file(
            out,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='smartpdf-converted.pdf'
        )

    except Exception as e:
        return (
            str(e) if isinstance(e, ValueError)
            else 'Unable to convert selected images.'
        ), 400

    finally:
        for im in images:
            im.close()


@app.route('/compress')
def compressor():
    return render_template('compress.html')


@app.route('/compress-image', methods=['POST'])
def compress_image():
    f = request.files.get('image')

    if not f or not f.filename:
        return 'Please select an image.', 400

    try:
        q = max(10, min(95, int(request.form.get('quality', 60))))

        with open_image(f) as original:
            im = original.copy()

        if im.mode in ('RGBA', 'LA') or (
            im.mode == 'P' and 'transparency' in im.info
        ):
            rgba = im.convert('RGBA')
            bg = Image.new('RGB', rgba.size, 'white')
            bg.paste(rgba, mask=rgba.getchannel('A'))
            rgba.close()
            im.close()
            im = bg
        else:
            converted = im.convert('RGB')
            im.close()
            im = converted

        out = io.BytesIO()
        im.save(out, format='JPEG', quality=q, optimize=True)
        im.close()
        out.seek(0)

        return send_file(
            out,
            mimetype='image/jpeg',
            as_attachment=True,
            download_name='compressed-image.jpg'
        )

    except Exception as e:
        return (
            str(e) if isinstance(e, ValueError)
            else 'Unable to compress this image.'
        ), 400


@app.route('/passport')
def passport():
    return render_template('passport.html')


@app.route('/passport-pdf', methods=['POST'])
def passport_pdf():
    f = request.files.get('image')

    if not f or not f.filename:
        return 'Please upload a photo.', 400

    try:
        with open_image(f) as original:
            im = original.convert('RGB')

        wmm = float(request.form.get('width_mm', 35))
        hmm = float(request.form.get('height_mm', 45))
        copies = int(request.form.get('copies', 8))
        paper = request.form.get('paper', '4x6')

        if not (15 <= wmm <= 100 and 15 <= hmm <= 100):
            return 'Photo dimensions must be between 15 and 100 mm.', 400

        if copies not in {1, 4, 8, 10, 12, 16, 20}:
            return 'Choose a supported number of copies.', 400

        if paper not in {'a4', '4x6'}:
            return 'Choose A4 or 4×6 inch paper.', 400

        dpi = 300
        pw = round(wmm / 25.4 * dpi)
        ph = round(hmm / 25.4 * dpi)

        if paper == 'a4':
            sw = round(210 / 25.4 * dpi)
            sh = round(297 / 25.4 * dpi)
        else:
            sw, sh = 4 * dpi, 6 * dpi

        photo = ImageOps.fit(
            im,
            (pw, ph),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.35)
        )
        im.close()

        margin = round(3 / 25.4 * dpi)
        gap = round(3 / 25.4 * dpi)

        cols = max(1, (sw - 2 * margin + gap) // (pw + gap))
        rows = max(1, (sh - 2 * margin + gap) // (ph + gap))
        perpage = cols * rows

        pages = []
        remaining = copies

        while remaining > 0:
            page = Image.new('RGB', (sw, sh), 'white')
            draw = ImageDraw.Draw(page)
            count = min(remaining, perpage)

            for i in range(count):
                x = margin + (i % cols) * (pw + gap)
                y = margin + (i // cols) * (ph + gap)
                page.paste(photo, (x, y))
                draw.rectangle(
                    (x, y, x + pw - 1, y + ph - 1),
                    outline=(205, 213, 225),
                    width=2
                )

            pages.append(page)
            remaining -= count

        out = io.BytesIO()
        pages[0].save(
            out,
            format='PDF',
            save_all=True,
            append_images=pages[1:],
            resolution=dpi
        )
        out.seek(0)
        photo.close()

        for page in pages:
            page.close()

        return send_file(
            out,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='smartpdf-photo-sheet.pdf'
        )

    except Exception as e:
        return (
            str(e) if isinstance(e, ValueError)
            else 'Unable to create the photo sheet. Check the image and settings.'
        ), 400


@app.route('/enhancer')
def enhancer():
    return render_template('enhancer.html')


if __name__ == '__main__':
    app.run(debug=True)
