# crawler/utils.py
from __future__ import annotations
import os, re, uuid, requests
from urllib.parse import urljoin, urlparse
import bleach
from bs4 import BeautifulSoup
from readability import Document
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage


IMG_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg")
IMG_FILENAME_RE = re.compile(r'\.(jpg|jpeg|png|webp|gif|svg)(\s*\(ở đây\))?$', re.I)

# ---------- HTTP ----------
HEADERS = {
    "User-Agent": "VNNewsBot/1.0 (+contact@example.com) Chrome/127.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
REQUEST_TIMEOUT = 25  # seconds

# ---------- Sanitize ----------
# ---------- Sanitize ----------
BASE_ALLOWED = set(bleach.sanitizer.ALLOWED_TAGS)
ALLOWED_TAGS = BASE_ALLOWED.union({
    "p","br","strong","em","b","i","u","span",
    "ul","ol","li","blockquote",
    "h2","h3","h4","h5","h6",
    "figure","figcaption","img","a",
})
# ALLOWED_ATTRS: thêm data-src, data-original, srcset, data-srcset, sizes
ALLOWED_ATTRS = {
    "a": ["href","title","rel","target"],
    "img": ["src","alt","title","loading","data-src","data-original","srcset","data-srcset","sizes"],
}

ALLOWED_PROTOCOLS = ["http","https","data"]

from bs4 import NavigableString, Comment

def _pick_from_srcset(srcset: str | None) -> str | None:
    if not srcset: 
        return None
    # "url 1x, url2 2x, url3 3x" -> lấy url đầu
    parts = [p.strip() for p in srcset.split(",") if p.strip()]
    if not parts:
        return None
    return parts[0].split()[0]

def _best_img_src(img) -> str | None:
    """Ưu tiên src -> srcset -> data-src -> data-srcset -> data-original."""
    return (
        img.get("src")
        or _pick_from_srcset(img.get("srcset"))
        or img.get("data-src")
        or _pick_from_srcset(img.get("data-srcset"))
        or img.get("data-original")
    )


def _strip_filename_textnodes(soup: BeautifulSoup) -> None:
    """
    Xoá mọi text node trần có nội dung chỉ là tên file ảnh (*.jpg|*.png|...),
    đồng thời dọn parent rỗng (figure/p/span/…).
    """
    for node in list(soup.find_all(string=True)):
        if isinstance(node, Comment):
            continue
        text = (str(node) or "").strip()
        if not text:
            continue
        # tương tự _looks_like_lonely_filename nhưng áp vào string thuần
        t = re.sub(r"\s+", " ", text).strip()
        if len(t) > 160:
            continue
        t = t.lstrip("@•-–—:·*[]()“”\"'")  # nhiều ký hiệu mở đầu có thể gặp
        if IMG_FILENAME_RE.search(t):
            parent = node.parent
            node.extract()
            # nếu parent không còn gì hữu dụng -> xoá parent
            if parent and not parent.get_text(strip=True) and not parent.find():
                parent.decompose()


def _looks_like_lonely_filename(text: str) -> bool:
    # Gom khoảng trắng, bỏ ký hiệu đầu dòng, xét độ dài để tránh xóa nhầm
    t = re.sub(r"\s+", " ", (text or "")).strip()
    if len(t) > 120:
        return False
    t = t.lstrip("@•-–—:··*")  # các ký tự thường gặp trước tên file
    return bool(IMG_FILENAME_RE.search(t))

def _remove_filename_artifacts(soup: BeautifulSoup) -> None:
    # Xóa các node chỉ là tên file *.jpg/… (ở đây)
    CANDIDATES = ("p", "span", "em", "strong", "small", "a")
    for el in list(soup.find_all(CANDIDATES)):
        text = el.get_text(" ", strip=True)
        if _looks_like_lonely_filename(text):
            el.decompose()


def _is_image_url(href: str | None) -> bool:
    if not href:
        return False
    href = href.strip().split("?", 1)[0].split("#", 1)[0]
    return any(href.lower().endswith(ext) for ext in IMG_EXTS)

def _convert_image_links_to_imgs(soup: BeautifulSoup, base_url: str) -> None:
    """
    - Với <a href="...jpg|png|webp|gif|svg">: thay bằng <img src="...">.
    - Nếu <p> chỉ chứa 1 link ảnh -> thay cả <p> thành <figure><img/></figure>.
    - Xoá các <p> chỉ còn text tên file *.jpg (ở đây).
    """
    # 1) <a href="...ext"> -> <img>
    for a in list(soup.find_all("a")):
        href = a.get("href")
        if not _is_image_url(href):
            continue
        abs_href = _abs_url(base_url, href)
        img = soup.new_tag("img", src=abs_href or href)
        # nếu <a> nằm trong <p> và chỉ có mỗi a -> thay cả <p> thành figure
        parent = a.parent
        if parent and parent.name == "p" and len(parent.contents) == 1:
            fig = soup.new_tag("figure")
            fig.append(img)
            a.replace_with(fig)
        else:
            a.replace_with(img)

    # 2) Xoá các paragraph chỉ là tên file *.jpg (ở đây)
    for p in list(soup.find_all("p")):
        text = p.get_text(" ", strip=True)
        if text and IMG_FILENAME_RE.search(text):
            p.decompose()


def _abs_url(base: str, maybe_url: str | None) -> str | None:
    if not maybe_url:
        return None
    try:
        u = maybe_url.strip()
        if u.startswith("//"):          # ← xử lý protocol-relative
            return "https:" + u
        return urljoin(base, u)
    except Exception:
        return maybe_url


def _first_meta_image(head: BeautifulSoup) -> str | None:
    for sel, attr in [
        ('meta[property="og:image"]', "content"),
        ('meta[property="og:image:secure_url"]', "content"),
        ('meta[name="twitter:image"]', "content"),
        ('meta[itemprop="image"]', "content"),
        ('link[rel="image_src"]', "href"),
    ]:
        tag = head.select_one(sel)
        if tag and tag.get(attr):
            return tag[attr]
    return None

def _sanitize_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for bad in soup(["script", "style", "noscript", "iframe"]):
        bad.decompose()
    cleaned = bleach.clean(
        str(soup),
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    )
    # Rút gọn xuống 2 newline tối đa
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned

def _download_to_media(abs_url: str, subdir: str = "articles") -> str | None:
    try:
        if abs_url.startswith("data:"):
            return None
        r = requests.get(abs_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        ext = os.path.splitext(urlparse(abs_url).path)[1].lower() or ".jpg"
        if ext not in IMG_EXTS:
            ext = ".jpg"

        fname = f"{uuid.uuid4().hex}{ext}"
        rel_path = os.path.join(subdir, fname).replace("\\", "/")
        default_storage.save(rel_path, ContentFile(r.content))
        return settings.MEDIA_URL.rstrip("/") + "/" + rel_path
    except Exception:
        return None

from urllib.parse import urlparse, parse_qs, unquote

def normalize_image_url(url: str) -> str:
    """
    - Nhận URL ảnh người dùng dán vào.
    - Nếu là link Google /imgres, tách param imgurl ra.
    - Trả lại URL ảnh gốc.
    """
    url = (url or "").strip()
    if not url:
        return ""
    try:
        p = urlparse(url)
        # bắt các domain google.* (google.com, google.com.vn, ...)
        if "google." in p.netloc and p.path.startswith("/imgres"):
            q = parse_qs(p.query)
            if "imgurl" in q and q["imgurl"]:
                return unquote(q["imgurl"][0])
        return url
    except Exception:
        return url


def _rewrite_images_to_media(soup: BeautifulSoup, base_url: str, subdir: str = "articles") -> tuple[str | None, str]:
    hero_url, hero_caption = None, ""

    # caption figure đầu (tạm lấy trước)
    first_fig = soup.find("figure")
    if first_fig:
        fc = first_fig.find("figcaption")
        if fc:
            hero_caption = fc.get_text(" ", strip=True)

    for idx, img in enumerate(soup.find_all("img")):
        raw_src = _best_img_src(img)
        abs_src = _abs_url(base_url, raw_src)
        if not abs_src:
            fig = img.parent if img.parent and img.parent.name == "figure" else None
            img.decompose()
            if fig and not fig.find("img"):
                fig.decompose()
            continue

        media_url = _download_to_media(abs_src, subdir=subdir)
        if not media_url:
            fig = img.parent if img.parent and img.parent.name == "figure" else None
            img.decompose()
            if fig and not fig.find("img"):
                fig.decompose()
            continue

        # Ghi đè src về MEDIA, dọn các attr lazy để HTML sạch
        img["src"] = media_url
        for k in ("data-src","data-srcset","data-original","srcset","sizes"):
            if k in img.attrs: del img.attrs[k]
        img["loading"] = img.get("loading") or "lazy"
        if not img.get("alt"): img["alt"] = ""

    # Sau khi rewrite xong, chọn hero là figure đầu có img đã rewrite
    for fig in soup.find_all("figure"):
        im = fig.find("img")
        if im and im.get("src"):
            hero_url = im["src"]
            cap = fig.find("figcaption")
            if cap:
                hero_caption = cap.get_text(" ", strip=True)
            break

    # fallback: first img bất kỳ
    if not hero_url:
        im = soup.find("img")
        if im and im.get("src"):
            hero_url = im["src"]

    return hero_url, hero_caption


def _html_to_blocks(safe_html: str) -> list[dict]:
    """Chuyển HTML đã sanitize thành danh sách block có trật tự (để render/đổi layout sau này)."""
    soup = BeautifulSoup(safe_html, "html.parser")
    blocks: list[dict] = []
    order = 0

    def push(btype: str, data: dict):
        nonlocal order
        blocks.append({"type": btype, "order": order, "data": data})
        order += 1

    for el in soup.find_all(recursive=False):
        name = (el.name or "").lower()

        if name in {"h2", "h3", "h4", "h5", "h6"}:
            push("heading", {"level": name, "text": el.get_text(" ", strip=True)})

        elif name == "p":
            only_img = el.find("img") and el.get_text(strip=True) == ""
            if only_img:
                img = el.find("img")
                push("figure", {
                    "src": img.get("src"),
                    "alt": img.get("alt", ""),
                    "caption": "",
                })
            else:
                push("paragraph", {"html": str(el)})

        elif name in {"ul", "ol"}:
            items = [li.get_text(" ", strip=True) for li in el.find_all("li", recursive=False)]
            push("list", {"ordered": name == "ol", "items": items})

        elif name == "blockquote":
            push("quote", {"html": str(el)})

        elif name == "figure":
            img = el.find("img")
            cap = el.find("figcaption")
            if img:
                push("figure", {
                    "src": img.get("src"),
                    "alt": img.get("alt", ""),
                    "caption": cap.get_text(" ", strip=True) if cap else "",
                })
        else:
            push("raw", {"html": str(el)})

    return blocks

def _pick_excerpt(blocks: list[dict]) -> str:
    """Lấy 1 đoạn đầu làm tóm tắt ngắn từ blocks."""
    for b in blocks:
        if b["type"] == "paragraph":
            text = BeautifulSoup(b["data"]["html"], "html.parser").get_text(" ", strip=True)
            if text:
                return text[:240]
    return ""

def fetch_and_extract(url: str) -> dict:
    """
    Trả về dict:
    {
      title, excerpt, content_html, main_image_url, main_image_caption, blocks
    }
    """
    result = {
        "title": "",
        "excerpt": "",
        "content_html": "",
        "main_image_url": None,
        "main_image_caption": "",
        "blocks": [],
    }

    # 1) Fetch
    try:
        r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        raw_html = r.text
    except Exception:
        return result

    # 2) Readability
    try:
        doc = Document(raw_html)
        title = (doc.short_title() or "").strip()
        main_html = doc.summary(html_partial=True)
    except Exception:
        title, main_html = "", raw_html  # fallback

    # 3) Meta image (fallback)
    try:
        meta_img = _first_meta_image(BeautifulSoup(raw_html, "html.parser"))
    except Exception:
        meta_img = None

    # 4) Sanitize & rewrite media/links
    safe_html = _sanitize_html(main_html)
    soup = BeautifulSoup(safe_html, "html.parser")
    # Chuyển các link ảnh -> img & dọn p chỉ tên file
    _convert_image_links_to_imgs(soup, base_url=url)
    _remove_filename_artifacts(soup)
    _strip_filename_textnodes(soup)   # ← xoá text node tên file còn sót

    subdir = f"articles/{urlparse(url).netloc}"
    hero_url, hero_cap = _rewrite_images_to_media(soup, base_url=url, subdir=subdir)

    # 5) Ưu tiên ảnh đã tải về MEDIA, fallback meta
    main_image_url = hero_url or _abs_url(url, meta_img)
    main_image_caption = hero_cap

    # 6) Blocks + excerpt (dùng luôn 2 hàm đã có để khỏi dư thừa)
    blocks = _html_to_blocks(str(soup))
    excerpt = _pick_excerpt(blocks)

    # 7) Kết quả
    result.update({
        "title": title,
        "excerpt": excerpt,
        "content_html": str(soup),               # đã rewrite src -> MEDIA_URL, href tuyệt đối
        "main_image_url": main_image_url,
        "main_image_caption": main_image_caption,
        "blocks": blocks,
    })
    return result
