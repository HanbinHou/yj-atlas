"""
AI Research Module — 根据项目名称搜索建筑信息 + 图片，生成标准格式 Markdown
"""
import json
import re
import shutil
import time
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.parse import quote

from anthropic import Anthropic

BASE_DIR = Path(__file__).resolve().parent.parent
CONTENT_DIR = BASE_DIR / "src" / "content"
PUBLIC_IMG = BASE_DIR / "public" / "images"

# ── config ────────────────────────────────────────────

def get_api_key() -> str:
    """Read Anthropic API key from config file."""
    config_file = Path(__file__).parent / "api_key.txt"
    if config_file.exists():
        return config_file.read_text(encoding="utf-8").strip()
    return ""

def set_api_key(key: str):
    (Path(__file__).parent / "api_key.txt").write_text(key.strip(), encoding="utf-8")

# ── template ──────────────────────────────────────────

CASE_TEMPLATE = """## 基本信息

| 项目 | 内容 |
|------|------|
| **建筑师** | {architect} |
| **建造年份** | {year} |
| **建筑类型** | {type} |
| **主要材料** | {materials} |
| **所在地** | {location} |
| **结构形式** | {structure} |
| **建筑状态** | {status} |

## 历史背景

{history}

## 设计分析

{design_analysis}

## 材料与构造

{material_detail}

## 意义与影响

{significance}
"""

RESEARCH_PROMPT = """你是一位建筑学研究助手。请对以下建筑项目进行深入研究，并输出严格格式化的内容。

项目名称：{project_name}

请按以下结构输出。每个字段用一个标记行分隔，不要遗漏任何字段。

---TITLE---
[项目的中文名称，如果原名非中文则用"中文译名（外文原名）"格式]
---ARCHITECT---
[建筑师/事务所名称]
---YEAR---
[建造年份，只输出数字]
---TYPE---
[建筑类型：住宅/公共建筑/文化建筑/宗教建筑/办公建筑/教育建筑/科研建筑/商业建筑/景观建筑/工业建筑/其他]
---MATERIALS---
[主要材料列表，用中文逗号分隔，例如：钢筋混凝土, 玻璃, 石材]
---LOCATION---
[城市, 国家]
---TAGS---
[3-6个标签，用中文逗号分隔，至少包含风格流派、功能特征、空间特征各一个]
---DESCRIPTION---
[一句话概述，不超过80个汉字，突出核心特征]
---STRUCTURE---
[结构形式，例如：框架结构/剪力墙结构/壳体结构/悬索结构/拱结构/桁架结构/木结构/钢结构/膜结构/混合结构]
---STATUS---
[已建成/已拆除/未建成/改造中]
---HISTORY---
[项目的建造背景、委托方、社会历史语境，2-3段，每段2-3句话]
---DESIGN_ANALYSIS---
[从空间组织、流线、光线、形式语言等角度分析设计策略，3-4段]
---MATERIAL_DETAIL---
[详细说明主要材料的运用方式、构造逻辑、建筑表现，2-3段]
---SIGNIFICANCE---
[项目在建筑史上的地位、对后世的影响、学术评价，2-3段]
---IMAGE_QUERIES---
[用于搜索高质量建筑图片的英文关键词，每行一个，共5个。优先使用摄影师名字+建筑名组合，如"Fallingwater photographer Ezra Stoller"]"""


def research_project(project_name: str) -> dict:
    """Main entry: research a project and return structured data + image searches."""
    api_key = get_api_key()
    if not api_key:
        return {"error": "请先在设置页面配置 Anthropic API Key"}

    client = Anthropic(api_key=api_key)

    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=4096,
        system="你是一位建筑学教授，擅长研究建筑案例并输出结构化的学术内容。回复使用简体中文。务必覆盖所有要求的字段，不要省略。",
        messages=[{"role": "user", "content": RESEARCH_PROMPT.format(project_name=project_name)}],
    )

    text = response.content[0].text
    data = parse_response(text)

    # Generate slug from title
    data["slug"] = _slugify(data.get("title", project_name))
    data["raw"] = text
    return data


def parse_response(text: str) -> dict:
    """Parse the structured response into a dict."""
    fields = {
        "TITLE": "title", "ARCHITECT": "architect", "YEAR": "year",
        "TYPE": "type", "MATERIALS": "materials", "LOCATION": "location",
        "TAGS": "tags", "DESCRIPTION": "description", "STRUCTURE": "structure",
        "STATUS": "status", "HISTORY": "history",
        "DESIGN_ANALYSIS": "design_analysis", "MATERIAL_DETAIL": "material_detail",
        "SIGNIFICANCE": "significance", "IMAGE_QUERIES": "image_queries",
    }
    result = {}
    for marker, key in fields.items():
        pattern = rf'---{marker}---\s*\n(.*?)(?=\n---|\Z)'
        match = re.search(pattern, text, re.DOTALL)
        value = match.group(1).strip() if match else ""
        result[key] = value
    return result


def build_markdown(data: dict) -> str:
    """Generate the final .md file content from research data."""
    # Parse year
    year_str = data.get("year", "").strip()
    try:
        year = int(re.search(r'\d+', year_str).group())
    except Exception:
        year = 0

    # Parse materials to list
    materials_str = data.get("materials", "")
    materials_list = [m.strip() for m in re.split(r'[,，、/]', materials_str) if m.strip()]

    # Parse tags
    tags_str = data.get("tags", "")
    tags_list = [t.strip() for t in re.split(r'[,，、/]', tags_str) if t.strip()]

    # Build frontmatter
    fm = {
        "title": data.get("title", ""),
        "architect": data.get("architect", ""),
        "year": year,
        "type": data.get("type", ""),
        "materials": materials_list,
        "location": data.get("location", ""),
        "tags": tags_list,
        "description": data.get("description", ""),
        "images": [],
    }

    # Build body
    body = CASE_TEMPLATE.format(
        architect=data.get("architect", ""),
        year=year_str,
        type=data.get("type", ""),
        materials=materials_str,
        location=data.get("location", ""),
        structure=data.get("structure", ""),
        status=data.get("status", ""),
        history=data.get("history", ""),
        design_analysis=data.get("design_analysis", ""),
        material_detail=data.get("material_detail", ""),
        significance=data.get("significance", ""),
    )

    # Assemble
    import yaml
    lines = ["---"]
    lines.append(yaml.dump(fm, allow_unicode=True, default_flow_style=False).strip())
    lines.append("---")
    lines.append("")
    lines.append(body)

    return "\n".join(lines), fm


def search_images(query: str, count: int = 5) -> list[str]:
    """Search for high-quality architecture images using Wikimedia Commons API."""
    results = []
    try:
        # Wikimedia Commons API
        search_url = (
            f"https://commons.wikimedia.org/w/api.php"
            f"?action=query&list=search&srsearch={quote(query + ' architecture')}"
            f"&srnamespace=6&format=json&srlimit={count * 3}"
        )
        req = Request(search_url, headers={"User-Agent": "YJAtlas/1.0"})
        data = json.loads(urlopen(req, timeout=15).read())

        pages = [r["title"] for r in data.get("query", {}).get("search", [])]

        # Get image URLs
        for page_title in pages[:count * 2]:
            img_url = (
                f"https://commons.wikimedia.org/w/api.php"
                f"?action=query&titles={quote(page_title)}"
                f"&prop=imageinfo&iiprop=url|size&format=json"
            )
            img_data = json.loads(urlopen(Request(img_url, headers={"User-Agent": "YJAtlas/1.0"}), timeout=10).read())
            pages_info = img_data.get("query", {}).get("pages", {})
            for _pid, pinfo in pages_info.items():
                ii = pinfo.get("imageinfo", [])
                if ii:
                    size = ii[0].get("width", 0)
                    url = ii[0].get("url", "")
                    # Filter: prefer high-res (>1200px wide)
                    if size >= 800 and url:
                        results.append({"url": url, "width": size, "title": ii[0].get("descriptionurl", "")})
            if len(results) >= count:
                break

    except Exception as e:
        print(f"[image search error] {e}")

    # Sort by resolution (prefer larger)
    results.sort(key=lambda x: x["width"], reverse=True)
    return results[:count]


def download_images(image_urls: list[dict], slug: str) -> list[str]:
    """Download images to public/images/cases/{slug}/, return list of paths."""
    dest_dir = PUBLIC_IMG / "cases" / slug
    dest_dir.mkdir(parents=True, exist_ok=True)
    paths = []

    for i, img_info in enumerate(image_urls):
        url = img_info["url"]
        ext = ".jpg"
        if ".png" in url.lower():
            ext = ".png"
        elif ".webp" in url.lower():
            ext = ".webp"
        dest_file = dest_dir / f"{i + 1:02d}{ext}"

        try:
            req = Request(url, headers={"User-Agent": "YJAtlas/1.0"})
            with urlopen(req, timeout=30) as resp:
                dest_file.write_bytes(resp.read())
            paths.append(f"/images/cases/{slug}/{dest_file.name}")
            time.sleep(0.3)  # Rate limit
        except Exception as e:
            print(f"[download error] {url}: {e}")

    return paths


def _slugify(text: str) -> str:
    text = text.lower().strip()
    # Remove parentheses and brackets content
    text = re.sub(r'[（(][^)）]*[)）]', '', text)
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text[:80]
