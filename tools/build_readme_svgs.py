"""Generate the animated SVGs used by the profile README.

Run from the repository root:

    python tools/build_readme_svgs.py

The SVGs are self-contained (no external fonts, scripts or services) so
GitHub can render them through its image proxy. Animations use SMIL and
CSS, which both play inside <img> tags.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parent.parent / "assets"

MONO = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono','DejaVu Sans Mono',monospace"
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,'DejaVu Sans',sans-serif"

BG = "#0d1117"
PANEL = "#161b22"
BORDER = "#30363d"
TEXT = "#e6edf3"
MUTED = "#8b949e"
GREEN = "#3fb950"
BLUE = "#58a6ff"
PURPLE = "#bc8cff"
PINK = "#ff7b72"
YELLOW = "#e3b341"
ORANGE = "#f0883e"
CYAN = "#39c5cf"


def esc(text: str) -> str:
    return escape(text, {'"': "&quot;"})


def svg_doc(width: int, height: int, body: str, title: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">\n'
        f"<title>{esc(title)}</title>\n{body}\n</svg>\n"
    )


# ---------------------------------------------------------------------------
# Timeline: show groups between two moments of a looping master clock.
# ---------------------------------------------------------------------------


@dataclass
class Item:
    start: float
    inner: str
    end: float | None = None


@dataclass
class Timeline:
    clock: str = "clk"
    items: list[Item] = field(default_factory=list)

    def at(self, t: float) -> str:
        return f"{self.clock}.begin+{t:.2f}s"

    def add(self, start: float, inner: str, end: float | None = None) -> Item:
        item = Item(start, inner, end)
        self.items.append(item)
        return item

    def render(self, total: float) -> str:
        out = [
            f'<rect width="0" height="0"><animate id="{self.clock}" attributeName="x" '
            f'from="0" to="0" dur="{total:.2f}s" begin="0s;{self.clock}.end"/></rect>'
        ]
        for item in self.items:
            end = total if item.end is None else item.end
            out.append(
                f'<g opacity="0"><set attributeName="opacity" to="1" '
                f'begin="{self.at(item.start)}" dur="{end - item.start:.2f}s"/>{item.inner}</g>'
            )
        return "\n".join(out)


# ---------------------------------------------------------------------------
# 1. Terminal "video"
# ---------------------------------------------------------------------------

CW = 8.43  # monospace advance at 14px; text uses textLength so this is exact
LH = 22


class Terminal:
    def __init__(self, width: int, x0: int, y0: int):
        self.tl = Timeline()
        self.width = width
        self.x0 = x0
        self.y0 = y0
        self.t = 0.6
        self.row = 0
        self.scene: list[Item] = []
        self.clip_id = 0
        self.defs: list[str] = []

    # -- helpers ----------------------------------------------------------
    @property
    def y(self) -> float:
        return self.y0 + self.row * LH

    def _add(self, start: float, inner: str, end: float | None = None) -> None:
        item = self.tl.add(start, inner, end)
        if end is None:
            self.scene.append(item)

    def _mono(self, x: float, y: float, text: str, color: str, extra: str = "") -> str:
        return (
            f'<text x="{x:.1f}" y="{y:.1f}" fill="{color}" textLength="{len(text) * CW:.1f}" '
            f'lengthAdjust="spacingAndGlyphs" {extra}>{esc(text)}</text>'
        )

    def segments(self, x: float, y: float, segs: list[tuple[str, str]]) -> str:
        parts = []
        for text, color in segs:
            # SVG collapses edge whitespace, so place the visible part exactly
            body = text.strip(" ")
            if body:
                lead = len(text) - len(text.lstrip(" "))
                parts.append(self._mono(x + lead * CW, y, body, color))
            x += len(text) * CW
        return "".join(parts)

    # -- line types -------------------------------------------------------
    def cmd(self, command: str, pause: float = 0.5, speed: float = 0.055) -> None:
        start = self.t
        y = self.y
        prompt = [("emre@istanbul", GREEN), (" ", TEXT), ("~", BLUE), (" $ ", MUTED)]
        prompt_len = sum(len(s) for s, _ in prompt)
        cx = self.x0 + prompt_len * CW
        n = len(command)
        lead = 3  # frames of idle cursor before typing
        frames = [0] * lead + list(range(n + 1))
        dur = len(frames) * speed
        key_times = ";".join(f"{i / len(frames):.4f}" for i in range(len(frames)))
        widths = ";".join(f"{f * CW:.1f}" for f in frames)
        xs = ";".join(f"{cx + f * CW:.1f}" for f in frames)
        self.clip_id += 1
        cid = f"tc{self.clip_id}"
        self.defs.append(
            f'<clipPath id="{cid}"><rect x="{cx:.1f}" y="{y - 16}" width="0" height="22">'
            f'<animate attributeName="width" values="{widths}" keyTimes="{key_times}" '
            f'calcMode="discrete" dur="{dur:.2f}s" begin="{self.tl.at(start)}" fill="freeze"/>'
            f"</rect></clipPath>"
        )
        inner = self.segments(self.x0, y, prompt) + (
            f'<g clip-path="url(#{cid})">{self._mono(cx, y, command, TEXT)}</g>'
        )
        self._add(start, inner)
        cursor = (
            f'<rect x="{cx:.1f}" y="{y - 14}" width="{CW:.1f}" height="17" fill="{TEXT}" opacity="0.8">'
            f'<animate attributeName="x" values="{xs}" keyTimes="{key_times}" calcMode="discrete" '
            f'dur="{dur:.2f}s" begin="{self.tl.at(start)}" fill="freeze"/></rect>'
        )
        self._add(start, cursor, start + dur + 0.15)
        self.t = start + dur + pause
        self.row += 1

    def out(self, segs: list[tuple[str, str]] | str, delay: float = 0.12, indent: int = 0) -> None:
        if isinstance(segs, str):
            segs = [(segs, TEXT)]
        self._add(self.t, self.segments(self.x0 + indent * CW, self.y, segs))
        self.t += delay
        self.row += 1

    def blank(self, delay: float = 0.05) -> None:
        self.row += 1
        self.t += delay

    def wait(self, seconds: float) -> None:
        self.t += seconds

    def raw(self, inner: str, end: float | None = None, start: float | None = None) -> None:
        self._add(self.t if start is None else start, inner, end)

    def swap(self, frames: list[str], step: float) -> None:
        """Show each frame for `step` seconds; the last frame stays."""
        for i, frame in enumerate(frames):
            last = i == len(frames) - 1
            self._add(self.t + i * step, frame, None if last else self.t + (i + 1) * step)
        self.t += step * (len(frames) - 1)

    def bar(self, x: float, y: float, w: float, color: str, frac: float, dur: float = 1.4) -> None:
        inner = (
            f'<rect x="{x:.1f}" y="{y - 11}" width="{w:.1f}" height="12" rx="3" fill="{BORDER}"/>'
            f'<rect x="{x:.1f}" y="{y - 11}" width="0" height="12" rx="3" fill="{color}">'
            f'<animate attributeName="width" values="0;{w * frac:.1f}" dur="{dur}s" '
            f'begin="{self.tl.at(self.t)}" fill="freeze" calcMode="spline" keySplines="0.2 0.8 0.2 1"/></rect>'
        )
        self._add(self.t, inner)

    def clear(self, hold: float) -> None:
        end = self.t + hold
        for item in self.scene:
            item.end = end
        self.scene = []
        self.t = end + 0.35
        self.row = 0


def build_terminal() -> str:
    W, H = 900, 470
    term = Terminal(W, 26, 76)
    x0 = term.x0

    # Scene 1 - whoami / neofetch
    term.cmd("whoami --verbose")
    term.wait(0.2)
    top = term.y - 14
    avatar = (
        f'<g transform="translate({x0},{top})">'
        f'<rect width="150" height="150" rx="22" fill="url(#avatarGrad)"/>'
        f'<rect x="1" y="1" width="148" height="148" rx="21" fill="none" stroke="#ffffff" stroke-opacity="0.18"/>'
        f'<text x="75" y="92" text-anchor="middle" font-family="{SANS}" font-size="54" '
        f'font-weight="800" fill="#ffffff">AE</text>'
        f'<text x="75" y="122" text-anchor="middle" font-family="{MONO}" font-size="13" '
        f'fill="#ffffff" fill-opacity="0.85">&lt;/&gt; + AI</text>'
        f'<rect x="1" y="1" width="148" height="148" rx="21" fill="none" stroke="#ffffff" stroke-width="3">'
        f'<animate attributeName="stroke-opacity" values="0;0.6;0" dur="2.4s" repeatCount="indefinite"/></rect>'
        f"</g>"
    )
    term.raw(avatar)
    info_x = x0 + 180
    info = [
        [("ahmet", GREEN), ("@", MUTED), ("emre", GREEN)],
        [("─" * 44, BORDER)],
        [("Rol      ", BLUE), ("Full-stack & AI Uygulama Geliştiricisi", TEXT)],
        [("Konum    ", BLUE), ("İstanbul, TR", TEXT)],
        [("Backend  ", BLUE), ("Python · Django · NestJS · PostgreSQL", TEXT)],
        [("Frontend ", BLUE), ("Next.js · TypeScript", TEXT)],
        [("Test     ", BLUE), ("pytest · Playwright · Vitest · mutasyon", TEXT)],
        [("AI       ", BLUE), ("Claude Code · Codex · Cursor · LLM eval", TEXT)],
        [("Motto    ", BLUE), ("\"AI ile hızlı yaz, testle kanıtla.\"", YELLOW)],
    ]
    for segs in info:
        term._add(term.t, term.segments(info_x, term.y, segs))
        term.t += 0.13
        term.row += 1
    palette = "".join(
        f'<rect x="{info_x + i * 26}" y="{term.y - 6}" width="22" height="12" rx="2" fill="{c}"/>'
        for i, c in enumerate([PINK, ORANGE, YELLOW, GREEN, CYAN, BLUE, PURPLE, TEXT])
    )
    term.raw(palette)
    term.clear(hold=3.4)

    # Scene 2 - KârKontrol quality gate
    term.cmd("cd karkontrol && make verify")
    term.out([("▸ ", PURPLE), ("pytest + vitest", TEXT), ("  birim ve entegrasyon testleri", MUTED)])
    dots_y = term.y
    frames = []
    for k in range(1, 9):
        frames.append(term.segments(x0, dots_y, [("." * (k * 7), GREEN), (f"  {min(k * 84, 669)}/669", MUTED)]))
    frames.append(term.segments(x0, dots_y, [("." * 56, GREEN), ("  669 passed ✓", GREEN)]))
    term.swap(frames, 0.18)
    term.row += 1
    term.wait(0.3)
    term.out([("▸ ", PURPLE), ("playwright test", TEXT), ("  uçtan uca senaryolar", MUTED)], 0.5)
    term.out([("  13 passed ✓", GREEN), ("   chromium · gerçek tarayıcı akışları", MUTED)], 0.5)
    term.out([("▸ ", PURPLE), ("mutation testing", TEXT), ("  testler gerçekten hata yakalıyor mu?", MUTED)], 0.2)
    bar_y = term.y
    term.bar(x0, bar_y, 420, GREEN, 0.9883)
    term.swap(
        [term.segments(x0 + 436, bar_y, [(f"%{v}", GREEN)]) for v in ("12.40", "47.10", "81.90", "95.20", "98.83")],
        0.28,
    )
    term.row += 1
    term.wait(0.4)
    term.out([("▸ ", PURPLE), ("llm-eval asistan", TEXT), ("  soru seti + regresyon takibi", MUTED)], 0.4)
    term.out([("  52/52 ✓", GREEN), ("   model davranışı CI'da ölçülüyor", MUTED)], 0.5)
    term.blank()
    term.out([("✔ ", GREEN), ("Kalite kapısı geçti. ", TEXT), ("1 kuruşluk fark bile kaçmıyor.", YELLOW)])
    term.clear(hold=3.2)

    # Scene 3 - Vidolya
    term.cmd("vidolya generate --foto urun.jpg --format 9:16")
    steps = [
        ("Claude", "fotoğraf analizi ve konsept"),
        ("Claude", "sahne ve prompt üretimi"),
        ("kredi", "atomik olarak rezerve edildi"),
        ("Seedance", "image-to-video render"),
        ("storage", "kalıcı depolama + caption"),
    ]
    for tool, desc in steps:
        y = term.y
        label = [("  [", MUTED), (f"{tool:<9}", CYAN), ("] ", MUTED), (desc, TEXT)]
        spin = [term.segments(x0, y, [(f"{s} ", YELLOW)] + label) for s in "⠋⠙⠹⠸⠼⠴"]
        spin.append(term.segments(x0, y, [("✓ ", GREEN)] + label))
        term.swap(spin, 0.09)
        term.row += 1
        term.wait(0.12)
    term.blank()
    stat_y = term.y
    term.out([("Platformda üretilen video  ", MUTED)], 0)
    counter_x = x0 + len("Platformda üretilen video  ") * CW
    term.swap(
        [
            term.segments(counter_x, stat_y, [(str(v), PINK)])
            for v in (0, 37, 88, 142, 199, 251, 298, 336, 361)
        ]
        + [term.segments(counter_x, stat_y, [("370+", PINK), ("  ▲ canlı SaaS · vidolya.com", MUTED)])],
        0.12,
    )
    term.wait(0.4)
    term.out([("Restoran · kuyumcu · butik → ", MUTED), ("ajans ve çekim olmadan dikey reklam videosu", TEXT)])
    # phone mock-up on the right
    px, py = W - 190, 92
    phone = (
        f'<g transform="translate({px},{py})">'
        f'<rect width="140" height="250" rx="20" fill="#010409" stroke="{BORDER}" stroke-width="2"/>'
        f'<rect x="10" y="14" width="120" height="222" rx="12" fill="url(#phoneGrad)"/>'
        f'<circle cx="70" cy="118" r="34" fill="#ffffff" fill-opacity="0.92">'
        f'<animate attributeName="r" values="26;36;26" dur="2.4s" repeatCount="indefinite"/></circle>'
        f'<circle cx="70" cy="118" r="18" fill="{PINK}" fill-opacity="0.8">'
        f'<animate attributeName="r" values="14;20;14" dur="2.4s" repeatCount="indefinite"/></circle>'
        f'<rect x="22" y="182" width="96" height="8" rx="4" fill="#ffffff" fill-opacity="0.85"/>'
        f'<rect x="34" y="196" width="72" height="6" rx="3" fill="#ffffff" fill-opacity="0.55"/>'
        f'<rect x="20" y="222" width="100" height="3" rx="1.5" fill="#ffffff" fill-opacity="0.3"/>'
        f'<rect x="20" y="222" width="0" height="3" rx="1.5" fill="#ffffff">'
        f'<animate attributeName="width" values="0;100" dur="3s" repeatCount="indefinite"/></rect>'
        f'<text x="70" y="40" text-anchor="middle" font-family="{SANS}" font-size="11" '
        f'font-weight="700" fill="#ffffff">9:16 · REELS</text>'
        f"</g>"
    )
    term.raw(phone, start=term.tl.items[-1].start - 3.8)
    term.clear(hold=3.4)

    # Scene 4 - Jev agent orchestration
    term.cmd('jev "B2B paneline iade akışı ekle"')
    term.out([("◆ planlayıcı ", PURPLE), ("isteği 4 sözleşmeli görev kartına böldü", TEXT)], 0.35)
    agents = [
        ("claude-code", "worktree/api     ", "iade endpoint'i + idempotency"),
        ("codex      ", "worktree/web     ", "iade formu + durum ekranı"),
        ("claude-code", "worktree/db      ", "stok geri alma transaction'ı"),
        ("codex      ", "worktree/tests   ", "API + E2E senaryoları"),
    ]
    rows = []
    for name, tree, task in agents:
        rows.append((term.y, name, tree, task))
        term.out([("  ⠿ ", YELLOW), (name, BLUE), ("  ", TEXT), (tree, MUTED), (task, TEXT)], 0.18)
    term.wait(0.3)
    for i, (y, name, tree, task) in enumerate(rows):
        done = term.segments(x0, y, [("  ✓ ", GREEN), (name, BLUE), ("  ", TEXT), (tree, MUTED), (task, TEXT)])
        term.raw(f'<rect x="{x0 - 4}" y="{y - 16}" width="{W - 2 * x0}" height="22" fill="{BG}"/>{done}',
                 start=term.t + 0.55 * (i + 1))
    term.wait(0.55 * len(rows) + 0.4)
    term.out([("◆ doğrulayıcı ", PURPLE), ("testleri koşuyor…", MUTED)], 0.5)
    term.out([("  API 576 ✓  DB 133 ✓  Web 180 ✓  E2E 19 ✓", GREEN)], 0.5)
    term.blank()
    term.out([("✔ ", GREEN), ("4 ajan paralel çalıştı, sonuç doğrulandı, rapor hazır.", TEXT)])
    term.clear(hold=3.4)

    # Scene 5 - principles + contact
    term.cmd("cat ilkeler.md")
    principles = [
        ("01", "AI ile hız, testle güven.", "Her iddia bir teste, ölçüme ya da CI kaydına bağlı."),
        ("02", "İş kuralları önce gelir.", "Para, stok, kredi: veritabanı seviyesinde atomik."),
        ("03", "LLM'i ölçmeden yayına almam.", "Soru setleri, regresyon takibi, GitHub Actions."),
    ]
    for num, head, body in principles:
        term.out([(f"{num} ", PINK), (head, TEXT)], 0.15)
        term.out([("   " + body, MUTED)], 0.45)
    term.blank()
    term.cmd("open --contact")
    term.out([("  linkedin  ", BLUE), ("ahmet-emre-yıldız", TEXT)], 0.15)
    term.out([("  web       ", BLUE), ("vidolya.com", TEXT)], 0.15)
    term.out([("  mail      ", BLUE), ("aemryld@gmail.com", TEXT)], 0.4)
    term.blank()
    y = term.y
    idle = term.segments(x0, y, [("emre@istanbul", GREEN), (" ", TEXT), ("~", BLUE), (" $ ", MUTED)])
    cur_x = x0 + len("emre@istanbul ~ $ ") * CW
    idle += (
        f'<rect x="{cur_x:.1f}" y="{y - 14}" width="{CW:.1f}" height="17" fill="{TEXT}">'
        f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.5;1" dur="1s" repeatCount="indefinite"/></rect>'
    )
    term.raw(idle)
    term.clear(hold=4.0)

    total = term.t
    frame = f"""
<defs>
  <linearGradient id="avatarGrad" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="{PURPLE}"/><stop offset="0.55" stop-color="{BLUE}"/><stop offset="1" stop-color="{CYAN}"/>
  </linearGradient>
  <linearGradient id="phoneGrad" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{PURPLE}"/><stop offset="1" stop-color="{PINK}"/>
  </linearGradient>
  {''.join(term.defs)}
</defs>
<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="14" fill="{BG}" stroke="{BORDER}" stroke-width="2"/>
<path d="M1,15 a14,14 0 0 1 14,-14 h{W - 30} a14,14 0 0 1 14,14 v25 h-{W - 2} z" fill="{PANEL}"/>
<line x1="1" y1="40" x2="{W - 1}" y2="40" stroke="{BORDER}"/>
<circle cx="24" cy="21" r="6.5" fill="#ff5f56"/><circle cx="44" cy="21" r="6.5" fill="#ffbd2e"/><circle cx="64" cy="21" r="6.5" fill="#27c93f"/>
<text x="{W / 2}" y="26" text-anchor="middle" font-family="{MONO}" font-size="13" fill="{MUTED}">emre@istanbul — ~/portfolio — zsh</text>
<rect x="{W - 130}" y="12" width="110" height="18" rx="9" fill="{PINK}" fill-opacity="0.15"/>
<circle cx="{W - 117}" cy="21" r="4" fill="{PINK}"><animate attributeName="opacity" values="1;0.2;1" dur="1.4s" repeatCount="indefinite"/></circle>
<text x="{W - 107}" y="25" font-family="{MONO}" font-size="11" fill="{PINK}">REC · canlı</text>
<g font-family="{MONO}" font-size="14">
{term.tl.render(total)}
</g>
"""
    return svg_doc(W, H, frame, "Terminal animasyonu: Ahmet Emre Yıldız kimdir, ne yapar")


# ---------------------------------------------------------------------------
# 2. Header banner
# ---------------------------------------------------------------------------


def build_header() -> str:
    W, H = 1000, 300
    roles = [
        ("Full-stack geliştirici", BLUE),
        ("AI uygulama geliştiricisi", PURPLE),
        ("Testle kanıtlayan mühendis", GREEN),
        ("Canlı SaaS kurucusu", PINK),
    ]
    cycle = 12
    role_css = []
    role_svg = []
    for i, (text, color) in enumerate(roles):
        role_css.append(f".r{i}{{animation:role {cycle}s {i * cycle / len(roles):.1f}s infinite both}}")
        role_svg.append(
            f'<text class="role r{i}" x="{W / 2}" y="186" text-anchor="middle" fill="{color}">'
            f'<tspan fill="{MUTED}">&gt; </tspan>{esc(text)}<tspan fill="{color}" class="blink">_</tspan></text>'
        )
    glyphs = ["{ }", "</>", "=>", "λ", "∑", "#", "::", "()", "[]", "&&", "%", "AI"]
    floating = []
    for i, g in enumerate(glyphs):
        x = 40 + (i * 83) % (W - 80)
        delay = (i * 1.7) % 9
        dur = 9 + (i % 4) * 2
        floating.append(
            f'<text x="{x}" y="{H + 20}" font-family="{MONO}" font-size="{14 + (i % 3) * 4}" '
            f'fill="{[BLUE, PURPLE, GREEN, PINK][i % 4]}" opacity="0">{esc(g)}'
            f'<animate attributeName="y" values="{H + 20};-20" dur="{dur}s" begin="{delay}s" repeatCount="indefinite"/>'
            f'<animate attributeName="opacity" values="0;0.35;0.35;0" keyTimes="0;0.2;0.8;1" dur="{dur}s" '
            f'begin="{delay}s" repeatCount="indefinite"/></text>'
        )
    body = f"""
<defs>
  <linearGradient id="nameGrad" x1="0" y1="0" x2="1" y2="0" gradientUnits="objectBoundingBox">
    <stop offset="0" stop-color="{BLUE}"><animate attributeName="stop-color" values="{BLUE};{PURPLE};{PINK};{BLUE}" dur="8s" repeatCount="indefinite"/></stop>
    <stop offset="0.5" stop-color="{PURPLE}"><animate attributeName="stop-color" values="{PURPLE};{PINK};{BLUE};{PURPLE}" dur="8s" repeatCount="indefinite"/></stop>
    <stop offset="1" stop-color="{PINK}"><animate attributeName="stop-color" values="{PINK};{BLUE};{PURPLE};{PINK}" dur="8s" repeatCount="indefinite"/></stop>
  </linearGradient>
  <radialGradient id="glowA"><stop offset="0" stop-color="{PURPLE}" stop-opacity="0.55"/><stop offset="1" stop-color="{PURPLE}" stop-opacity="0"/></radialGradient>
  <radialGradient id="glowB"><stop offset="0" stop-color="{BLUE}" stop-opacity="0.5"/><stop offset="1" stop-color="{BLUE}" stop-opacity="0"/></radialGradient>
  <radialGradient id="glowC"><stop offset="0" stop-color="{PINK}" stop-opacity="0.35"/><stop offset="1" stop-color="{PINK}" stop-opacity="0"/></radialGradient>
  <pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse">
    <path d="M32 0H0V32" fill="none" stroke="#ffffff" stroke-opacity="0.045"/>
  </pattern>
  <clipPath id="card"><rect width="{W}" height="{H}" rx="18"/></clipPath>
  <style>
    .role{{font-family:{MONO};font-size:24px;font-weight:600;opacity:0}}
    {''.join(role_css)}
    @keyframes role{{0%{{opacity:0;transform:translateY(12px)}}4%{{opacity:1;transform:translateY(0)}}21%{{opacity:1;transform:translateY(0)}}25%{{opacity:0;transform:translateY(-12px)}}100%{{opacity:0}}}}
    .blink{{animation:blink 1s steps(1) infinite}}
    @keyframes blink{{50%{{opacity:0}}}}
  </style>
</defs>
<g clip-path="url(#card)">
  <rect width="{W}" height="{H}" fill="{BG}"/>
  <circle cx="180" cy="60" r="260" fill="url(#glowA)"><animate attributeName="cx" values="180;320;180" dur="14s" repeatCount="indefinite"/></circle>
  <circle cx="820" cy="250" r="280" fill="url(#glowB)"><animate attributeName="cx" values="820;660;820" dur="16s" repeatCount="indefinite"/></circle>
  <circle cx="520" cy="320" r="220" fill="url(#glowC)"><animate attributeName="cy" values="320;240;320" dur="12s" repeatCount="indefinite"/></circle>
  <rect width="{W}" height="{H}" fill="url(#grid)"/>
  {''.join(floating)}
  <text x="{W / 2}" y="70" text-anchor="middle" font-family="{MONO}" font-size="15" fill="{MUTED}" letter-spacing="3">MERHABA, BEN</text>
  <text x="{W / 2}" y="138" text-anchor="middle" font-family="{SANS}" font-size="62" font-weight="800" fill="url(#nameGrad)">Ahmet Emre Yıldız</text>
  {''.join(role_svg)}
  <text x="{W / 2}" y="238" text-anchor="middle" font-family="{SANS}" font-size="18" fill="{TEXT}">Kodu AI ajanlarıyla hızlı yazıyorum, <tspan fill="{GREEN}" font-weight="700">doğru olduğunu testlerle kanıtlıyorum.</tspan></text>
  <text x="{W / 2}" y="272" text-anchor="middle" font-family="{MONO}" font-size="13" fill="{MUTED}">📍 İstanbul · Python/Django · Next.js/TypeScript · NestJS · LLM</text>
</g>
<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="17" fill="none" stroke="{BORDER}" stroke-width="2"/>
"""
    return svg_doc(W, H, body, "Ahmet Emre Yıldız — Full-stack ve AI uygulama geliştiricisi")


# ---------------------------------------------------------------------------
# 3. Project cards
# ---------------------------------------------------------------------------

CARD_W, CARD_H = 500, 280


def card(slug: str, title: str, tag: str, accent: str, lines: list[str], visual: str, footer: str) -> str:
    desc = "".join(
        f'<text x="28" y="{110 + i * 21}" font-family="{SANS}" font-size="14.5" fill="{MUTED}">{esc(l)}</text>'
        for i, l in enumerate(lines)
    )
    tag_w = len(tag) * 7.3 + 24
    body = f"""
<defs>
  <linearGradient id="{slug}Edge" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="{accent}"/><stop offset="0.5" stop-color="{BORDER}"/><stop offset="1" stop-color="{accent}" stop-opacity="0.6"/>
  </linearGradient>
  <radialGradient id="{slug}Glow" cx="1" cy="0" r="1"><stop offset="0" stop-color="{accent}" stop-opacity="0.22"/><stop offset="1" stop-color="{accent}" stop-opacity="0"/></radialGradient>
</defs>
<rect x="1" y="1" width="{CARD_W - 2}" height="{CARD_H - 2}" rx="16" fill="{BG}"/>
<rect x="1" y="1" width="{CARD_W - 2}" height="{CARD_H - 2}" rx="16" fill="url(#{slug}Glow)"/>
<rect x="1" y="1" width="{CARD_W - 2}" height="{CARD_H - 2}" rx="16" fill="none" stroke="url(#{slug}Edge)" stroke-width="2"/>
<rect x="28" y="30" width="{tag_w:.0f}" height="22" rx="11" fill="{accent}" fill-opacity="0.14" stroke="{accent}" stroke-opacity="0.5"/>
<text x="{28 + tag_w / 2:.0f}" y="45.5" text-anchor="middle" font-family="{MONO}" font-size="11.5" font-weight="600" fill="{accent}">{esc(tag)}</text>
<text x="28" y="86" font-family="{SANS}" font-size="25" font-weight="800" fill="{TEXT}">{esc(title)}</text>
{desc}
{visual}
<text x="28" y="{CARD_H - 24}" font-family="{MONO}" font-size="12.5" fill="{accent}">{esc(footer)} →</text>
"""
    return svg_doc(CARD_W, CARD_H, body, f"{title} — {tag}")


def build_card_vidolya() -> str:
    counts = [0, 46, 112, 180, 241, 297, 338, 362]
    step = 0.22
    total = step * len(counts) + 5
    tl = Timeline("v")
    for i, c in enumerate(counts):
        tl.add(i * step, f'<text x="28" y="212" font-family="{SANS}" font-size="44" font-weight="800" fill="{PINK}">{c}</text>',
               (i + 1) * step)
    tl.add(len(counts) * step, f'<text x="28" y="212" font-family="{SANS}" font-size="44" font-weight="800" fill="{PINK}">370+</text>')
    visual = f"""
<defs><linearGradient id="vPhone" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{PURPLE}"/><stop offset="1" stop-color="{PINK}"/></linearGradient></defs>
{tl.render(total)}
<text x="28" y="234" font-family="{SANS}" font-size="13" fill="{MUTED}">platformda üretilen video</text>
<g transform="translate(372,40)">
  <rect width="102" height="186" rx="16" fill="#010409" stroke="{BORDER}" stroke-width="2"/>
  <rect x="8" y="10" width="86" height="166" rx="10" fill="url(#vPhone)"/>
  <rect x="26" y="52" width="50" height="50" rx="10" fill="#ffffff" fill-opacity="0.9">
    <animateTransform attributeName="transform" type="rotate" values="-6 51 77;6 51 77;-6 51 77" dur="3s" repeatCount="indefinite"/>
  </rect>
  <circle cx="51" cy="77" r="12" fill="{PINK}"><animate attributeName="r" values="9;14;9" dur="1.5s" repeatCount="indefinite"/></circle>
  <rect x="18" y="122" width="66" height="7" rx="3.5" fill="#ffffff" fill-opacity="0.85"/>
  <rect x="26" y="135" width="50" height="5" rx="2.5" fill="#ffffff" fill-opacity="0.55"/>
  <rect x="16" y="162" width="70" height="3" rx="1.5" fill="#ffffff" fill-opacity="0.3"/>
  <rect x="16" y="162" width="0" height="3" rx="1.5" fill="#ffffff"><animate attributeName="width" values="0;70" dur="3s" repeatCount="indefinite"/></rect>
  <text x="51" y="28" text-anchor="middle" font-family="{SANS}" font-size="9" font-weight="700" fill="#ffffff">9:16</text>
</g>
"""
    return card(
        "vid", "Vidolya", "CANLI SAAS", PINK,
        ["Ürün fotoğrafından dakikalar içinde dikey", "reklam videosu. Ajans ve çekim gerekmez."],
        visual, "vaka çalışması",
    )


def build_card_karkontrol() -> str:
    r = 52
    circ = 2 * 3.14159265 * r
    target = circ * (1 - 0.9883)
    visual = f"""
<g transform="translate(400,150)">
  <circle r="{r}" fill="none" stroke="{BORDER}" stroke-width="11"/>
  <circle r="{r}" fill="none" stroke="{GREEN}" stroke-width="11" stroke-linecap="round" transform="rotate(-90)"
    stroke-dasharray="{circ:.2f}" stroke-dashoffset="{circ:.2f}">
    <animate attributeName="stroke-dashoffset" values="{circ:.2f};{target:.2f};{target:.2f};{circ:.2f}" keyTimes="0;0.3;0.9;1" dur="7s" repeatCount="indefinite"/>
  </circle>
  <text y="2" text-anchor="middle" font-family="{SANS}" font-size="22" font-weight="800" fill="{TEXT}">%98,83</text>
  <text y="22" text-anchor="middle" font-family="{MONO}" font-size="10.5" fill="{MUTED}">mutasyon</text>
</g>
<g font-family="{SANS}">
  <text x="28" y="196" font-size="30" font-weight="800" fill="{GREEN}">669</text>
  <text x="28" y="216" font-size="12.5" fill="{MUTED}">test</text>
  <text x="118" y="196" font-size="30" font-weight="800" fill="{BLUE}">13</text>
  <text x="118" y="216" font-size="12.5" fill="{MUTED}">Playwright E2E</text>
  <text x="228" y="196" font-size="30" font-weight="800" fill="{PURPLE}">52/52</text>
  <text x="228" y="216" font-size="12.5" fill="{MUTED}">LLM asistan</text>
</g>
"""
    return card(
        "kk", "KârKontrol", "TEST · KALİTE", GREEN,
        ["Pazaryeri satıcısının kâr hesabını doğrular:", "1 kuruş, kargo baremini ve kârı değiştirir."],
        visual, "canlı test raporları",
    )


def build_card_b2b() -> str:
    parts = [("API", 576, BLUE), ("DB", 133, PURPLE), ("Web", 180, GREEN), ("E2E", 19, ORANGE)]
    total = sum(p[1] for p in parts)
    bar_w = 444
    x = 28
    segs = []
    legend = []
    for i, (name, n, color) in enumerate(parts):
        w = bar_w * n / total
        segs.append(
            f'<rect x="{x:.1f}" y="172" width="{max(w - 3, 2):.1f}" height="16" rx="4" fill="{color}" opacity="0">'
            f'<animate attributeName="opacity" values="0;0;1;1;0" keyTimes="0;{0.05 + i * 0.08:.2f};{0.12 + i * 0.08:.2f};0.92;1" dur="7s" repeatCount="indefinite"/></rect>'
        )
        legend.append(
            f'<circle cx="{28 + i * 112 + 5}" cy="{212}" r="5" fill="{color}"/>'
            f'<text x="{28 + i * 112 + 16}" y="217" font-family="{MONO}" font-size="13" fill="{TEXT}">{n} '
            f'<tspan fill="{MUTED}">{name}</tspan></text>'
        )
        x += w
    visual = f"""
<text x="28" y="160" font-family="{MONO}" font-size="12" fill="{MUTED}">NestJS · Next.js · PostgreSQL · {total} test</text>
<rect x="28" y="172" width="{bar_w}" height="16" rx="4" fill="{PANEL}"/>
{''.join(segs)}
{''.join(legend)}
"""
    return card(
        "b2b", "B2B Operations Suite", "FULL-STACK", BLUE,
        ["Sipariş, stok, depo, fatura ve iade tek panelde.", "Stok ve para hiçbir zaman \"yaklaşık\" değil."],
        visual, "repoyu incele",
    )


def build_card_jev() -> str:
    src = (60, 196)
    hub = (180, 196)
    agents = [(300, 166, "claude"), (300, 196, "codex"), (300, 226, "claude")]
    sink = (430, 196)
    paths = []
    dots = []
    for i, (ax, ay, name) in enumerate(agents):
        p1 = f"M{hub[0]},{hub[1]} C{hub[0] + 50},{hub[1]} {ax - 50},{ay} {ax},{ay}"
        p2 = f"M{ax},{ay} C{ax + 50},{ay} {sink[0] - 50},{sink[1]} {sink[0]},{sink[1]}"
        for j, p in enumerate((p1, p2)):
            paths.append(f'<path d="{p}" fill="none" stroke="{BORDER}" stroke-width="2"/>')
            dots.append(
                f'<circle r="4" fill="{[BLUE, GREEN, PURPLE][i]}"><animateMotion path="{p}" dur="1.2s" '
                f'begin="{0.9 + j * 1.3 + i * 0.25:.2f}s;{0.9 + j * 1.3 + i * 0.25:.2f}s+4s" repeatCount="indefinite"/></circle>'
            )
    paths.append(f'<path d="M{src[0]},{src[1]} L{hub[0]},{hub[1]}" stroke="{BORDER}" stroke-width="2"/>')
    dots.append(f'<circle r="4" fill="{YELLOW}"><animateMotion path="M{src[0]},{src[1]} L{hub[0]},{hub[1]}" dur="0.9s" repeatCount="indefinite"/></circle>')

    def node(x, y, label, color, w=74):
        return (
            f'<rect x="{x - w / 2}" y="{y - 12}" width="{w}" height="24" rx="12" fill="{PANEL}" stroke="{color}"/>'
            f'<text x="{x}" y="{y + 4}" text-anchor="middle" font-family="{MONO}" font-size="11" fill="{color}">{label}</text>'
        )

    nodes = node(*src, "istek", YELLOW, 64) + node(*hub, "planlayıcı", PURPLE, 86)
    nodes += "".join(node(ax, ay, name, [BLUE, GREEN, PURPLE][i]) for i, (ax, ay, name) in enumerate(agents))
    nodes += node(*sink, "doğrula ✓", GREEN, 86)
    visual = "".join(paths) + "".join(dots) + nodes
    return card(
        "jev", "Jev", "AI AJAN ORKESTRASYONU", PURPLE,
        ["Tek cümlelik isteği Claude Code ve Codex", "ajanlarından oluşan bir ekibe dağıtır."],
        visual, "interaktif demo",
    )


# ---------------------------------------------------------------------------
# 4. Workflow pipeline
# ---------------------------------------------------------------------------


def build_workflow() -> str:
    W, H = 1000, 190
    stages = [
        ("AI ajanı yazar", "Claude Code · Codex", BLUE),
        ("Testler", "pytest · Playwright", GREEN),
        ("Mutasyon", "testi test et", YELLOW),
        ("LLM eval", "soru seti · regresyon", PURPLE),
        ("CI", "GitHub Actions", CYAN),
        ("Yayında", "gerçek kullanıcı", PINK),
    ]
    n = len(stages)
    gap = (W - 200) / (n - 1)
    xs = [100 + i * gap for i in range(n)]
    y = 82
    dur = 7
    travel = 0.8  # share of the cycle spent travelling
    body = [
        f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="16" fill="{BG}" stroke="{BORDER}" stroke-width="2"/>',
        f'<line x1="{xs[0]}" y1="{y}" x2="{xs[-1]}" y2="{y}" stroke="{BORDER}" stroke-width="3" stroke-dasharray="2 8" stroke-linecap="round"/>',
        f'<line x1="{xs[0]}" y1="{y}" x2="{xs[0]}" y2="{y}" stroke="url(#flow)" stroke-width="3" stroke-linecap="round">'
        f'<animate attributeName="x2" values="{xs[0]};{xs[-1]};{xs[-1]};{xs[0]}" keyTimes="0;{travel};0.97;1" dur="{dur}s" repeatCount="indefinite"/></line>',
    ]
    for i, (name, sub, color) in enumerate(stages):
        x = xs[i]
        hit = travel * i / (n - 1)
        k1 = max(hit - 0.001, 0)
        body.append(
            f'<circle cx="{x}" cy="{y}" r="17" fill="{PANEL}" stroke="{color}" stroke-width="2.5"/>'
            f'<circle cx="{x}" cy="{y}" r="8" fill="{color}" opacity="0.15">'
            f'<animate attributeName="opacity" values="0.15;0.15;1;1;0.15" keyTimes="0;{k1:.3f};{hit + 0.001:.3f};0.97;1" dur="{dur}s" repeatCount="indefinite"/></circle>'
            f'<circle cx="{x}" cy="{y}" r="17" fill="none" stroke="{color}" stroke-width="2" opacity="0">'
            f'<animate attributeName="r" values="17;17;30;30" keyTimes="0;{k1:.3f};{min(hit + 0.08, 0.99):.3f};1" dur="{dur}s" repeatCount="indefinite"/>'
            f'<animate attributeName="opacity" values="0;0;0.8;0;0" keyTimes="0;{k1:.3f};{hit + 0.001:.3f};{min(hit + 0.08, 0.99):.3f};1" dur="{dur}s" repeatCount="indefinite"/></circle>'
            f'<text x="{x}" y="{y + 46}" text-anchor="middle" font-family="{SANS}" font-size="15" font-weight="700" fill="{TEXT}">{esc(name)}</text>'
            f'<text x="{x}" y="{y + 66}" text-anchor="middle" font-family="{MONO}" font-size="11.5" fill="{MUTED}">{esc(sub)}</text>'
        )
    body.append(
        f'<circle cx="{xs[0]}" cy="{y}" r="6" fill="#ffffff">'
        f'<animate attributeName="cx" values="{xs[0]};{xs[-1]};{xs[-1]};{xs[0]}" keyTimes="0;{travel};0.97;1" dur="{dur}s" repeatCount="indefinite"/>'
        f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;{travel};{travel + 0.02};1" dur="{dur}s" repeatCount="indefinite"/></circle>'
    )
    body.append(
        f'<text x="{W / 2}" y="34" text-anchor="middle" font-family="{MONO}" font-size="13" fill="{MUTED}">'
        f'her değişiklik bu hattan geçer · <tspan fill="{GREEN}">kanıt yoksa yayın yok</tspan></text>'
    )
    defs = (
        f'<defs><linearGradient id="flow" gradientUnits="userSpaceOnUse" x1="{xs[0]}" y1="0" x2="{xs[-1]}" y2="0">'
        + "".join(f'<stop offset="{i / (n - 1):.2f}" stop-color="{c}"/>' for i, (_, _, c) in enumerate(stages))
        + "</linearGradient></defs>"
    )
    return svg_doc(W, H, defs + "\n".join(body), "Çalışma hattı: AI yazar, testler, mutasyon, LLM eval, CI, yayın")


# ---------------------------------------------------------------------------
# 5. Tech stack
# ---------------------------------------------------------------------------


def build_stack() -> str:
    W = 1000
    groups = [
        ("Diller", BLUE, ["Python", "TypeScript", "C#", "SQL"]),
        ("Backend", PURPLE, ["Django", "NestJS", "PostgreSQL", "Prisma", "Supabase"]),
        ("Frontend", CYAN, ["Next.js", "React"]),
        ("Test", GREEN, ["pytest", "Playwright", "Vitest", "mutation testing"]),
        ("AI & CV", PINK, ["Claude Code", "Codex", "Cursor", "LLM API", "LLM eval", "YOLOv8"]),
        ("DevOps", ORANGE, ["GitHub Actions", "Git worktree"]),
    ]
    row_h = 40
    H = 30 + len(groups) * row_h + 14
    out = [f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="16" fill="{BG}" stroke="{BORDER}" stroke-width="2"/>']
    k = 0
    for r, (label, color, items) in enumerate(groups):
        y = 30 + r * row_h
        out.append(f'<text x="30" y="{y + 19}" font-family="{MONO}" font-size="13" font-weight="700" fill="{color}">{esc(label)}</text>')
        x = 150
        for item in items:
            w = len(item) * 7.83 + 26
            delay = 0.08 * k
            k += 1
            out.append(
                f'<g opacity="0"><animate attributeName="opacity" from="0" to="1" begin="{delay:.2f}s" dur="0.4s" fill="freeze"/>'
                f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="27" rx="13.5" fill="{color}" fill-opacity="0.12" stroke="{color}" stroke-opacity="0.45"/>'
                f'<text x="{x + w / 2:.1f}" y="{y + 18}" text-anchor="middle" font-family="{MONO}" font-size="13" fill="{TEXT}" '
                f'textLength="{len(item) * 7.83:.1f}" lengthAdjust="spacingAndGlyphs">{esc(item)}</text></g>'
            )
            x += w + 10
    # light sweep
    out.append(
        f'<rect x="-200" y="0" width="160" height="{H}" fill="url(#sweep)" clip-path="url(#stackClip)">'
        f'<animate attributeName="x" values="-200;{W + 40}" dur="5s" begin="2s" repeatCount="indefinite"/></rect>'
    )
    defs = (
        '<defs><linearGradient id="sweep" x1="0" y1="0" x2="1" y2="0">'
        '<stop offset="0" stop-color="#ffffff" stop-opacity="0"/><stop offset="0.5" stop-color="#ffffff" stop-opacity="0.06"/>'
        '<stop offset="1" stop-color="#ffffff" stop-opacity="0"/></linearGradient>'
        f'<clipPath id="stackClip"><rect width="{W}" height="{H}" rx="16"/></clipPath></defs>'
    )
    return svg_doc(W, H, defs + "\n".join(out), "Teknolojiler")


def main() -> None:
    OUT.mkdir(exist_ok=True)
    files = {
        "header.svg": build_header(),
        "terminal.svg": build_terminal(),
        "workflow.svg": build_workflow(),
        "stack.svg": build_stack(),
        "card-vidolya.svg": build_card_vidolya(),
        "card-karkontrol.svg": build_card_karkontrol(),
        "card-b2b.svg": build_card_b2b(),
        "card-jev.svg": build_card_jev(),
    }
    for name, content in files.items():
        (OUT / name).write_text(content, encoding="utf-8")
        print(f"assets/{name}  {len(content) / 1024:.1f} KB")


if __name__ == "__main__":
    main()
