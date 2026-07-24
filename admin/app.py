"""
YJ Atlas 管理后台 — 爬虫内容导入 / 手动录入 / 图片处理 / 一键发布
"""
import shutil
import re
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

@app.route("/research")
def research_page():
    return render_template("research.html")

@app.route("/cases")
@app.route("/materials")
@app.route("/books")
def content_pages():
    path = request.path.strip("/")
    labels = {"cases": ("🏛️ 案例管理", "案例"), "materials": ("🧱 材料管理", "材料"), "books": ("📚 书目管理", "书目")}
    title, label = labels.get(path, ("管理", ""))
    items = list_content(path)
    return render_template("content_list.html", title=title, label=label, type=path, items=items)

@app.route("/api/reorder-images", methods=["POST"])
def api_reorder_images():
    """Reorder images in a case's frontmatter."""
    data = request.json
    filename = data.get("filename")
    content_type = data.get("type", "cases")
    new_order = data.get("images", [])

    dir_map = {"cases": CASES_DIR, "materials": MATERIALS_DIR}
    target = dir_map.get(content_type)
    if not target:
        return jsonify({"error": "invalid type"}), 400

    md_file = target / filename
    if not md_file.exists():
        return jsonify({"error": "file not found"}), 404

    text = md_file.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) < 3:
        return jsonify({"error": "invalid format"}), 400

    fm = yaml.safe_load(parts[1]) or {}
    fm["images"] = new_order

    lines = ["---"]
    lines.append(yaml.dump(fm, allow_unicode=True, default_flow_style=False).strip())
    lines.append("---")
    lines.append(parts[2].strip() if len(parts) > 2 else "")
    md_file.write_text("\n".join(lines), encoding="utf-8")
    return jsonify({"ok": True})

@app.route("/site-images/<path:subpath>")
def serve_site_images(subpath):
    """Proxy images from the Astro public/images/ directory."""
    return send_from_directory(BASE_DIR / "public" / "images", subpath)

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

@app.route("/api/edit/<content_type>/<filename>", methods=["POST"])
def api_edit(content_type, filename):
    """Update an existing content file in place."""
    payload = request.json
    frontmatter = payload.get("frontmatter", {})
    body = payload.get("body", "")

    dir_map = {"cases": CASES_DIR, "materials": MATERIALS_DIR, "books": BOOKS_DIR}
    target = dir_map.get(content_type)
    if not target:
        return jsonify({"error": "invalid type"}), 400

    md_file = target / filename
    if not md_file.exists():
        return jsonify({"error": "file not found"}), 404

    lines = ["---"]
    lines.append(yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False).strip())
    lines.append("---")
    lines.append("")
    lines.append(body)
    md_file.write_text("\n".join(lines), encoding="utf-8")
    return jsonify({"ok": True})

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
    """Import one project from crawler → format via DeepSeek → copy images."""
    from researcher import get_api_key, _deepseek_chat, parse_response, build_markdown, _slugify, RESEARCH_PROMPT

    payload = request.json
    source_folder = Path(payload["source_folder"])
    title = payload.get("title", source_folder.name)
    architect = payload.get("architect", "")
    include_images = payload.get("include_images", True)
    crawler_body = payload.get("body", "")

    # Use DeepSeek to reformat crawler content into standard template
    api_key = get_api_key()
    if api_key and crawler_body:
        try:
            prompt = RESEARCH_PROMPT.format(project_name=f"{architect} - {title}")
            text = _deepseek_chat(
                system_prompt="你是一位建筑学教授。将以下建筑项目资料整理成标准格式。使用简体中文。",
                user_message=f"以下是爬虫抓取的建筑项目原始资料，请整理成标准格式：\n\n{crawler_body[:4000]}\n\n{prompt}",
            )
            data = parse_response(text)
            slug = _slugify(data.get("title") or title)
            if not slug or slug == "untitled":
                slug = _slugify(title)
            md_body, fm = build_markdown(data)
            body_final = md_body.split("---\n", 2)[-1] if "---\n" in md_body else md_body
        except Exception:
            slug = slugify(title)
            fm = {
                "title": title, "architect": architect, "year": payload.get("year", 2025),
                "type": payload.get("type", ""), "materials": payload.get("materials", []),
                "location": payload.get("location", ""), "tags": payload.get("tags", []),
                "description": payload.get("description", ""), "images": [],
            }
            body_final = crawler_body
    else:
        slug = slugify(title)
        fm = {
            "title": title, "architect": architect, "year": payload.get("year", 2025),
            "type": payload.get("type", ""), "materials": payload.get("materials", []),
            "location": payload.get("location", ""), "tags": payload.get("tags", []),
            "description": payload.get("description", ""), "images": [],
        }
        body_final = crawler_body

    dest_md = CASES_DIR / f"{slug}.md"

    # Copy images
    img_dest = PUBLIC_IMG / "cases" / slug
    img_paths = []
    if include_images and source_folder.exists():
        img_dest.mkdir(parents=True, exist_ok=True)
        for f in sorted(source_folder.glob("*.jpg")):
            dest_file = img_dest / f.name
            try:
                from PIL import Image
                size_mb = f.stat().st_size / (1024 * 1024)
                if size_mb > 2:
                    img = Image.open(f).convert("RGB")
                    max_dim = 2000
                    if max(img.size) > max_dim:
                        ratio = max_dim / max(img.size)
                        img = img.resize((int(img.size[0]*ratio), int(img.size[1]*ratio)), Image.LANCZOS)
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
    lines.append(body_final)
    dest_md.write_text("\n".join(lines), encoding="utf-8")

    return jsonify({"ok": True, "slug": slug, "images_copied": len(img_paths)})

@app.route("/api/publish", methods=["POST"])
def api_publish():
    """Build site + deploy to Netlify + git backup."""
    steps = []
    try:
        # 1. Build
        steps.append({"step": "build", "status": "running"})
        result = subprocess.run(
            "npm run build",
            cwd=str(BASE_DIR), capture_output=True, text=True, timeout=120,
            shell=True, encoding="utf-8", errors="replace",
        )
        steps[-1]["status"] = "ok" if result.returncode == 0 else "error"
        steps[-1]["output"] = result.stdout[-500:] + result.stderr[-500:]

        if result.returncode != 0:
            return jsonify({"steps": steps, "error": "build failed"})

        # 2. Deploy
        steps.append({"step": "deploy", "status": "running"})
        result = subprocess.run(
            "npx netlify deploy --prod --dir=dist",
            cwd=str(BASE_DIR), capture_output=True, text=True, timeout=180,
            shell=True, encoding="utf-8", errors="replace",
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
        subprocess.run("git add -A", cwd=str(BASE_DIR), capture_output=True, shell=True)
        result = subprocess.run(
            f'git commit -m "Publish: {datetime.now().strftime("%Y-%m-%d %H:%M")}"',
            cwd=str(BASE_DIR), capture_output=True, text=True, timeout=30,
            shell=True, encoding="utf-8", errors="replace",
        )
        subprocess.run("git push", cwd=str(BASE_DIR), capture_output=True, timeout=60, shell=True)
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


@app.route("/api/import-enriched", methods=["POST"])
def api_import_enriched():
    """Import from crawler with AI enrichment to match research format."""
    from researcher import get_api_key, _deepseek_chat, _ddgs_search, build_markdown, _slugify

    payload = request.json
    source_folder = Path(payload["source_folder"])
    architect = payload.get("architect", source_folder.name)
    title = payload.get("title", source_folder.name)

    api_key = get_api_key()
    if not api_key:
        return jsonify({"error": "请先配置 DeepSeek API Key"}), 400

    # Step 1: Read crawler content as context
    md_file = source_folder / "content.md"
    crawler_data = read_frontmatter(md_file) if md_file.exists() else {"body": ""}
    crawler_body = crawler_data.get("body", "")

    # Step 2: Web search for more info
    search_query = f"{architect} {title} architecture"
    web_results = _ddgs_search(search_query, count=5)
    sources_text = "\n\n".join([
        f"来源: {r.get('url','')}\n{r.get('body','')[:2000]}"
        for r in web_results[:4]
    ])

    # Step 3: DeepSeek structured extraction
    from researcher import RESEARCH_PROMPT
    prompt = RESEARCH_PROMPT.format(project_name=f"{architect} - {title}")

    system_prompt = "你是一位建筑学教授。基于提供的资料生成结构化建筑案例。回复使用简体中文。务必覆盖所有要求的字段。"

    user_msg = f"""以下是爬虫抓取的原始内容和网络搜索结果，请整合生成标准的建筑案例分析：

=== 爬虫原文 ===
{crawler_body[:3000]}

=== 网络搜索补充 ===
{sources_text}

{prompt}"""

    text = _deepseek_chat(system_prompt, user_msg)

    # Step 4: Parse and build MD
    from researcher import parse_response
    data = parse_response(text)
    slug = _slugify(data.get("title") or title)
    if not slug or slug == "untitled":
        slug = _slugify(title)

    md_text, fm = build_markdown(data)

    # Step 5: Copy crawler images (keeping originals)
    img_dest = PUBLIC_IMG / "cases" / slug
    img_paths = []
    if source_folder.exists():
        img_dest.mkdir(parents=True, exist_ok=True)
        for f in sorted(source_folder.glob("*.jpg")):
            dest_file = img_dest / f.name
            try:
                from PIL import Image
                size_mb = f.stat().st_size / (1024 * 1024)
                if size_mb > 2:
                    img = Image.open(f).convert("RGB")
                    max_dim = 2000
                    if max(img.size) > max_dim:
                        ratio = max_dim / max(img.size)
                        img = img.resize((int(img.size[0]*ratio), int(img.size[1]*ratio)), Image.LANCZOS)
                    dest_file = img_dest / f"{f.stem}.webp"
                    img.save(dest_file, "WEBP", quality=85)
                else:
                    shutil.copy2(f, dest_file)
            except Exception:
                shutil.copy2(f, dest_file)
            img_paths.append(f"/images/cases/{slug}/{dest_file.name}")

    fm["images"] = img_paths

    # Save MD
    import yaml
    lines = ["---"]
    lines.append(yaml.dump(fm, allow_unicode=True, default_flow_style=False).strip())
    lines.append("---")
    lines.append("")
    lines.append(md_text.split("---\n", 2)[-1] if "---\n" in md_text else md_text)
    (CASES_DIR / f"{slug}.md").write_text("\n".join(lines), encoding="utf-8")

    return jsonify({
        "ok": True, "slug": slug,
        "title": data.get("title", ""),
        "architect": data.get("architect", ""),
        "type": data.get("type", ""),
        "location": data.get("location", ""),
        "images_count": len(img_paths),
        "raw": text,
    })

# ─── AI Research ──────────────────────────────────────

@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    from researcher import get_api_key, set_api_key
    if request.method == "POST":
        key = request.json.get("api_key", "")
        set_api_key(key)
        return jsonify({"ok": True, "has_key": bool(key)})
    return jsonify({"has_key": bool(get_api_key())})

@app.route("/api/research-project", methods=["POST"])
def api_research_project():
    """AI research: search web for project info + images, generate MD."""
    from researcher import get_api_key, research_project, build_markdown, search_images, download_images
    import shutil

    project_name = request.json.get("project_name", "").strip()
    if not project_name:
        return jsonify({"error": "请输入项目名称"}), 400
    if not get_api_key():
        return jsonify({"error": "请先在设置页面配置 DeepSeek API Key"}), 400

    # Step 1: Research with Claude
    data = research_project(project_name)
    if "error" in data:
        return jsonify(data), 500

    # Step 2: Build markdown
    md_text, fm = build_markdown(data)

    # Step 3: Search & download images
    image_queries = data.get("image_queries", "")
    queries = [q.strip() for q in image_queries.split("\n") if q.strip()]
    if not queries:
        queries = [f"{data.get('architect','')} {data.get('title','')} architecture"]

    all_images = []
    for q in queries[:3]:
        imgs = search_images(q, count=3)
        all_images.extend(imgs)
        if len(all_images) >= 8:
            break

    slug = data.get("slug", "")
    if not slug or slug == "untitled":
        slug = re.sub(r'[^\w一-鿿-]', '', project_name)[:60] or "unnamed"
    img_paths = download_images(all_images[:8], slug)

    # Update frontmatter with image paths
    fm["images"] = img_paths
    import yaml
    lines = ["---"]
    lines.append(yaml.dump(fm, allow_unicode=True, default_flow_style=False).strip())
    lines.append("---")
    lines.append("")
    lines.append(md_text.split("---\n", 2)[-1] if "---\n" in md_text else md_text)

    # Save MD file
    md_file = Path(CASES_DIR) / f"{slug}.md"
    md_file.write_text("\n".join(lines), encoding="utf-8")

    return jsonify({
        "ok": True,
        "slug": slug,
        "title": data.get("title", ""),
        "architect": data.get("architect", ""),
        "year": data.get("year", ""),
        "type": data.get("type", ""),
        "location": data.get("location", ""),
        "description": data.get("description", ""),
        "tags": data.get("tags", ""),
        "materials": data.get("materials", ""),
        "images_downloaded": len(img_paths),
        "image_paths": img_paths,
        "md_preview": md_text[:500],
        "raw": data.get("raw", ""),
    })


if __name__ == "__main__":
    print(f"\n  YJ Atlas 管理后台")
    print(f"  http://localhost:5000\n")
    app.run(host="127.0.0.1", port=5000, debug=False)
