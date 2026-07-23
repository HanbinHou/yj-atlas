"""
YJ Atlas 管理后台 — 爬虫内容导入 / 手动录入 / 图片处理 / 一键发布
"""
import shutil
import subprocess
import sys
from pathlib import Path
from datetime import datetime

import yaml
from flask import Flask, request, jsonify, render_template, send_from_directory

# ---- paths ----
BASE_DIR = Path(__file__).resolve().parent.parent
CONTENT_DIR = BASE_DIR / "src" / "content"
PUBLIC_IMG = BASE_DIR / "public" / "images"
CASES_DIR = CONTENT_DIR / "cases"
MATERIALS_DIR = CONTENT_DIR / "materials"
BOOKS_DIR = CONTENT_DIR / "books"

CASES_DIR.mkdir(parents=True, exist_ok=True)
MATERIALS_DIR.mkdir(parents=True, exist_ok=True)
BOOKS_DIR.mkdir(parents=True, exist_ok=True)
(PUBLIC_IMG / "cases").mkdir(parents=True, exist_ok=True)
(PUBLIC_IMG / "materials").mkdir(parents=True, exist_ok=True)
(PUBLIC_IMG / "books").mkdir(parents=True, exist_ok=True)

app = Flask(__name__)

# ─── helpers ───────────────────────────────────────────

def read_frontmatter(path: Path) -> dict:
    """Read YAML frontmatter + body from a markdown file."""
    if not path.exists():
        return {"frontmatter": {}, "body": ""}
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            fm = yaml.safe_load(parts[1]) or {}
            return {"frontmatter": fm, "body": parts[2].strip()}
    return {"frontmatter": {}, "body": text.strip()}

def slugify(text: str) -> str:
    """Simple slug: lowercase, replace spaces/special chars with hyphens."""
    import re
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text[:80]

def list_content(content_type: str) -> list[dict]:
    """List all content files of a given type with their frontmatter."""
    dir_map = {"cases": CASES_DIR, "materials": MATERIALS_DIR, "books": BOOKS_DIR}
    target = dir_map.get(content_type)
    if not target:
        return []
    items = []
    for md_file in sorted(target.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
        data = read_frontmatter(md_file)
        data["filename"] = md_file.name
        data["slug"] = md_file.stem
        items.append(data)
    return items

# ─── routes ────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/import")
def import_page():
    return render_template("import.html")

@app.route("/cases")
@app.route("/materials")
@app.route("/books")
def content_pages():
    path = request.path.strip("/")
    labels = {"cases": ("🏛️ 案例管理", "案例"), "materials": ("🧱 材料管理", "材料"), "books": ("📚 书目管理", "书目")}
    title, label = labels.get(path, ("管理", ""))
    return render_template("content_list.html", title=title, label=label, type=path)

@app.route("/api/thumbnail")
def api_thumbnail():
    """Serve a thumbnail from a file path (query param)."""
    path = request.args.get("path", "")
    if not path or not Path(path).exists():
        return "", 404
    return send_from_directory(Path(path).parent, Path(path).name)

@app.route("/api/content/<content_type>")
def api_list(content_type):
    return jsonify(list_content(content_type))

@app.route("/api/content/<content_type>/<filename>", methods=["GET", "DELETE"])
def api_content_item(content_type, filename):
    dir_map = {"cases": CASES_DIR, "materials": MATERIALS_DIR, "books": BOOKS_DIR}
    target = dir_map.get(content_type)
    if not target:
        return jsonify({"error": "invalid type"}), 400
    path = target / filename
    if request.method == "DELETE":
        if path.exists():
            path.unlink()
            return jsonify({"ok": True})
        return jsonify({"error": "not found"}), 404
    data = read_frontmatter(path)
    data["filename"] = filename
    data["slug"] = path.stem
    return jsonify(data)

@app.route("/api/save/<content_type>", methods=["POST"])
def api_save(content_type):
    """Save content from the form editor."""
    payload = request.json
    slug = slugify(payload.get("title", "untitled"))
    frontmatter = payload.get("frontmatter", {})
    body = payload.get("body", "")
    filename = f"{slug}.md"

    dir_map = {"cases": CASES_DIR, "materials": MATERIALS_DIR, "books": BOOKS_DIR}
    target = dir_map.get(content_type)
    if not target:
        return jsonify({"error": "invalid type"}), 400

    # Build markdown
    lines = ["---"]
    lines.append(yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False).strip())
    lines.append("---")
    lines.append("")
    lines.append(body)
    (target / filename).write_text("\n".join(lines), encoding="utf-8")
    return jsonify({"ok": True, "slug": slug, "filename": filename})

@app.route("/api/scan-crawler", methods=["POST"])
def api_scan_crawler():
    """Scan a date folder from the crawler and return available projects."""
    payload = request.json
    folder = payload.get("folder", "")
    if not folder:
        return jsonify({"error": "no folder"}), 400

    base = Path(folder)
    projects = []
    for subdir in sorted(base.iterdir()):
        if not subdir.is_dir() or subdir.name.startswith("_"):
            continue
        md_file = subdir / "content.md"
        if not md_file.exists():
            continue
        data = read_frontmatter(md_file)
        # Count images
        images = sorted([f.name for f in subdir.glob("*.jpg")])
        projects.append({
            "folder": subdir.name,
            "path": str(subdir),
            "frontmatter": data.get("frontmatter", {}),
            "body": data.get("body", ""),
            "images": images,
            "image_count": len(images),
        })
    return jsonify(projects)

@app.route("/api/import-case", methods=["POST"])
def api_import_case():
    """Import one project from crawler → generate case .md + copy images."""
    payload = request.json
    source_folder = Path(payload["source_folder"])
    title = payload.get("title", source_folder.name)
    architect = payload.get("architect", "")
    case_type = payload.get("type", "")
    materials = payload.get("materials", [])
    location = payload.get("location", "")
    year = payload.get("year", 2025)
    tags = payload.get("tags", [])
    description = payload.get("description", "")
    body = payload.get("body", "")
    include_images = payload.get("include_images", True)

    slug = slugify(title)
    dest_md = CASES_DIR / f"{slug}.md"

    # Build frontmatter
    fm = {
        "title": title,
        "architect": architect,
        "year": year,
        "type": case_type,
        "materials": materials,
        "location": location,
        "tags": tags,
        "description": description,
        "images": [],
    }

    # Copy images
    img_dest = PUBLIC_IMG / "cases" / slug
    if include_images and source_folder.exists():
        img_dest.mkdir(parents=True, exist_ok=True)
        img_paths = []
        for f in sorted(source_folder.glob("*.jpg")):
            dest_file = img_dest / f.name
            # Resize if > 2MB
            try:
                from PIL import Image
                size_mb = f.stat().st_size / (1024 * 1024)
                if size_mb > 2:
                    img = Image.open(f)
                    img = img.convert("RGB")
                    max_dim = 2000
                    if max(img.size) > max_dim:
                        ratio = max_dim / max(img.size)
                        new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                        img = img.resize(new_size, Image.LANCZOS)
                    dest_file = img_dest / f"{f.stem}.webp"
                    img.save(dest_file, "WEBP", quality=85)
                else:
                    shutil.copy2(f, dest_file)
            except Exception:
                shutil.copy2(f, dest_file)
            img_paths.append(f"/images/cases/{slug}/{dest_file.name}")
        fm["images"] = img_paths

    # Write markdown
    lines = ["---"]
    lines.append(yaml.dump(fm, allow_unicode=True, default_flow_style=False).strip())
    lines.append("---")
    lines.append("")
    lines.append(body)
    dest_md.write_text("\n".join(lines), encoding="utf-8")

    return jsonify({"ok": True, "slug": slug, "images_copied": len(fm["images"])})

@app.route("/api/publish", methods=["POST"])
def api_publish():
    """Build site + deploy to Netlify + git backup."""
    steps = []
    try:
        # 1. Build
        steps.append({"step": "build", "status": "running"})
        result = subprocess.run(
            ["npm", "run", "build"],
            cwd=BASE_DIR, capture_output=True, text=True, timeout=120,
            shell=True,
        )
        steps[-1]["status"] = "ok" if result.returncode == 0 else "error"
        steps[-1]["output"] = result.stdout[-500:] + result.stderr[-500:]

        # 2. Deploy
        steps.append({"step": "deploy", "status": "running"})
        result = subprocess.run(
            ["npx", "netlify", "deploy", "--prod", "--dir=dist"],
            cwd=BASE_DIR, capture_output=True, text=True, timeout=180,
            shell=True,
        )
        steps[-1]["status"] = "ok" if result.returncode == 0 else "error"
        steps[-1]["output"] = result.stdout[-500:] + result.stderr[-500:]

        # Extract deploy URL
        deploy_url = ""
        for line in result.stdout.split("\n"):
            if "Production URL:" in line or "production URL" in line.lower():
                deploy_url = line.split()[-1].strip()
        if not deploy_url:
            deploy_url = "https://yjatlas.com"
        steps[-1]["url"] = deploy_url

        # 3. Git backup
        steps.append({"step": "git", "status": "running"})
        subprocess.run(["git", "add", "-A"], cwd=BASE_DIR, capture_output=True, shell=True)
        result = subprocess.run(
            ["git", "commit", "-m", f"Publish: {datetime.now().strftime('%Y-%m-%d %H:%M')}"],
            cwd=BASE_DIR, capture_output=True, text=True, timeout=30,
            shell=True,
        )
        subprocess.run(["git", "push"], cwd=BASE_DIR, capture_output=True, timeout=60, shell=True)
        steps[-1]["status"] = "ok"
        steps[-1]["output"] = result.stdout[:300]

    except subprocess.TimeoutExpired as e:
        steps[-1]["status"] = "timeout"
        steps[-1]["output"] = str(e)
    except Exception as e:
        steps[-1]["status"] = "error"
        steps[-1]["output"] = str(e)

    return jsonify({"steps": steps})

@app.route("/api/preview", methods=["POST"])
def api_preview():
    """Start dev server and return URL."""
    # Check if dev server is already running
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    running = sock.connect_ex(('localhost', 4321)) == 0
    sock.close()
    if running:
        return jsonify({"url": "http://localhost:4321", "already_running": True})

    # Start in background
    subprocess.Popen(
        ["npx", "astro", "dev", "--host", "0.0.0.0"],
        cwd=BASE_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        shell=True,
    )
    return jsonify({"url": "http://localhost:4321", "already_running": False})

@app.route("/api/preview-stop", methods=["POST"])
def api_preview_stop():
    subprocess.run(["npx", "astro", "dev", "stop"], cwd=BASE_DIR, capture_output=True, shell=True)
    return jsonify({"ok": True})

@app.route("/api/open-folder/<path:subpath>")
def api_open_folder(subpath):
    """Open a folder in Explorer."""
    target = BASE_DIR / subpath
    if target.exists():
        subprocess.Popen(["explorer", str(target)], shell=True)
    return jsonify({"ok": True})


if __name__ == "__main__":
    print(f"\n  YJ Atlas 管理后台")
    print(f"  http://localhost:5000\n")
    app.run(host="127.0.0.1", port=5000, debug=False)
