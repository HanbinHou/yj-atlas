"""
AI Research Module — SearXNG 全网搜索 + DeepSeek 结构化提取 + 图片下载
"""
import json
import re
import time
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.parse import quote
import urllib.request

BASE_DIR = Path(__file__).resolve().parent.parent
CONTENT_DIR = BASE_DIR / "src" / "content"
PUBLIC_IMG = BASE_DIR / "public" / "images"

DEEPSEEK_BASE = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-v4-pro"
SEARXNG_URL = "http://localhost:8888"

# ── config ────────────────────────────────────────────

def get_api_key() -> str:
    config_file = Path(__file__).parent / "api_key.txt"
    if config_file.exists():
        return config_file.read_text(encoding="utf-8").strip()
    return ""

def set_api_key(key: str):
    (Path(__file__).parent / "api_key.txt").write_text(key.strip(), encoding="utf-8")

# ── SearXNG search ────────────────────────────────────

def _ddgs_search(query: str, count: int = 8) -> list[dict]:
    """DuckDuckGo web search via ddgs."""
    try:
        from ddgs import DDGS
        results = []
        for r in DDGS().text(f"{query} architecture", max_results=count):
            results.append({"url": r.get("href", ""), "title": r.get("title", ""), "body": r.get("body", "")})
        return results
    except Exception as e:
        print(f"[DDGS error] {e}")
        return []

def searx_search(query: str, category: str = "general", count: int = 10) -> list[dict]:
    """Search via SearXNG. category: general | images."""
    try:
        url = f"{SEARXNG_URL}/search?q={quote(query)}&format=json&categories={category}&pageno=1"
        req = Request(url, headers={"User-Agent": "YJAtlas/1.0"})
        data = json.loads(urlopen(req, timeout=15).read())
        results = data.get("results", [])
        return results[:count]
    except Exception as e:
        print(f"[SearXNG error] {e}")
        return []

def fetch_page_text(url: str, max_chars: int = 5000) -> str:
    """Fetch and extract text from a web page."""
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        html = urlopen(req, timeout=10).read().decode("utf-8", errors="ignore")
        # Simple tag stripping
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL|re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL|re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:max_chars]
    except Exception as e:
        print(f"[fetch error] {url}: {e}")
        return ""

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
[建筑类型，从以下选择最匹配的一个：住宅/集合住宅/商业/办公/社区中心/文化建筑/博物馆/图书馆/学校/体育建筑/宗教建筑/医院/交通建筑/工业建筑/景观建筑/城市设计/改造项目/临时建筑/其他]
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

MATERIAL_RESEARCH_PROMPT = """你是一位建筑材料专家。请对以下建筑材料进行深入研究，输出严格格式化的内容。

材料名称：{project_name}

---TITLE---
[材料的中文名称]
---CATEGORY---
[从以下选择：结构材料/围护材料/饰面材料/保温材料/防水材料/声学材料/其他]
---SCENARIOS---
[适用场景，用中文逗号分隔，如：框架结构, 外墙, 室内饰面]
---DESCRIPTION---
[一句话概述，不超过80个汉字，突出核心特征与建筑价值]
---TAGS---
[3-5个标签，用中文逗号分隔]
---PROP_NAME_1---
[性能参数1名称，如：密度]
---PROP_VAL_1---
[性能参数1值，如：2400 kg/m³]
---PROP_NAME_2---
[性能参数2名称]
---PROP_VAL_2---
[性能参数2值]
---PROP_NAME_3---
[性能参数3名称]
---PROP_VAL_3---
[性能参数3值]
---PROP_NAME_4---
[性能参数4名称]
---PROP_VAL_4---
[性能参数4值]
---BODY---
[详细说明材料的组成、生产工艺、建筑表现、典型应用案例，3-5段]
---IMAGE_QUERIES---
[用于搜索材料图片的英文关键词，每行一个，共4个]"""

BOOK_RESEARCH_PROMPT = """你是一位建筑文献研究助手。请对以下建筑书籍进行深入研究，输出严格格式化的内容。

书名：{project_name}

---TITLE---
[书名]
---AUTHOR---
[作者姓名]
---YEAR---
[出版年份，只输出数字]
---CATEGORY---
[从以下选择：建筑基础/理论与历史/设计方法论/结构与技术/材料与构造/环境调控/设计表达/城市设计/建筑图集/其他]
---SUMMARY---
[200字以内的内容摘要，涵盖核心论点和价值]
---TAGS---
[3-5个标签，用中文逗号分隔]
---READING_PATH---
[入门/进阶/深度]
---BODY---
[详细介绍书籍背景、章节结构、核心观点、学术影响，3-5段]"""


def _deepseek_chat(system_prompt: str, user_message: str, max_tokens: int = 4096) -> str:
    """Call DeepSeek API (OpenAI-compatible)."""
    api_key = get_api_key()
    url = f"{DEEPSEEK_BASE}/v1/chat/completions"
    payload = json.dumps({
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.7,
    }).encode("utf-8")

    req = Request(url, data=payload, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    })
    resp = json.loads(urlopen(req, timeout=120).read())
    return resp["choices"][0]["message"]["content"]


def research_project(project_name: str) -> dict:
    """Main entry: SearXNG search → fetch pages → DeepSeek extract → structured MD."""
    api_key = get_api_key()
    if not api_key:
        return {"error": "请先在设置页面配置 DeepSeek API Key"}

    # Step 1: Web search via DuckDuckGo (SearXNG → DDGS)
    web_results = _ddgs_search(project_name, count=8)
    if not web_results:
        web_results = searx_search(f"{project_name} architecture", "general", count=8)

    # Step 2: Fetch content from top pages
    page_texts = []
    for r in web_results[:5]:
        url = r.get("url", "")
        text = fetch_page_text(url, 3000)
        if text:
            page_texts.append(f"来源: {url}\n标题: {r.get('title','')}\n内容: {text}")

    # Step 3: Build prompt with web sources
    if page_texts:
        sources_block = "\n\n---\n\n".join(page_texts)
        user_message = f"""以下是从互联网搜索"{project_name}"找到的资料：

{sources_block}

请基于以上资料和你的知识，按以下格式输出结构化的建筑案例分析：

{RESEARCH_PROMPT.format(project_name=project_name)}"""
    else:
        user_message = RESEARCH_PROMPT.format(project_name=project_name)

    # Step 4: Extract with DeepSeek
    text = _deepseek_chat(
        system_prompt="你是一位建筑学教授，擅长研究建筑案例并基于搜索资料输出结构化的学术内容。回复使用简体中文。务必覆盖所有要求的字段，不要省略任何一个。",
        user_message=user_message,
    )

    data = parse_response(text)
    # Robust slug: title > project_name > timestamp
    slug = _slugify(data.get("title") or "")
    if not slug or "untitled" in slug or slug == "untitled":
        slug = _slugify(project_name)
    if not slug or "untitled" in slug or slug == "untitled":
        slug = f"project-{int(time.time())}"
    data["slug"] = slug
    data["raw"] = text
    data["sources_count"] = len(page_texts)
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


def search_images(query: str, count: int = 8) -> list[dict]:
    """Search images via DuckDuckGo, fallback to Wikimedia Commons."""
    results = []

    # Primary: DuckDuckGo image search
    try:
        from ddgs import DDGS
        for r in DDGS().images(f"{query} architecture", max_results=count):
            img_url = r.get("image", "") or r.get("thumbnail", "")
            if img_url and img_url.startswith("http"):
                results.append({"url": img_url, "width": r.get("width", 1200), "title": r.get("title", "")})
    except Exception as e:
        print(f"[DDGS image error] {e}")

    # If SearXNG is available, also try it
    try:
        img_results = searx_search(f"{query} architecture", "images", count=count)
        for r in img_results:
            img_url = r.get("img_src") or r.get("thumbnail_src") or r.get("url", "")
            if img_url and img_url.startswith("http"):
                results.append({"url": img_url, "width": 1200, "title": r.get("title", "")})
    except Exception:
        pass

    # Fallback: Wikimedia Commons
    if len(results) < 3:
        try:
            search_url = (
                f"https://commons.wikimedia.org/w/api.php"
                f"?action=query&list=search&srsearch={quote(query + ' architecture')}"
                f"&srnamespace=6&format=json&srlimit={count * 2}"
            )
            data = json.loads(urlopen(Request(search_url, headers={"User-Agent": "YJAtlas/1.0"}), timeout=15).read())
            pages = [r["title"] for r in data.get("query", {}).get("search", [])]
            for page_title in pages[:count * 2]:
                img_url = (
                    f"https://commons.wikimedia.org/w/api.php"
                    f"?action=query&titles={quote(page_title)}"
                    f"&prop=imageinfo&iiprop=url|size&format=json"
                )
                img_data = json.loads(urlopen(Request(img_url, headers={"User-Agent": "YJAtlas/1.0"}), timeout=10).read())
                for pinfo in img_data.get("query", {}).get("pages", {}).values():
                    ii = pinfo.get("imageinfo", [])
                    if ii and ii[0].get("width", 0) >= 800:
                        results.append({"url": ii[0]["url"], "width": ii[0]["width"], "title": ii[0].get("descriptionurl", "")})
                if len(results) >= count:
                    break
        except Exception as e:
            print(f"[Wikimedia error] {e}")

    results.sort(key=lambda x: x.get("width", 0), reverse=True)
    return results[:count]


def download_images(image_urls: list[dict], slug: str, content_type: str = "cases") -> list[str]:
    """Download images to public/images/{content_type}/{slug}/, return list of paths."""
    dest_dir = PUBLIC_IMG / content_type / slug
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
            paths.append(f"/images/{content_type}/{slug}/{dest_file.name}")
            time.sleep(0.3)  # Rate limit
        except Exception as e:
            print(f"[download error] {url}: {e}")

    return paths


def research_material(material_name: str) -> dict:
    """Research a material via web search + DeepSeek."""
    api_key = get_api_key()
    if not api_key:
        return {"error": "请先配置 DeepSeek API Key"}

    web_results = _ddgs_search(f"{material_name} building material architecture", count=5)
    page_texts = []
    for r in web_results[:4]:
        text = fetch_page_text(r.get("url", ""), 2500)
        if text:
            page_texts.append(f"来源: {r.get('url','')}\n{text}")

    sources_block = "\n\n---\n\n".join(page_texts) if page_texts else material_name
    user_msg = f"搜索资料：\n{sources_block}\n\n{MATERIAL_RESEARCH_PROMPT.format(project_name=material_name)}"

    text = _deepseek_chat(
        system_prompt="你是一位建筑材料专家。基于搜索资料生成结构化的材料分析。必填所有字段。",
        user_message=user_msg,
    )
    return _parse_material(text, material_name)


def _parse_material(text: str, fallback_name: str) -> dict:
    """Parse material research response."""
    def extract(marker, txt):
        pattern = rf'---{marker}---\s*\n(.*?)(?=\n---|\Z)'
        m = re.search(pattern, txt, re.DOTALL)
        return m.group(1).strip() if m else ""

    props = []
    for i in range(1, 5):
        name = extract(f"PROP_NAME_{i}", text)
        val = extract(f"PROP_VAL_{i}", text)
        if name and val:
            props.append({"name": name, "value": val})

    slug = _slugify(extract("TITLE", text) or fallback_name)
    if not slug or slug == "untitled":
        slug = _slugify(fallback_name)

    return {
        "slug": slug,
        "title": extract("TITLE", text) or fallback_name,
        "category": extract("CATEGORY", text),
        "scenarios": extract("SCENARIOS", text),
        "description": extract("DESCRIPTION", text),
        "tags": extract("TAGS", text),
        "properties": props,
        "body": extract("BODY", text),
        "image_queries": extract("IMAGE_QUERIES", text),
        "raw": text,
    }


def research_book(book_name: str) -> dict:
    """Research a book via web search + DeepSeek (lightweight, no images)."""
    api_key = get_api_key()
    if not api_key:
        return {"error": "请先配置 DeepSeek API Key"}

    web_results = _ddgs_search(f"{book_name} architecture book", count=5)
    page_texts = []
    for r in web_results[:4]:
        text = fetch_page_text(r.get("url", ""), 2500)
        if text:
            page_texts.append(f"来源: {r.get('url','')}\n{text}")

    sources_block = "\n\n---\n\n".join(page_texts) if page_texts else book_name
    user_msg = f"搜索资料：\n{sources_block}\n\n{BOOK_RESEARCH_PROMPT.format(project_name=book_name)}"

    text = _deepseek_chat(
        system_prompt="你是一位建筑文献研究助手。基于搜索资料输出结构化的书目信息。必填所有字段。",
        user_message=user_msg,
    )
    return _parse_book(text, book_name)


def _parse_book(text: str, fallback_name: str) -> dict:
    """Parse book research response."""
    def extract(marker, txt):
        pattern = rf'---{marker}---\s*\n(.*?)(?=\n---|\Z)'
        m = re.search(pattern, txt, re.DOTALL)
        return m.group(1).strip() if m else ""

    slug = _slugify(extract("TITLE", text) or fallback_name)
    if not slug or slug == "untitled":
        slug = _slugify(fallback_name)

    return {
        "slug": slug,
        "title": extract("TITLE", text) or fallback_name,
        "author": extract("AUTHOR", text),
        "year": extract("YEAR", text),
        "category": extract("CATEGORY", text),
        "summary": extract("SUMMARY", text),
        "tags": extract("TAGS", text),
        "readingPath": extract("READING_PATH", text) or "intermediate",
        "body": extract("BODY", text),
        "raw": text,
    }


def _slugify(text: str) -> str:
    text = text.lower().strip()
    # Remove parentheses and brackets content
    text = re.sub(r'[（(][^)）]*[)）]', '', text)
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text[:80]
