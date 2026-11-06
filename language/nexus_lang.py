# -*- coding: utf-8 -*-
"""넥서스 언어 v1 — 코드 층 해석기.

문법 정본(문법_정본_v1.md)의 실행형이다. 결정적 파싱·복원·왕복 검사와
모델 층 출구용 에코 탐지를 제공한다. 이 모듈은 어떤 추측도 하지 않는다:
모르는 태그·깨진 해시·형식 위반은 NLError로 거부한다.

사용 예:
    d = load_dictionary("사전_v1.txt")
    msg = compose([("PV", "필수"), ("L", "한국어")], d, sid="s1", layer="model")
    parsed = parse(msg, d)
    plain = restore(parsed, d)          # 원문 렌더링
    hits = detect_echo(model_answer, d) # 에코 탐지 (문법 §8)
"""
import hashlib
import re
from dataclasses import dataclass, field


class NLError(Exception):
    """넥서스 언어 형식·검증 오류. 호출자는 원문 경로로 되돌려야 한다."""


LAYERS = {"지시": 1, "덩어리": 2, "데이터": 3}
STATUSES = {"유효", "폐기"}


@dataclass
class Entry:
    tag: str
    layer: str
    source: str          # 원문
    usage: str
    date: str
    status: str = "유효"

    @property
    def active(self):
        return self.status == "유효"


@dataclass
class Dictionary:
    version: str
    date: str
    entries: dict = field(default_factory=dict)   # tag -> Entry (폐기 포함)

    def get(self, tag):
        return self.entries.get(tag)

    def active_tags(self):
        return [t for t, e in self.entries.items() if e.active]

    def phrases(self):
        """에코 탐지·구절 치환용 원문 구절 — 긴 것부터. 복원에는 폐기도 포함."""
        ps = [e.source for e in self.entries.values()]
        return sorted(set(ps), key=len, reverse=True)


def load_dictionary(path):
    """사전 파일을 엄격히 읽는다. 형식이 깨졌으면 NLError."""
    version, date, entries = None, None, {}
    with open(path, encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, 1):
            line = raw.rstrip("\n")
            if not line.strip() or line.startswith("#"):
                continue
            if line.startswith("@DICT"):
                version = line.split(None, 1)[1].strip()
                continue
            if line.startswith("@DATE"):
                date = line.split(None, 1)[1].strip()
                continue
            parts = [p.strip() for p in line.split(" | ")]
            if len(parts) != 6:
                raise NLError(f"사전 {lineno}행: 필드 6개가 아님: {line[:40]}")
            tag, layer, source, usage, rdate, status = parts
            if layer not in LAYERS:
                raise NLError(f"사전 {lineno}행: 모르는 층 {layer}")
            if status not in STATUSES:
                raise NLError(f"사전 {lineno}행: 모르는 상태 {status}")
            if tag in entries:
                raise NLError(f"사전 {lineno}행: 태그 중복 {tag}")
            entries[tag] = Entry(tag, layer, source, usage, rdate, status)
    if version is None:
        raise NLError("사전에 @DICT 판본이 없음")
    return Dictionary(version=version, date=date or "", entries=entries)


# ---------------------------------------------------------------- 전문 조립·파싱

def _body_hash(body_lines):
    return hashlib.sha256("\n".join(body_lines).encode("utf-8")).hexdigest()[:12]


ROOTS = {"T", "W", "S", "R"}        # 주소 뿌리: 타일·창고·세션·기록 (문법 §11)
DELTA_OPS = {"=", "+", "-"}


def _delta_line(addr, op, value, base=None):
    line = f"@{addr} {op}"
    if value:
        line += f" {value}"
    if base:
        line += f" #{base}"
    return line


_BASE_TAIL_RE = re.compile(r"\s#([0-9a-f]{8})$")


def _parse_delta_line(bl):
    """델타 줄을 결정적으로 나눈다: 꼬리 해시 분리 → 주소·연산·값 순서 분리."""
    base = None
    m = _BASE_TAIL_RE.search(bl)
    if m:
        base = m.group(1)
        bl = bl[:m.start()]
    parts = bl.split(" ", 2)
    if len(parts) < 2 or parts[1] not in DELTA_OPS:
        raise NLError(f"델타 줄 형식 위반: {bl[:40]}")
    addr = parts[0][1:]
    value = parts[2] if len(parts) > 2 else ""
    return addr, parts[1], value, base


def compose(body, dictionary, sid="-", layer="code", dict_version=None,
            deltas=None, map_version=None):
    """body: [(키, 값)], deltas: [(주소, 연산, 값, 기준해시|None)] → 전문.

    키는 사전 등록 태그만 허용한다. 본문 줄 순서는 적용 순서다.
    map_version을 주면 머리에 공유 주소 지도 판본(MAP)을 선언한다.
    """
    lines = []
    for key, value in body:
        if key not in dictionary.entries:
            raise NLError(f"미등록 키: {key}")
        if "\n" in str(value):
            raise NLError("값에 줄바꿈은 쓸 수 없다 (한 줄 = 한 규칙)")
        lines.append(f"{key}={value}")
    for addr, op, value, base in (deltas or []):
        if addr.split("/")[0] not in ROOTS or op not in DELTA_OPS:
            raise NLError(f"델타 형식 위반: @{addr} {op}")
        if "\n" in str(value):
            raise NLError("델타 값에 줄바꿈은 쓸 수 없다")
        lines.append(_delta_line(addr, op, value, base))
    head = ["@NL 1.0",
            f"DICT 사전_v1@{dict_version or dictionary.version}",
            f"SID {sid}",
            f"LAYER {layer}"]
    if map_version:
        head.append(f"MAP {map_version}")
    head.append("---")
    return "\n".join(head + lines + [f"#H={_body_hash(lines)}"])


@dataclass
class Message:
    dict_version: str
    sid: str
    layer: str
    body: list = field(default_factory=list)      # [(키, 값)] 상태 줄
    deltas: list = field(default_factory=list)    # [(주소, 연산, 값, 기준해시|None)]
    map_version: str = None
    hash_ok: bool = False


_KEYVAL_RE = re.compile(r"^([^=]{1,24})=(.*)$")


def parse(text, dictionary, verify_hash=True):
    """전문을 결정적으로 파싱한다. 위반은 NLError.

    본문 줄이 '@'로 시작하면 델타 줄, 아니면 상태 줄(키=값)로 읽는다.
    """
    lines = (text or "").split("\n")
    if len(lines) < 6 or lines[0].strip() != "@NL 1.0":
        raise NLError("전문 머리가 @NL 1.0으로 시작하지 않음")
    if not lines[1].startswith("DICT "):
        raise NLError("DICT 줄이 없음")
    dict_version = lines[1][5:].strip()
    if not lines[2].startswith("SID "):
        raise NLError("SID 줄이 없음")
    sid = lines[2][4:].strip()
    if not lines[3].startswith("LAYER "):
        raise NLError("LAYER 줄이 없음")
    layer = lines[3][6:].strip()
    idx = 4
    map_version = None
    if lines[idx].startswith("MAP "):
        map_version = lines[idx][4:].strip()
        idx += 1
    if lines[idx].strip() != "---":
        raise NLError("머리/본문 경계(---)가 없음")
    if not lines[-1].startswith("#H="):
        raise NLError("꼬리 해시(#H=)가 없음")
    body_lines = lines[idx + 1:-1]
    hash_ok = _body_hash(body_lines) == lines[-1][3:].strip()
    if verify_hash and not hash_ok:
        raise NLError("본문 해시 불일치 — 전문이 변조됐거나 깨졌다")
    body, deltas = [], []
    for bl in body_lines:
        if bl.startswith("@"):
            addr, op, value, base = _parse_delta_line(bl)
            if addr.split("/")[0] not in ROOTS:
                raise NLError(f"모르는 주소 뿌리: {addr}")
            deltas.append((addr, op, value, base))
            continue
        m = _KEYVAL_RE.match(bl)
        if not m:
            raise NLError(f"본문 줄 형식 위반: {bl[:40]}")
        key, value = m.group(1), m.group(2)
        if key not in dictionary.entries:
            raise NLError(f"미등록 키: {key}")
        body.append((key, value))
    return Message(dict_version=dict_version, sid=sid, layer=layer,
                   body=body, deltas=deltas, map_version=map_version,
                   hash_ok=hash_ok)


# ---------------------------------------------------------------- 복원 ↔ 태그화

def _tag_pattern(dictionary):
    """값 안의 독립 태그 토큰을 찾기 위한 패턴 (긴 태그 우선).

    태그는 구분자(공백·|·:·=·괄호 등)로 둘러싸인 독립 토큰일 때만 치환한다.
    조사(를·을 등)가 바로 붙은 형태는 치환하지 않는다 — 전문의 값에서는
    태그를 독립 토큰으로 쓰는 것이 문법의 작성 관례다.
    """
    tags = sorted(dictionary.entries.keys(), key=len, reverse=True)
    alt = "|".join(re.escape(t) for t in tags)
    return re.compile(r"(?<![^\s|:\[\]()=,·])(" + alt + r")(?![^\s|:\[\]()=,·])")


def _expand_value(value, dictionary):
    """따옴표 밖의 태그 토큰을 원문으로 치환한다."""
    if value.startswith('"'):
        return value                      # 보호 인용은 손대지 않는다
    pat = _tag_pattern(dictionary)

    def _sub(m):
        e = dictionary.entries.get(m.group(1))
        return e.source if e else m.group(1)
    return pat.sub(_sub, value)


def restore(msg, dictionary):
    """파싱된 전문을 원문 렌더링으로 복원한다 (키 원문 + 값의 태그 확장)."""
    out = []
    for key, value in msg.body:
        e = dictionary.entries.get(key)
        label = e.source if e else key
        out.append(f"{label}={_expand_value(value, dictionary)}")
    return "\n".join(out)


def _contract_value(value, dictionary):
    """따옴표 밖의 원문 구절을 태그로 치환한다 (긴 구절 우선)."""
    if value.startswith('"'):
        return value
    out = value
    for phrase in dictionary.phrases():
        if len(phrase) < 2:
            continue
        tag = next(t for t, e in dictionary.entries.items() if e.source == phrase)
        out = out.replace(phrase, tag)
    return out


def tagify(text, dictionary):
    """원문 렌더링(라벨=값 줄들)을 태그 전문 본문으로 되돌린다.

    라벨(첫 '=' 앞부분)이 사전 원문과 일치하면 그 태그로 바꾸고,
    값 안의 원문 구절도 태그로 치환한다. 왕복 검사의 한쪽 방향이다.
    """
    by_source = {}
    for t, e in dictionary.entries.items():
        by_source.setdefault(e.source, t)
    out = []
    for line in (text or "").split("\n"):
        if not line.strip():
            continue
        m = _KEYVAL_RE.match(line)
        if not m:
            raise NLError(f"원문 줄 형식 위반: {line[:40]}")
        label, value = m.group(1), m.group(2)
        key = by_source.get(label, label)
        out.append(f"{key}={_contract_value(value, dictionary)}")
    return "\n".join(out)


def roundtrip_check(plain_text, dictionary):
    """원문 렌더링 → 태그화 → 복원 → 원문과 같은지 검사한다.

    반환: (통과 여부, 진단 문자열). 신규 태그 등록의 필수 증거 (문법 §7).
    """
    try:
        tagged = tagify(plain_text, dictionary)
        body = []
        for line in tagged.split("\n"):
            m = _KEYVAL_RE.match(line)
            body.append((m.group(1), m.group(2)))
        msg = parse(compose(body, dictionary), dictionary)
        back = restore(msg, dictionary)
    except NLError as exc:
        return False, f"왕복 중 오류: {exc}"
    norm = lambda s: "\n".join(l.rstrip() for l in s.strip().split("\n"))
    if norm(back) == norm(plain_text):
        return True, "원문 → 태그 → 복원이 원문과 일치"
    return False, f"불일치\n--- 복원 ---\n{back}\n--- 원문 ---\n{plain_text}"


# ------------------------------------------------- 공유 상태·델타 엔진 (문법 §11)

def state_hash(value):
    """주소 값의 기준 해시 (SHA-256 앞 8자)."""
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:8]


def diff_state(before, after):
    """두 상태(주소→값 dict)의 차이를 델타 목록으로 만든다. 결정적 순서."""
    deltas = []
    for addr in sorted(set(before) | set(after)):
        if addr not in after:
            deltas.append((addr, "-", "", state_hash(before[addr])))
        elif addr not in before:
            deltas.append((addr, "+", after[addr], None))
        elif before[addr] != after[addr]:
            deltas.append((addr, "=", after[addr], state_hash(before[addr])))
    return deltas


def state_digest(state):
    """동기화 2단계의 해시 목록: 주소 → 기준 해시. 내용은 담지 않는다."""
    return {addr: state_hash(v) for addr, v in state.items()}


def sync_plan(local_state, remote_digest):
    """상대 해시 목록만으로 동기화 델타를 산출한다 (문법 §12).

    반환 델타를 상대 상태에 적용하면 local_state와 같아진다.
    어긋난 주소의 값만 델타에 실린다 — 나머지는 이동하지 않는다.
    """
    deltas = []
    for addr in sorted(set(local_state) | set(remote_digest)):
        if addr not in remote_digest:
            deltas.append((addr, "+", local_state[addr], None))
        elif addr not in local_state:
            deltas.append((addr, "-", "", remote_digest[addr]))
        elif state_hash(local_state[addr]) != remote_digest[addr]:
            deltas.append((addr, "=", local_state[addr],
                           remote_digest[addr]))
    return deltas


def apply_delta(state, deltas):
    """델타를 상태에 적용해 새 상태를 돌려준다.

    기준 해시가 현재 값과 다르면(오래된 상태 위의 쓰기) NLError로 거부한다.
    '+'는 없는 주소에만, '-'는 있는 주소에만 쓸 수 있다.
    """
    out = dict(state)
    for addr, op, value, base in deltas:
        if op == "+":
            if addr in out:
                raise NLError(f"델타 '+': 이미 있는 주소 {addr}")
            out[addr] = value
        elif op == "=":
            if addr not in out:
                raise NLError(f"델타 '=': 없는 주소 {addr}")
            if base and state_hash(out[addr]) != base:
                raise NLError(f"델타 '=': 기준 해시 불일치 {addr} — "
                              "오래된 상태 위의 쓰기를 거부")
            out[addr] = value
        elif op == "-":
            if addr not in out:
                raise NLError(f"델타 '-': 없는 주소 {addr}")
            if base and state_hash(out[addr]) != base:
                raise NLError(f"델타 '-': 기준 해시 불일치 {addr}")
            del out[addr]
        else:
            raise NLError(f"모르는 델타 연산 {op}")
    return out


# ---------------------------------------------------------------- 에코 탐지 (문법 §8)

def _assign_re(dictionary):
    tags = sorted((t for t in dictionary.entries
                   if not t.startswith("[")), key=len, reverse=True)
    alt = "|".join(re.escape(t) for t in tags)
    return re.compile(r"^\s*(?:" + alt + r")\s*=\s*\S")


def detect_echo(output, dictionary):
    """모델 답변에서 사전 에코를 탐지한다. 반환: hit 목록(빈 목록 = 정상)."""
    text = output or ""
    hits = []
    # ① 사전 원문 구절이 답변에 그대로 등장 (가장 강한 신호)
    for phrase in dictionary.phrases():
        if len(phrase) >= 4 and phrase in text:
            hits.append({"type": "dict_phrase", "detail": phrase})
    # ② 등록 태그 할당 줄이 2줄 이상
    are = _assign_re(dictionary)
    n_assign = sum(1 for l in text.split("\n") if are.match(l))
    if n_assign >= 2:
        hits.append({"type": "assign_lines", "detail": n_assign})
    # ③ 화자 접두·사전 구획 표지로 시작하거나 사전 블록이 통째로 등장
    stripped = text.lstrip()
    if stripped.startswith(("A:", "U:")):
        hits.append({"type": "speaker_prefix", "detail": stripped[:2]})
    if "[µ사전]" in text:
        hits.append({"type": "dict_block", "detail": "[µ사전]"})
    for scaffold in ("[타일|T]", "[신뢰도]"):
        if scaffold in text:
            hits.append({"type": "scaffold", "detail": scaffold})
    return hits


# ------------------------------------- 이웃 추론·결손 복원 (문법 §13 부칙)
#
# 설계 스켈레톤이다. 전부 코드 층의 결정 연산이며 추측으로 값을 만들지
# 않는다: 후보는 이웃이 수학적으로 좁힐 때만 생기고, 확신도는
# 충실도 × 일치도로 계산하며, 임계(τ) 미만이면 채택 대신 재동기화
# 요청을 돌려준다. 복원값은 실값이 아니므로 해시를 만들지 않는다.

CONFIDENCE_THRESHOLD = 0.75     # 채택 임계 τ (문법 §13.2 — 근거는 정본 참조)
MIN_NEIGHBOR_EVIDENCE = 4       # 최소 증거: 있는 이웃이 이 수 미만이면 무조건 불채택
_MAJORITY_HOLD = 0.75           # 배치 검증: 이웃 다수 판정 비율 (문법 §13.3)
_NUMERIC_HOLD_DEVIATION = 0.5   # 배치 검증: 중앙값 상대 편차 상한 (문법 §13.3)


def grid_coord(addr):
    """격자 주소면 (뿌리, 구역, 행, 열), 아니면 None. (문법 §13.0)

    격자는 타일 뿌리의 `@T/<구역>/<행>/<열>` 꼴뿐이다. 상태 dict의
    주소는 '@' 없는 형태("T/구역/3/4")로 다룬다.
    """
    parts = str(addr).split("/")
    if len(parts) != 4 or parts[0] != "T":
        return None
    if not (parts[2].isdigit() and parts[3].isdigit()):
        return None
    return parts[0], parts[1], int(parts[2]), int(parts[3])


def grid_neighbors(addr):
    """같은 구역 안 8이웃 주소 목록. 격자 주소가 아니면 빈 목록."""
    coord = grid_coord(addr)
    if coord is None:
        return []
    root, zone, row, col = coord
    out = []
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            r, c = row + dr, col + dc
            if r >= 0 and c >= 0:
                out.append(f"{root}/{zone}/{r}/{c}")
    return out


def _as_number(value):
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _fmt_number(x, integer_form):
    if integer_form and float(x).is_integer():
        return str(int(x))
    return str(x)


def _median(nums):
    s = sorted(nums)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


@dataclass
class Reconstruction:
    addr: str
    value: object = None            # 복원 후보값 (없으면 None)
    confidence: float = 0.0
    method: str = ""                # 순서 보간 | 수치 중앙값 | 범주 다수결 | 해시 확정
    evidence: dict = field(default_factory=dict)
    adopted: bool = False           # 잠정 채택 여부 (확신도·최소 증거 통과)
    confirmed: bool = False         # 기준 해시 일치로 확정됨
    needs_resync: bool = True       # True면 §12 재동기화로 되돌릴 것


def reconstruct_hole(state, addr, known_hash=None):
    """빈 주소 하나를 이웃으로 복원 시도한다. (문법 §13.1)

    state: 주소→값 dict (그 주소는 없어야 한다).
    known_hash: 그 주소의 기준 해시(해시 목록에서 아는 경우). 후보의
    해시가 일치하면 추론이 아니라 확정이다.
    반환 Reconstruction — adopted가 False면 값을 쓰지 말고
    needs_resync를 따라 재동기화를 요청하라.
    """
    if addr in state:
        raise NLError(f"복원 대상이 결손이 아님: {addr}")
    rec = Reconstruction(addr=addr)
    neighbors = grid_neighbors(addr)
    if not neighbors:
        rec.method = "비격자 주소 — 이웃 없음"
        return rec
    present = [a for a in neighbors if a in state]
    possible = len(neighbors)
    coverage = len(present) / possible if possible else 0.0
    ev = {"이웃_있음": len(present), "이웃_가능": possible,
          "충실도": round(coverage, 4)}
    rec.evidence = ev
    if not present:
        rec.method = "이웃 전무"
        return rec
    values = [state[a] for a in present]
    nums = [_as_number(v) for v in values]
    candidate, agreement, method = None, 0.0, ""

    coord = grid_coord(addr)
    root, zone, row, col = coord
    left = state.get(f"{root}/{zone}/{row}/{col - 1}") if col >= 1 else None
    right = state.get(f"{root}/{zone}/{row}/{col + 1}")
    ln, rn = _as_number(left), _as_number(right)
    if ln is not None and rn is not None:
        # 순서 보간: 같은 행 좌우가 값을 직접 정한다 (문법 §13.1)
        candidate = (ln + rn) / 2.0
        method = "순서 보간"
        l2 = _as_number(state.get(f"{root}/{zone}/{row}/{col - 2}")) \
            if col >= 2 else None
        r2 = _as_number(state.get(f"{root}/{zone}/{row}/{col + 2}"))
        if l2 is not None and r2 is not None:
            inner = abs(rn - ln)
            outer_half = abs(r2 - l2) / 2.0
            scale = max(inner, 1.0)
            agreement = 1.0 if abs(outer_half - inner) / scale <= 0.1 else 0.75
        elif l2 is not None or r2 is not None:
            agreement = 0.9
        else:
            agreement = 0.85
        # 분포 정합 보정: 보간 후보가 이웃 전체의 중앙값에서 크게 벗어나면
        # 그 행만으로는 신뢰할 수 없다 — 일치도를 절반으로 깎는다.
        allnums = [n for n in nums if n is not None]
        if allnums:
            med_all = _median(allnums)
            if abs(candidate - med_all) / max(abs(med_all), 1.0) \
                    > _NUMERIC_HOLD_DEVIATION:
                agreement *= 0.5
        candidate = _fmt_number(candidate,
                                all(float(n).is_integer() for n in (ln, rn)))
    elif all(n is not None for n in nums):
        med = _median(nums)
        spread = max(nums) - min(nums)
        scale = max(abs(med), 1.0)
        agreement = max(0.0, min(1.0, 1.0 - spread / scale))
        method = "수치 중앙값"
        candidate = _fmt_number(med, all(str(v).replace(",", "").strip()
                                         .lstrip("-").isdigit()
                                         for v in values))
    else:
        counts = {}
        for v in values:
            counts[str(v)] = counts.get(str(v), 0) + 1
        top = max(counts.values())
        winners = sorted(v for v, c in counts.items() if c == top)
        if len(winners) > 1:
            rec.method = "범주 동률 — 후보를 하나로 좁힐 수 없음"
            rec.evidence = ev
            return rec
        candidate = winners[0]
        agreement = top / len(values)
        method = "범주 다수결"

    confidence = coverage * agreement
    rec.value, rec.method = candidate, method
    rec.confidence = round(confidence, 4)
    ev["일치도"] = round(agreement, 4)

    if known_hash is not None and candidate is not None \
            and state_hash(candidate) == known_hash:
        # 후보가 기준 해시와 일치 — 추론이 증명으로 바뀐다 (문법 §13.1-2)
        rec.confidence, rec.method = 1.0, method + " + 해시 확정"
        rec.adopted, rec.confirmed, rec.needs_resync = True, True, False
        return rec

    if len(present) >= MIN_NEIGHBOR_EVIDENCE \
            and confidence >= CONFIDENCE_THRESHOLD:
        rec.adopted, rec.needs_resync = True, False
    return rec


def validate_tile_placement(state, addr, value):
    """새 타일 배치의 이웃 정합 검증. (문법 §13.3)

    반환 dict: 판정(확정|보류|미검증), 사유, 복원후보.
    이웃은 값을 고치지 않는다 — 모순이면 보류와 후보 제시까지만 한다.
    """
    neighbors = [a for a in grid_neighbors(addr) if a in state]
    if len(neighbors) < MIN_NEIGHBOR_EVIDENCE:
        return {"판정": "미검증", "사유": "이웃 증거 부족 — 검증 생략",
                "복원후보": None}
    values = [state[a] for a in neighbors]
    vnum = _as_number(value)
    nums = [n for n in (_as_number(v) for v in values) if n is not None]
    if vnum is not None and len(nums) >= len(values) / 2:
        med = _median(nums)
        deviation = abs(vnum - med) / max(abs(med), 1.0)
        if deviation > _NUMERIC_HOLD_DEVIATION:
            return {"판정": "보류",
                    "사유": f"수치 모순: 이웃 중앙값 {med}와 상대 편차 "
                            f"{deviation:.2f} > {_NUMERIC_HOLD_DEVIATION}",
                    "복원후보": _fmt_number(med, float(med).is_integer())}
        return {"판정": "확정", "사유": "이웃 수치 분포와 정합",
                "복원후보": None}
    counts = {}
    for v in values:
        counts[str(v)] = counts.get(str(v), 0) + 1
    top_value, top_count = max(counts.items(), key=lambda kv: kv[1])
    if top_count / len(values) >= _MAJORITY_HOLD and str(value) != top_value:
        return {"판정": "보류",
                "사유": f"범주 모순: 이웃 {top_count}/{len(values)}가 "
                        f"'{top_value}'",
                "복원후보": top_value}
    return {"판정": "확정", "사유": "이웃 분포와 정합", "복원후보": None}


_IRREVERSIBLE_ACTIONS = {"실행", "단정", "발송", "예약", "결제", "삭제"}


def make_preparation(content, basis_addrs, expires=None):
    """의도 준비 기록을 만든다 — 제안 형태만 허용한다. (문법 §13.4)

    되돌릴 수 없는 동작은 '준비'로도 만들 수 없고, 근거 주소가 없는
    추론은 제안이 되지 못한다. 위반은 NLError.
    """
    if not basis_addrs:
        raise NLError("근거 주소 없는 추론은 제안으로 만들지 않는다 (§13.4-3)")
    return {"형태": "제안", "내용": content, "근거": list(basis_addrs),
            "취소가능": True, "만료": expires, "실행됨": False}


def guard_preparation_only(record, action_kind):
    """준비 기록으로 하려는 동작이 '제안' 범위를 넘으면 거부한다."""
    if action_kind in _IRREVERSIBLE_ACTIONS or action_kind != "제안":
        raise NLError(f"의도 준비는 제안까지만 — '{action_kind}'은 금지 (§13.4)")
    if not record.get("취소가능") or record.get("실행됨"):
        raise NLError("취소 불가능하거나 이미 실행된 준비 기록 (§13.4-2)")
    return True


# ------------------------------------- 얽힘 동기화·덩어리 법칙 (문법 §14 부칙)
#
# 설계 스켈레톤이다. 얽힘은 의미로 명시해 맺는 관계라 좌표(§13 이웃)와
# 무관하다. 이 층의 함수들은 값을 복사하지 않는다: 동기화의 범위와
# 순서를 계산하고, 전파 후보는 안전장치를 거쳐 보류로만 돌려준다.
# 실측 근거 — T3 얽힘 자동 갱신(2026-11-01): 소실 0건·원본 보존은
# 성공(안전장치 채택), 전파 품질 2/3이라 자동 갱신은 조건부 후보.

ENTANGLE_PREFIX = "R/얽힘/"     # 얽힘 집합 정의 주소 접두 (문법 §14.1)


def entangle_sets(state):
    """상태에서 얽힘 집합 정의를 읽는다. (문법 §14.1)

    집합 정의는 주소 `R/얽힘/<집합ID>`에 원소 주소 목록(쉼표 구분)을
    값으로 둔다. 반환: (집합 {ID: [주소...]}, 역색인 {주소: [ID...]}).
    집합 정의 주소를 원소로 쓰는 중첩 선언은 NLError로 거부한다.
    """
    sets, index = {}, {}
    for addr in sorted(state):
        if not addr.startswith(ENTANGLE_PREFIX):
            continue
        set_id = addr[len(ENTANGLE_PREFIX):]
        if not set_id:
            raise NLError(f"얽힘 집합 ID가 비어 있음: {addr}")
        members = []
        for raw in str(state[addr]).split(","):
            m = raw.strip()
            if not m:
                continue
            if m.startswith(ENTANGLE_PREFIX):
                raise NLError(f"얽힘 집합의 원소에 집합 정의 주소는 "
                              f"쓸 수 없다: {m} (집합 {set_id})")
            if m not in members:
                members.append(m)
        sets[set_id] = members
        for m in members:
            index.setdefault(m, []).append(set_id)
    return sets, index


def entangled_closure(addr, sets, index):
    """전파 범위: 그 주소가 속한 모든 집합의 합집합. (문법 §14.2-2)

    한 사건의 범위는 직접 집합까지만이다 — 합집합 안에서 생긴 2차
    변경의 연쇄는 다음 사건으로 분리하므로 여기서 확장을 잇지 않는다.
    주소 자체는 항상 포함된다. 결정적 순서(정렬)로 돌려준다.
    """
    out = {addr}
    for set_id in index.get(addr, []):
        out.update(sets[set_id])
    return sorted(out)


def entanglement_sync_plan(changed_addrs, local_state, remote_digest):
    """얽힘 집합 단위 전파를 반영한 동기화 계획. (문법 §14.2)

    §12 sync_plan의 델타를 그대로 쓰되, 변경 주소들의 얽힘 범위
    (수렴 대상)에 속한 델타를 앞으로 당겨 최우선 적용 순서를 만든다.
    반환: {범위, 수렴대상, 델타, 표식} — 표식은 전파 사건 기록
    (문법 §14.2-7)의 골격이다. 값 적용은 apply_delta가 기준 해시로
    검증하므로, 충돌하는 델타는 그 자리에서 거부된다.
    """
    sets, index = entangle_sets(local_state)
    scope = set()
    for a in changed_addrs:
        scope.update(entangled_closure(a, sets, index))
    plan = sync_plan(local_state, remote_digest)
    head = [d for d in plan if d[0] in scope]
    tail = [d for d in plan if d[0] not in scope]
    return {"범위": sorted(scope),
            "수렴대상": sorted(d[0] for d in head),
            "델타": head + tail,
            "표식": {"근원": list(changed_addrs), "확신도": "미측정"}}


# 타일 엔진 propagate_update의 안전장치 기준을 그대로 승계한다 (§14.2-6)
_PROPAGATION_MIN_LEN = 8


def propagation_candidates(state, changed_addr, rewrite_fn,
                           derived_addrs=None):
    """파생 주소의 자동 전파 갱신 후보를 만든다. (문법 §14.2-6)

    얽힌 주소 중 derived_addrs로 선언된 파생 주소에만 후보를 만든다.
    안전장치: 후보가 비었거나 원문 대비 과도하게 짧으면, 또는 전파
    함수가 실패하면 원본을 유지한다 (T3 실측 — 소실 0건·원본 보존).
    가드를 통과한 후보도 자동 채택하지 않는다: 모델 재작성 후보는
    확신도를 측정할 수 없어 '전파' 표식과 함께 보류로만 돌려준다
    (T3 전파 품질 2/3 — 자동 갱신은 조건부 후보).
    반환: 보류·유지 항목 목록 [{주소, 원문, 후보, 판정, 사유, 확신도, 표식}]
    """
    sets, index = entangle_sets(state)
    derived = set(derived_addrs or [])
    new_text = state.get(changed_addr, "")
    out = []
    for addr in entangled_closure(changed_addr, sets, index):
        if addr == changed_addr or addr not in derived or addr not in state:
            continue
        original = state[addr]
        item = {"주소": addr, "원문": original, "후보": None,
                "판정": "원본유지", "사유": "", "확신도": "미측정",
                "표식": "전파"}
        try:
            cand = rewrite_fn(original, new_text)
        except Exception as exc:  # noqa: BLE001 — 실패해도 원본 보존이 원칙
            item["사유"] = f"전파 함수 실패 — 원본 보존: {exc}"
            out.append(item)
            continue
        if not cand or not cand.strip():
            item["사유"] = "빈 후보 — 원본 보존 (T3 안전장치)"
        elif len(cand) < max(_PROPAGATION_MIN_LEN, len(original) * 0.3):
            item["사유"] = "과도 축소 후보 — 원본 보존 (T3 안전장치)"
        else:
            item.update({"후보": cand, "판정": "보류",
                         "사유": "모델 재작성 후보는 자동 채택하지 않는다 "
                                 "— 확신도 미측정 (§14.2-6, T3 품질 2/3)"})
        out.append(item)
    return out


_CLUSTER_TOKEN_RE = re.compile(r"[가-힣a-zA-Z0-9]{2,}")


def _cluster_tokens(text):
    return set(t.lower() for t in _CLUSTER_TOKEN_RE.findall(text or ""))


def retrieve_cluster(state, seed_addr, query=None, present_limit=None):
    """덩어리 법칙 — 핵심이 속한 얽힘 집합 전원을 한 줄기로 준비한다.
    (문법 §14.3)

    인출 단위는 낱개가 아니라 덩어리 전원이며, 인출은 §13.4의 준비다.
    사용자에게 닿는 제시 후보는 질의 적합도(토큰 겹침, 타일 엔진 인출
    점수 방식 준용)로 코드가 고른다 — 핵심은 점수와 무관하게 항상
    제시에 포함된다. 질의가 없으면 줄기 전체가 제시 후보다.
    반환: {핵심, 덩어리(줄기 순서), 제시[(주소, 점수)], 준비(§13.4 기록)}
    """
    sets, index = entangle_sets(state)
    members = entangled_closure(seed_addr, sets, index)
    stem = [seed_addr] + [a for a in members if a != seed_addr]
    if query:
        qtok = _cluster_tokens(query)
        scored = []
        for addr in stem:
            toks = _cluster_tokens(state.get(addr, ""))
            score = sum(len(t) * 2 for t in qtok if t in toks)
            scored.append((addr, score))
        ranked = sorted(scored, key=lambda kv: (-kv[1], kv[0]))
        present = [(a, s) for a, s in ranked if s > 0 or a == seed_addr]
    else:
        present = [(a, 0) for a in stem]
    if present_limit:
        kept = present[:present_limit]
        if seed_addr not in [a for a, _ in kept]:
            # §14.3-3: 핵심은 점수와 무관하게 항상 제시에 포함된다 —
            # 절단이 핵심을 잘라내면 마지막 자리를 핵심과 바꾼다.
            seed_entry = [(a, s) for a, s in present if a == seed_addr]
            if seed_entry:
                kept = kept[:present_limit - 1] + seed_entry
        present = kept
    prep = make_preparation(f"덩어리 법칙 준비: {seed_addr}", stem)
    return {"핵심": seed_addr, "덩어리": stem, "제시": present, "준비": prep}


# ------------------------------------- 법칙 체계 (문법 §15 부칙)
#
# 법칙은 상시 전원이 아니라 장부다. 전부 적용하되 간섭이 일어나지
# 않도록: 법칙마다 관할 층이 하나이고, 층 안에서는 측면·국면·대상이
# 갈리며, 상황마다 라우팅 표가 골라 부른다. 이 절의 자료구조가 그
# 장부·행렬·라우팅·게이트의 실행형이다 — 쌍 판정은 여기서 한 번만
# 정의하고, 정본 §15.4의 행렬은 이 정의와 일치해야 한다.

LAW_LAYERS = ("주소", "동기화", "인출", "판정", "저장")

LAWS = [
    {"코드": "ENT", "이름": "얽힘", "층": "동기화", "측면": "범위",
     "상황": "얽힌 원소의 확정 변경",
     "지표": "사건당 수렴 완료율·충돌 건수"},
    {"코드": "SUP", "이름": "중첩", "층": "판정", "측면": "유지 국면",
     "상황": "후보가 여럿인 복원·검수 판정 전",
     "지표": "붕괴 후 실값 대조 적중률"},
    {"코드": "INT", "이름": "간섭(결맞음)", "층": "판정", "측면": "평가 국면",
     "상황": "복수 신호가 한 대상을 판정할 때",
     "지표": "실값 대조 오판율"},
    {"코드": "OBS", "이름": "관측 효과", "층": "인출", "측면": "기록",
     "상황": "모든 인출·해시 대조",
     "지표": "쓰임 기록 누락률 (목표 0)"},
    {"코드": "LEAP", "이름": "양자 도약", "층": "동기화", "측면": "형태",
     "상황": "모든 상태 변경",
     "지표": "변경 총수 = 사건 수 대조"},
    {"코드": "EXC", "이름": "배타 원리", "층": "주소", "측면": "점유",
     "상황": "모든 쓰기·적용",
     "지표": "주소당 확정값 1개 불변식 위반 건수 (목표 0)"},
    {"코드": "RES", "이름": "공명", "층": "저장", "측면": "점수",
     "상황": "주기 승격 심사",
     "지표": "승격 후 인출 적중률 변화·오승격률"},
    {"코드": "PHA", "이름": "상전이", "층": "저장", "측면": "표식",
     "상황": "규모 임계 도달",
     "지표": "임계 판정 전후 지표 추이"},
    {"코드": "ETP", "이름": "엔트로피", "층": "저장", "측면": "값형",
     "상황": "주기 정리",
     "지표": "저장 토큰 추이·§10 복원 하한 유지"},
    {"코드": "ACT", "이름": "최소작용", "층": "판정", "측면": "경로(정상)",
     "상황": "경로·전문 구성 결정",
     "지표": "경로당 평균 비용 (토큰+단계)"},
    {"코드": "REL", "이름": "상대성", "층": "동기화", "측면": "순서",
     "상황": "모든 동기화·충돌 정렬",
     "지표": "양쪽 장부의 사건 순서 일치율"},
    {"코드": "GRV", "이름": "중력", "층": "인출", "측면": "순서",
     "상황": "복수 덩어리가 인출 후보일 때",
     "지표": "인출 상한 내 질의 적합도 총합"},
    {"코드": "FRC", "이름": "프랙탈", "층": "주소", "측면": "형식",
     "상황": "주소 신규 부여·구역 개편",
     "지표": "주소 형식 검증 통과율"},
    {"코드": "TUN", "이름": "터널링", "층": "판정", "측면": "경로(장벽)",
     "상황": "직행 경로가 장벽에 막힐 때",
     "지표": "장벽 대비 우회 성공률·무결성 위반 0"},
]

LAW_CODES = [law["코드"] for law in LAWS]
_LAYER_COUNTS = {"주소": 2, "동기화": 3, "인출": 2, "판정": 4, "저장": 3}

# 쌍 판정 장부: 여기에 없는 쌍은 '무간섭'이다. '간섭'(●)은 해소법이
# 없으면 등록 자체가 성립하지 않고, '접점'(◐)은 분리법이 함께 적힌다.
# 판정 기호는 정본 §15.4 행렬과 같다: ● 간섭 / ◐ 접점(분리 해소) / · 무간섭.
PAIR_VERDICTS = {
    frozenset(("ENT", "RES")): ("간섭",
        "제안/선언 분리 — 공명은 얽힘 '제안'까지만, 얽힘은 선언으로만 (§14.1-3)"),
    frozenset(("SUP", "INT")): ("간섭",
        "국면 순서 고정 — 유지(중첩) → 평가(간섭) → 확정(붕괴). "
        "평가가 시작되면 후보 추가를 동결한다"),
    frozenset(("SUP", "EXC")): ("간섭",
        "지위 분리 — 배타는 확정값에만 적용하고, 후보는 확정 밖 지위"
        "(표식·장부)로 존재한다"),
    frozenset(("RES", "ETP")): ("간섭",
        "순서 고정(공명 산정 → 엔트로피 정리) + 보존 조건(공명 하한 "
        "미만만 정리 대상) + 쓰기 분리(공명은 점수만, 엔트로피는 "
        "압축만 — 삭제·주소 변경 없음)"),
    frozenset(("ACT", "TUN")): ("간섭",
        "발동 조건 상호 배제 — 장벽이 없으면 최소작용만, 장벽이 "
        "확인되면 터널링만. 동시 발동 금지"),
    frozenset(("ENT", "SUP")): ("접점",
        "지위 분리 — 전파 후보는 보류 장부('전파' 표식), 판정 후보는 중첩 장부"),
    frozenset(("ENT", "LEAP")): ("접점",
        "측면 분리 — 얽힘은 전파 범위, 도약은 전이 형태. 전파 단위는 사건"),
    frozenset(("ENT", "PHA")): ("접점",
        "국면 종속 — 상전이 표식이 동기화 기본 국면을 정하되 얽힘 범위 계산은 불변"),
    frozenset(("ENT", "ETP")): ("접점",
        "보존 조건 — 전파 기록의 근원·결과 필드는 엔트로피 정리에서 제외"),
    frozenset(("ENT", "ACT")): ("접점",
        "최적화 제외 — 얽힘 전파 범위는 최소작용의 단축 대상이 아니다"),
    frozenset(("ENT", "REL")): ("접점",
        "측면 분리 — 얽힘은 범위, 상대성은 순서"),
    frozenset(("ENT", "GRV")): ("접점",
        "읽기 전용 — 중력은 얽힘 집합 구조를 읽기만 하고 쓰지 않는다"),
    frozenset(("ENT", "TUN")): ("접점",
        "범위 불변 — 터널링은 경로만 바꾸고 전파 범위는 얽힘이 정한 그대로"),
    frozenset(("SUP", "LEAP")): ("접점",
        "시간축 분리 — 유지 국면이 끝나 확정되는 순간만 도약 사건이 된다"),
    frozenset(("SUP", "ETP")): ("접점",
        "정리 제외 — 아직 붕괴하지 않은 후보는 엔트로피 정리 대상이 아니다"),
    frozenset(("SUP", "ACT")): ("접점",
        "대상 분리(값 유지/경로) + 순서 고정(경로 결정 → 후보 수집·유지)"),
    frozenset(("SUP", "TUN")): ("접점",
        "순서 고정 — 터널링 인입 후에만 중첩 유지. 유지 중인 후보 집합을 "
        "터널링이 직접 바꾸지 않는다"),
    frozenset(("INT", "EXC")): ("접점",
        "순서 고정 — 간섭 판정 → 배타 게이트 → 확정. 간섭이 배타를 우회해 쓰지 않는다"),
    frozenset(("INT", "ETP")): ("접점",
        "보존 조건 — 판정 기록의 신호 근거 필드는 정리에서 보존"),
    frozenset(("INT", "ACT")): ("접점",
        "대상 분리(판정 신호/경로) + 순서 고정(경로 결정 → 신호 평가)"),
    frozenset(("INT", "TUN")): ("접점",
        "순서 고정 — 터널링으로 인입된 신호도 간섭 평가를 거친다 (평가 생략 없음)"),
    frozenset(("OBS", "LEAP")): ("접점",
        "쓰기 분리 — 쓰임 기록은 동기화 대상 상태가 아니라 관측 장부 전용"),
    frozenset(("OBS", "RES")): ("접점",
        "읽기 전용 — 공명은 쓰임 장부를 읽어 사용 빈도를 산정한다"),
    frozenset(("OBS", "ETP")): ("접점",
        "주기 편입 — 쓰임 기록은 엔트로피 정리 주기에 편입해 무한 누적을 막는다"),
    frozenset(("OBS", "REL")): ("접점",
        "순서 종속 — 쓰임 장부의 정렬은 절대 시각이 아닌 사건 순서"),
    frozenset(("OBS", "GRV")): ("접점",
        "측면 분리 — 관측은 기록, 중력은 인출 순서"),
    frozenset(("LEAP", "EXC")): ("접점",
        "순서 고정 — 배타(기준 해시) 검증을 통과한 전이만 적용 (§11 승계)"),
    frozenset(("LEAP", "PHA")): ("접점",
        "국면 종속 — 전이 묶음 크기는 국면 규칙을 따르되 사건 원자성은 불변"),
    frozenset(("LEAP", "ETP")): ("접점",
        "경계 보존 — 사건 원장을 요약할 때도 사건 경계는 보존한다"),
    frozenset(("LEAP", "REL")): ("접점",
        "측면 분리 — 도약은 사건 내부의 원자성, 상대성은 사건 사이의 순서"),
    frozenset(("LEAP", "TUN")): ("접점",
        "원자성 유지 — 우회 전이도 경유지에서 중간 상태를 만들지 않는다"),
    frozenset(("EXC", "ETP")): ("접점",
        "형식 불변 — 압축은 값의 요약형 전환만. 주소 병합·변경 금지"),
    frozenset(("EXC", "FRC")): ("접점",
        "측면 분리 — 배타는 주소의 점유, 프랙탈은 주소의 형식"),
    frozenset(("EXC", "TUN")): ("접점",
        "예외 없음 — 우회 쓰기도 기준 해시 검증 필수"),
    frozenset(("RES", "PHA")): ("접점",
        "쓰기 분리(공명은 점수, 상전이는 표식) + 읽기 전용(상전이 임계 "
        "판정이 공명 총량을 읽음)"),
    frozenset(("RES", "GRV")): ("접점",
        "축 분리 — 공명은 시간축 누적 빈도, 중력은 구조축 연결 수. "
        "승격 심사는 공명만, 인출 순서는 중력만"),
    frozenset(("PHA", "ETP")): ("접점",
        "선언 분리 — 상전이는 국면 표식 선언만. 정리 주기·강도의 변경은 게이트 통과 후"),
    frozenset(("PHA", "ACT")): ("접점",
        "기준 종속 — 최소작용의 비용 기준은 국면 표식이 정한 정의를 따른다"),
    frozenset(("PHA", "FRC")): ("접점",
        "형식 제약 — 계층 세분·병합의 상전이도 자기유사 주소 형식을 유지"),
    frozenset(("ETP", "ACT")): ("접점",
        "하한 우선 — 복원 가능성 하한(§10) 아래로 내려가는 압축은 금지"),
    frozenset(("ETP", "FRC")): ("접점",
        "경계 존중 — 정리는 구역 경계를 깨지 않는다"),
    frozenset(("ACT", "GRV")): ("접점",
        "결정 지점 분리 — 순서는 중력, 경로는 최소작용"),
    frozenset(("REL", "TUN")): ("접점",
        "순서 부여권 — 우회로 도달한 사건의 순서도 상대성이 부여한다"),
}

_PAIR_SYMBOL = {"간섭": "●", "접점": "◐", "무간섭": "·"}


def law_pair(code_a, code_b):
    """두 법칙의 쌍 판정을 돌려준다. (문법 §15.4)

    반환: {쌍, 판정(간섭|접점|무간섭), 기호, 해소법}.
    장부에 없는 쌍은 무간섭이다. 같은 법칙끼리는 판정 대상이 아니다.
    """
    if code_a not in LAW_CODES or code_b not in LAW_CODES:
        raise NLError(f"법칙 장부에 없는 코드: {code_a}·{code_b}")
    if code_a == code_b:
        raise NLError("같은 법칙끼리는 쌍 판정을 하지 않는다")
    verdict, how = PAIR_VERDICTS.get(frozenset((code_a, code_b)),
                                     ("무간섭", ""))
    return {"쌍": (code_a, code_b), "판정": verdict,
            "기호": _PAIR_SYMBOL[verdict], "해소법": how}


def interference_matrix():
    """14×14 간섭 행렬을 LAW_CODES 순서의 기호 행렬로 돌려준다."""
    rows = []
    for a in LAW_CODES:
        row = []
        for b in LAW_CODES:
            row.append("—" if a == b else law_pair(a, b)["기호"])
        rows.append(row)
    return rows


def validate_law_registry():
    """법칙 장부의 자기 정합을 검증한다. 반환: (통과, 문제 목록)."""
    problems = []
    codes = [law["코드"] for law in LAWS]
    if len(codes) != len(set(codes)):
        problems.append("법칙 코드 중복")
    if len(LAWS) != 14:
        problems.append(f"법칙 수 {len(LAWS)} — 장부는 14개가 정본")
    counts = {}
    for law in LAWS:
        if law["층"] not in LAW_LAYERS:
            problems.append(f"{law['코드']}: 모르는 관할 층 {law['층']}")
        if not law.get("측면") or not law.get("상황") or not law.get("지표"):
            problems.append(f"{law['코드']}: 측면·상황·지표 중 누락")
        counts[law["층"]] = counts.get(law["층"], 0) + 1
    if counts != _LAYER_COUNTS:
        problems.append(f"층 배정이 정본과 다름: {counts}")
    for pair, (verdict, how) in PAIR_VERDICTS.items():
        if len(pair) != 2 or not set(pair) <= set(codes):
            problems.append(f"쌍 판정의 코드 이상: {sorted(pair)}")
        if verdict in ("간섭", "접점") and not how:
            problems.append(f"쌍 {sorted(pair)}: {verdict}인데 분리·해소법이 없음")
    matrix = interference_matrix()
    for i, a in enumerate(LAW_CODES):
        for j, b in enumerate(LAW_CODES):
            if matrix[i][j] != matrix[j][i]:
                problems.append(f"행렬 비대칭: {a}×{b}")
    return not problems, problems


# 상황 라우팅 (문법 §15.3) — 목록의 순서가 곧 발동 순서다.
# 표에 없는 상황은 어떤 법칙도 부르지 않는다 (라우팅은 코드의 결정
# 이며 모델이 고르지 않는다 — 매니저는 규칙이다).
SITUATION_ROUTES = {
    "확정 변경": ["ENT", "LEAP", "REL", "EXC"],
    "동기화": ["REL", "ACT"],
    "판정": ["SUP", "INT"],
    "경로 결정": ["ACT"],
    "인출": ["GRV", "OBS"],
    "주소 부여": ["FRC", "EXC"],
    "주기 심사": ["RES", "ETP", "PHA"],
    "규모 임계": ["PHA"],
    "장벽": ["TUN", "EXC"],
}


def route_situation(situation):
    """상황에 배정된 법칙 코드 목록(발동 순서)을 돌려준다.

    라우팅 표에 없는 상황은 NLError — 임의로 법칙을 부르지 않는다.
    장벽 상황에서는 터널링이 최소작용을 대신한다(조건 상호 배제,
    §15.4): '동기화'·'경로 결정' 경로에 터널링은 들어 있지 않다.
    """
    if situation not in SITUATION_ROUTES:
        raise NLError(f"라우팅 표에 없는 상황: {situation} — "
                      "법칙을 임의로 부르지 않는다 (§15.3)")
    return list(SITUATION_ROUTES[situation])


def registration_gate(application, pair_verdicts):
    """새 법칙의 등록 게이트. (문법 §15.6)

    application: {코드, 이름, 정의, 작동, 층, 상황, 지표} 신청서.
    pair_verdicts: {기존 법칙 코드: (판정, 해소법)} — 기존 전 법칙과의
    쌍 판정이 빠짐없이 있어야 하고, '간섭' 판정에는 해소법이 있어야
    한다. 반환: (통과, 문제 목록). 하니스 시험(동시 발동·라우팅·지표
    측정)은 이 게이트를 통과한 신청에 붙는 다음 절차다.
    """
    problems = []
    for fieldname in ("코드", "이름", "정의", "작동", "층", "상황", "지표"):
        if not application.get(fieldname):
            problems.append(f"신청서 누락: {fieldname}")
    layer = application.get("층")
    if layer is not None and layer not in LAW_LAYERS:
        problems.append(f"관할 층은 하나만, 다섯 층 중 하나: {layer}")
    if application.get("코드") in LAW_CODES:
        problems.append(f"이미 등록된 코드: {application.get('코드')}")
    for law in LAWS:
        v = pair_verdicts.get(law["코드"])
        if v is None:
            problems.append(f"쌍 판정 누락: {law['코드']}")
        elif v[0] == "간섭" and not v[1]:
            problems.append(f"{law['코드']}와 간섭인데 해소법이 없음")
    return not problems, problems


# ------------------------------------- 시험 적용 법칙 (문법 §15.8)
#
# 프로젝트 책임자 2026-11-05 방침: "법칙을 다 적용해봐. 적용해서 안 좋은
# 것은 빼고 좋은 것은 유지한다." — 정식 등록(§15.6)을 기다리지 않고
# 시험 상태로 먼저 걸어, 걸린 지점의 전후를 재어 판정한다.
# 이 절이 그 시험 장부의 실행형이다. 정본 장부(LAWS·PAIR_VERDICTS·
# SITUATION_ROUTES)는 건드리지 않는다: 시험 법칙은 라우팅에 들어가지
# 않고 각 적용 지점의 검사 함수로만 불린다. 되돌리기는 이 절과
# §15.8 표에서 해당 항목을 지우는 것으로 끝난다 (법칙별 개별 제거
# 가능). 적용 지점·측정·판정은 법칙_시험적용_기록_2026-11-05.md가
# 정본 기록이다.

TRIAL_LAWS = [
    {"코드": "INV", "이름": "불변량", "층": "동기화", "측면": "불변",
     "상황": "변환(전파 재작성·요약·재배치) 완료 직후",
     "지표": "오염 검출률·정상 변환 오탐률", "상태": "시험"},
    {"코드": "CAU", "이름": "인과", "층": "동기화", "측면": "인과",
     "상황": "모든 변경 사건의 접수",
     "지표": "원인 누락 접수율 (목표 0)·stale 차단율", "상태": "시험"},
    {"코드": "LND", "이름": "소실 회계", "층": "저장", "측면": "회계",
     "상황": "요약·삭제가 생기는 모든 정리 변환",
     "지표": "미회계 소실 건수 (목표 0)", "상태": "시험"},
    {"코드": "IBT", "이름": "관련성 압축", "층": "저장", "측면": "선택 기준",
     "상황": "주기 정리의 보존 집합 산출",
     "지표": "같은 예산에서 질의 적중 보존율", "상태": "시험"},
    {"코드": "SYB", "이름": "동률 붕괴", "층": "판정", "측면": "동률",
     "상황": "확정(붕괴) 순간의 동률",
     "지표": "입력 순열 대비 결정 일치율·동률 해소 기록 건수", "상태": "시험"},
    {"코드": "TAG", "이름": "태그 탄생", "층": "저장", "측면": "형식",
     "상황": "기계가 기록을 발생시키는 모든 지점",
     "지표": "산문 대비 토큰 절감률·캡슐 왕복 복원 일치율 (목표 100%)"
     "·형식 위반 거부율", "상태": "시험"},
]

TRIAL_LAW_CODES = [law["코드"] for law in TRIAL_LAWS]
ALL_LAW_CODES = LAW_CODES + TRIAL_LAW_CODES

# 시험 쌍 판정: 여기에 없는 쌍은 '무간섭'이다. 이번 시험에서는
# ●(간섭) 판정이 나온 쌍이 없다 — 전부 분리법이 서는 ◐이거나
# 무간섭이다. 판정 기호는 정본과 같다.
TRIAL_PAIR_VERDICTS = {
    # --- INV (불변량) ---
    frozenset(("INV", "ENT")): ("접점",
        "검사 종속 — 불변량 대조는 전파가 만든 새 상태에 사후로만 "
        "걸리고 전파 자체를 막지 않는다. 위반은 판정으로 올린다"),
    frozenset(("INV", "LEAP")): ("접점",
        "순서 분리 — 전이(도약) 적용이 먼저, 불변량 대조는 적용 뒤"),
    frozenset(("INV", "EXC")): ("접점",
        "대상 분리 — 배타는 값의 동일성(해시), 불변량은 관계량. "
        "검사 층위가 다르다"),
    frozenset(("INV", "ETP")): ("접점",
        "허용 델타 선언 — 변환마다 유지할 관계량과 허용 변화를 쌍으로 "
        "선언하고, 선언 없는 관계량 변화만 위반으로 센다"),
    frozenset(("INV", "SUP")): ("접점",
        "지위 분리 — 불변량 대조는 확정 상태에만 걸고 후보·보류는 "
        "세지 않는다"),
    frozenset(("INV", "OBS")): ("접점",
        "범위 제외 — 쓰임 장부(@R)는 불변량 산정 범위 밖 "
        "(관측의 쓰기 분리를 준용)"),
    frozenset(("INV", "RES")): ("접점",
        "범위 분리 — 공명 점수는 불변량의 관계량 산정에서 제외한다 "
        "(점수는 공명 측면 전용)"),
    frozenset(("INV", "PHA")): ("접점",
        "국면 종속 — 허용 델타 선언은 국면 표식이 정한 정의를 따른다"),
    frozenset(("INV", "CAU")): ("접점",
        "게이트/검사 분리 — 인과는 접수 전 게이트, 불변량은 적용 후 검사"),
    frozenset(("INV", "LND")): ("접점",
        "읽기 전용 의존 — 소실 회계 장부가 불변량 대조의 입력"
        "(허용 델타 산정 근거)이 된다"),
    frozenset(("INV", "IBT")): ("접점",
        "허용 델타 — 관련성 정리가 바꾸는 관계량은 산출 시점에 "
        "선언된 것만 허용한다"),
    # --- CAU (인과) ---
    frozenset(("CAU", "ENT")): ("접점",
        "원인 승계 — 전파로 생긴 변경의 원인은 전파를 일으킨 확정 사건"),
    frozenset(("CAU", "LEAP")): ("접점",
        "필드 분리 — 도약은 사건의 형태(원자성), 인과는 사건의 원인 "
        "필드. 원인 없는 사건은 형태로 성립해도 접수하지 않는다"),
    frozenset(("CAU", "REL")): ("접점",
        "조건/정렬 분리 — 인과는 접수 게이트, 상대성은 접수된 사건의 "
        "정렬. 인과가 거부한 사건은 정렬에 들어가지 않는다"),
    frozenset(("CAU", "EXC")): ("접점",
        "게이트 순서 — 인과 존재 조건 → 배타 해시 검증 순으로 "
        "통과해야 적용된다"),
    frozenset(("CAU", "TUN")): ("접점",
        "예외 없음 — 우회로 도착한 사건도 원인이 필수다"),
    frozenset(("CAU", "SUP")): ("접점",
        "지위 분리 — 후보 상태에서는 체인을 걸지 않고, 붕괴 확정 "
        "사건이 원인이 된다"),
    frozenset(("CAU", "ETP")): ("접점",
        "원인 필수 — 정리로 생기는 변경 사건도 원인(정리 주기 "
        "사건)을 단다"),
    # --- LND (소실 회계) ---
    frozenset(("LND", "ETP")): ("접점",
        "행위/회계 분리 — 엔트로피가 정리하면 소실 회계가 장부를 "
        "남긴다. 장부 없는 소실은 미완으로 판정한다"),
    frozenset(("LND", "RES")): ("접점",
        "읽기 전용 의존 — 소실 회계는 공명 보존 집합을 읽어 소실과 "
        "보존을 나눠 적는다"),
    frozenset(("LND", "LEAP")): ("접점",
        "경계 보존 — 소실 회계는 사건 경계를 깨지 않고 사건 단위로 적는다"),
    frozenset(("LND", "IBT")): ("접점",
        "기준/회계 분리 — 관련성이 고르고 소실 회계가 잃은 양을 "
        "적는다. 회계는 선택을 바꾸지 않는다"),
    # --- IBT (관련성 압축) ---
    frozenset(("IBT", "ETP")): ("접점",
        "기준/실행 분리 — 관련성은 보존 집합을 산출만 하고, 값형 "
        "변환(요약·색인)은 엔트로피만 한다"),
    frozenset(("IBT", "RES")): ("접점",
        "읽기 전용 — 관련성 산정에 공명 점수를 신호로 읽을 수 "
        "있으나 승격 판정은 공명만 한다"),
    # --- SYB (동률 붕괴) ---
    frozenset(("SYB", "SUP")): ("접점",
        "국면 분리 — 중첩은 후보 유지와 붕괴 사건, 동률은 붕괴 "
        "순간의 동률 해소만 맡는다. 동률이 없으면 발동하지 않는다"),
    frozenset(("SYB", "INT")): ("접점",
        "국면 분리 — 평가(간섭)가 동률 확신을 내면 확정 순간에만 "
        "동률이 깬다"),
    frozenset(("SYB", "ACT")): ("접점",
        "대상 종속 — 최소작용의 비용 동률일 때만 동률 우선순위를 "
        "적용한다"),
    frozenset(("SYB", "EXC")): ("접점",
        "순서 고정 — 동률 해소(동률) → 배타 검증(배타). 배타가 "
        "거부하면 다음 순위로 넘어가지 않고 보류한다"),
    frozenset(("SYB", "REL")): ("접점",
        "읽기 전용 — 동률 해소의 우선순위 키로 상대성의 사건 "
        "순서를 읽는다"),
    # --- TAG (태그 탄생) ---
    frozenset(("TAG", "ENT")): ("접점",
        "표기/선언 분리 — 캡슐의 연결(LK) 칸은 얽힘 집합의 주소 "
        "나열을 나를 뿐, 얽힘 선언은 §14의 행위다. 캡슐로 "
        "태어났다고 얽히지 않는다"),
    frozenset(("TAG", "SUP")): ("접점",
        "지위 분리 — 캡슐은 확정된 사건 기록만 태어난다. 후보·"
        "보류는 지위 표식과 함께 기존 꼴로 남는다"),
    frozenset(("TAG", "OBS")): ("접점",
        "대상 분리 — 쓰임 장부(@R) 기록은 캡슐로 태어날 수 "
        "있으나, 관측의 규율(기록만 남기고 값은 건드리지 않는다)은 "
        "표기가 바꾸지 않는다"),
    frozenset(("TAG", "LEAP")): ("접점",
        "형태/표기 분리 — 도약은 사건의 원자성, 태그 탄생은 사건 "
        "기록의 표기 꼴. 캡슐 한 줄이 사건 하나에 대응할 뿐이다"),
    frozenset(("TAG", "EXC")): ("접점",
        "형식 무관 검증 — 배타의 기준 해시 검증은 값의 꼴을 "
        "가리지 않는다. 캡슐 줄도 한 주소의 값으로서 동일하게 "
        "검증받는다"),
    frozenset(("TAG", "RES")): ("접점",
        "읽기 전용 의존 — 공명 점수의 기록은 캡슐로 태어날 수 "
        "있으나, 점수 누적과 승격 제안은 공명만 정한다"),
    frozenset(("TAG", "ETP")): ("접점",
        "국면 분리 — 태그 탄생은 생성 국면, 엔트로피는 정리 국면. "
        "정리 결과도 캡슐 꼴을 유지하고, 사람말 보호 구역은 "
        "정리에서도 원문을 지킨다"),
    frozenset(("TAG", "ACT")): ("접점",
        "읽기 전용 의존 — 경로 비용(토큰) 산정이 캡슐의 절감"
        "(실측 16.2%)을 입력으로 읽는다. 경로 선택은 최소작용만 "
        "정한다"),
    frozenset(("TAG", "REL")): ("접점",
        "순서 분리 — 캡슐의 시각(TM)은 장부 머리가 공유하는 "
        "표기일 뿐, 사건 순서는 상대성의 단조 순서가 정본이다. "
        "필드 순서는 표기 순서이지 사건 순서가 아니다"),
    frozenset(("TAG", "FRC")): ("접점",
        "형식 종속 — 캡슐의 주소·자리 표기는 프랙탈의 계층 주소 "
        "형식을 그대로 따르고, 주소 형식을 새로 만들지 않는다"),
    frozenset(("TAG", "INV")): ("접점",
        "읽기 전용 의존 — 캡슐은 코드가 결정적으로 파싱하므로 "
        "관계량 산정이 표기 해석 없이 수행된다. 대조 규율은 "
        "불변량만 정한다"),
    frozenset(("TAG", "CAU")): ("접점",
        "필드/판정 분리 — 캡슐의 연결 칸이 원인을 나를 수는 "
        "있으나, 원인 존재·신선도의 접수 판정은 인과 게이트만 한다"),
    frozenset(("TAG", "LND")): ("접점",
        "읽기 전용 의존 — 소실 장부의 항목은 기계 기록이라 "
        "캡슐로 태어난다. 무엇을 적는가는 소실 회계만 정한다"),
    frozenset(("TAG", "IBT")): ("접점",
        "읽기 전용 의존 — 관련성 산정은 캡슐을 파싱해 읽는다. "
        "보존 기준은 관련성 압축만 정한다"),
    frozenset(("TAG", "SYB")): ("접점",
        "읽기 전용 의존 — 동률 해소 사건의 기록은 캡슐로 "
        "태어난다. 해소 우선순위는 동률 붕괴만 정한다"),
}


def trial_law_pair(code_a, code_b):
    """시험 법칙이 낀 쌍의 판정. 정본 쌍은 law_pair와 같다.

    반환: {쌍, 판정(간섭|접점|무간섭), 기호, 해소법}.
    """
    for c in (code_a, code_b):
        if c not in ALL_LAW_CODES:
            raise NLError(f"법칙 장부에 없는 코드: {c}")
    if code_a == code_b:
        raise NLError("같은 법칙끼리는 쌍 판정을 하지 않는다")
    if code_a in LAW_CODES and code_b in LAW_CODES:
        return law_pair(code_a, code_b)
    verdict, how = TRIAL_PAIR_VERDICTS.get(frozenset((code_a, code_b)),
                                           ("무간섭", ""))
    return {"쌍": (code_a, code_b), "판정": verdict,
            "기호": _PAIR_SYMBOL[verdict], "해소법": how}


def combined_interference_matrix():
    """정본 14 + 시험 6 = 20×20 간섭 행렬 (ALL_LAW_CODES 순서)."""
    rows = []
    for a in ALL_LAW_CODES:
        row = []
        for b in ALL_LAW_CODES:
            row.append("—" if a == b else trial_law_pair(a, b)["기호"])
        rows.append(row)
    return rows


def validate_trial_registry():
    """시험 장부의 자기 정합 검증. 반환: (통과, 문제 목록).

    정본 validate_law_registry와 별개로, 시험 편입이 정본 규율을
    깨지 않는지(층·측면 유일성, 쌍 판정 완결, 행렬 대칭)를 강제한다.
    """
    problems = []
    codes = [law["코드"] for law in TRIAL_LAWS]
    if len(codes) != len(set(codes)):
        problems.append("시험 법칙 코드 중복")
    for c in codes:
        if c in LAW_CODES:
            problems.append(f"정본과 코드 충돌: {c}")
    aspects = {}
    for law in LAWS + TRIAL_LAWS:
        if law["층"] not in LAW_LAYERS:
            problems.append(f"{law['코드']}: 모르는 관할 층 {law['층']}")
        key = (law["층"], law["측면"])
        if key in aspects:
            problems.append(f"측면 중복: {law['층']} 층 {law['측면']} — "
                            f"{aspects[key]}와 {law['코드']}")
        aspects[key] = law["코드"]
    for law in TRIAL_LAWS:
        if law.get("상태") != "시험":
            problems.append(f"{law['코드']}: 상태가 '시험'이 아님")
        if not law.get("측면") or not law.get("상황") or not law.get("지표"):
            problems.append(f"{law['코드']}: 측면·상황·지표 중 누락")
    for pair, (verdict, how) in TRIAL_PAIR_VERDICTS.items():
        if len(pair) != 2 or not set(pair) <= set(ALL_LAW_CODES):
            problems.append(f"시험 쌍 판정의 코드 이상: {sorted(pair)}")
        if not set(pair) & set(TRIAL_LAW_CODES):
            problems.append(f"시험 쌍 판정에 시험 법칙이 없음: {sorted(pair)}")
        if verdict in ("간섭", "접점") and not how:
            problems.append(f"시험 쌍 {sorted(pair)}: {verdict}인데 "
                            "분리·해소법이 없음")
    matrix = combined_interference_matrix()
    for i, a in enumerate(ALL_LAW_CODES):
        for j, b in enumerate(ALL_LAW_CODES):
            if matrix[i][j] != matrix[j][i]:
                problems.append(f"통합 행렬 비대칭: {a}×{b}")
    return not problems, problems


# --- INV 불변량: 변환 뒤 관계량 대조 ---------------------------------

_REF_TOKEN_RE = re.compile(r"[^\s,]+/[^\s,]*")


def state_quantities(state):
    """상태의 관계량: 주소 수·수치합·길이합·참조 수. (시험 INV)

    개별 값의 내용이 아니라 값들 사이의 양(量)을 재는 것이 해시와의
    차이다. 쓰임 장부(@R 접두)는 관측의 쓰기 분리를 준용해 제외한다.
    """
    qtys = {"주소수": 0, "수치합": 0.0, "길이합": 0, "참조수": 0}
    for addr, value in state.items():
        if str(addr).startswith("@R"):
            continue
        qtys["주소수"] += 1
        num = _as_number(value)
        if num is not None:
            qtys["수치합"] += num
        text = str(value)
        qtys["길이합"] += len(text)
        qtys["참조수"] += len(_REF_TOKEN_RE.findall(text))
    return qtys


def verify_transform(before, after, declared):
    """변환 뒤 불변량 대조. (시험 INV)

    declared: {관계량: 허용 변화량} — 선언에 없는 관계량은 허용 0.
    반환: (통과, 위반 목록 [{관계량, 변환전, 변환후, 변화, 허용}]).
    """
    qb, qa = state_quantities(before), state_quantities(after)
    violations = []
    for name in qb:
        delta = qa[name] - qb[name]
        allowed = declared.get(name, 0)
        if abs(delta - allowed) > 1e-9:
            violations.append({"관계량": name, "변환전": qb[name],
                               "변환후": qa[name], "변화": delta,
                               "허용": allowed})
    return not violations, violations


# --- CAU 인과: 사건 접수 게이트 --------------------------------------

class CausalGate:
    """원인 체인을 강제하는 사건 접수 게이트. (시험 CAU)

    사건: {"id", "델타": (주소, 연산, 값, 기준해시), "원인": 사건id|None,
    "기원": bool}. 주소별 현재 머리(head) 사건을 추적한다.
    규칙: ① 원인 없는 사건은 그 주소의 기원 사건(기원=True)으로
    명시된 경우에만 접수한다. ② 원인이 그 주소의 현재 머리가 아닌
    사건은 stale로 거부한다 — 삭제 뒤 옛 값 부활형 역행 덮기를
    포함한다. 접수된 사건만 apply_delta로 넘기는 것이 전제다.
    """

    def __init__(self):
        self.heads = {}          # 주소 → 머리 사건 id
        self.seen = set()        # 접수된 사건 id 전수

    def submit(self, event):
        """반환: (접수 여부, 사유). 접수되면 머리를 갱신한다."""
        eid = event.get("id")
        delta = event.get("델타") or ()
        addr = delta[0] if delta else None
        cause = event.get("원인")
        if not eid or addr is None:
            return False, "사건 id·델타가 없음"
        if eid in self.seen:
            return False, f"이미 접수된 사건: {eid}"
        if cause is None:
            if not event.get("기원"):
                return False, "원인 없는 변경은 접수하지 않는다 (CAU)"
            if addr in self.heads:
                return False, f"기원 사건은 주소의 첫 사건만: {addr}"
        else:
            if cause not in self.seen:
                return False, f"원인 사건이 접수된 적 없음: {cause}"
            if self.heads.get(addr) != cause:
                return False, (f"stale — 원인이 현재 머리가 아님 "
                               f"({addr}: 머리 {self.heads.get(addr)}, "
                               f"원인 {cause})")
        self.seen.add(eid)
        self.heads[addr] = eid
        return True, "접수"


# --- LND 소실 회계: 정리 변환의 소실 장부 -----------------------------

def loss_ledger(before, after):
    """정리 변환의 소실 장부를 만든다. (시험 LND)

    사라진 주소는 '소실', 값이 짧아진 주소는 '요약'으로 적는다.
    소실 항목에는 값의 기준 해시를 남겨 §13 해시 확정 복원의
    단서로 삼는다. 반환: {항목, 소실건수, 요약건수, 소실문자수}.
    """
    entries = []
    lost_chars = 0
    for addr in sorted(set(before) - set(after)):
        text = str(before[addr])
        lost_chars += len(text)
        entries.append({"주소": addr, "종류": "소실",
                        "문자수": len(text),
                        "해시": state_hash(before[addr])})
    n_shrunk = 0
    for addr in sorted(set(before) & set(after)):
        gap = len(str(before[addr])) - len(str(after[addr]))
        if gap > 0:
            n_shrunk += 1
            entries.append({"주소": addr, "종류": "요약",
                            "문자수": gap, "해시": state_hash(before[addr])})
    return {"항목": entries,
            "소실건수": sum(1 for e in entries if e["종류"] == "소실"),
            "요약건수": n_shrunk,
            "소실문자수": lost_chars}


def unaccounted_loss(before, after, ledger):
    """장부에 등재되지 않은 소실·요약을 센다. (시험 LND)

    ledger가 None이면 생긴 소실 전부가 미회계다 — 시험 전의 상태.
    반환: 미회계 항목 목록 [{주소, 종류}].
    """
    recorded = set()
    if ledger:
        recorded = {(e["주소"], e["종류"]) for e in ledger["항목"]}
    missing = []
    for addr in sorted(set(before) - set(after)):
        if (addr, "소실") not in recorded:
            missing.append({"주소": addr, "종류": "소실"})
    for addr in sorted(set(before) & set(after)):
        if len(str(after[addr])) < len(str(before[addr])):
            if (addr, "요약") not in recorded:
                missing.append({"주소": addr, "종류": "요약"})
    return missing


# --- IBT 관련성 압축: 정리의 보존 집합 산출 ---------------------------

def size_keep_set(state, budget_chars):
    """대조 실행형 — 현행 크기 기준: 작은 값부터 예산까지 채운다.

    관련성 압축(IBT)의 '전' 상태를 재는 기준선이다. 채우는 규칙
    (예산에 들어갈 때만 추가, 주소순 동률)은 IBT와 동일하게 둔다.
    """
    keep, used = [], 0
    for addr in sorted(state, key=lambda a: (len(str(state[a])), a)):
        size = len(str(state[addr]))
        if used + size <= budget_chars:
            keep.append(addr)
            used += size
    return keep


def relevance_keep_set(state, queries, budget_chars):
    """관련성 기준으로 보존 집합을 산출만 한다. (시험 IBT)

    관련성 = 타일 토큰과 질의 토큰들의 겹침 합. 실제 값형 변환은
    하지 않는다 — 변환은 엔트로피(ETP)의 몫이다 (기준/실행 분리).
    동률은 주소순으로 결정적으로 처리한다.
    """
    qtokens = set()
    for q in queries:
        qtokens |= _cluster_tokens(q)
    scored = []
    for addr, value in state.items():
        overlap = len(_cluster_tokens(str(value)) & qtokens)
        scored.append((addr, overlap))
    keep, used = [], 0
    for addr, _score in sorted(scored, key=lambda s: (-s[1], s[0])):
        size = len(str(state[addr]))
        if used + size <= budget_chars:
            keep.append(addr)
            used += size
    return keep


# --- SYB 동률 붕괴: 확정 순간의 결정적 동률 해소 ----------------------

_STATUS_RANK = {"실값": 0, "복원": 1, "전파": 2, "후보": 3, "보류": 4}


def collapse_pick(candidates, ledger=None):
    """확정 순간의 동률을 결정적으로 깬다. (시험 SYB)

    candidates: [{주소, 값, 확신도, 지위, 사건순서, 해시확정}].
    확신도 최고 그룹이 하나면 그대로 확정하고, 동률이면 우선순위
    — 해시 확정 → 지위(실값>복원>전파>후보>보류) → 사건 순서 →
    주소순 — 로 깬다. 동률 해소가 일어나면 ledger(목록)에 기록을
    남긴다. 반환: (선택된 후보, 해소 기록|None).
    """
    if not candidates:
        raise NLError("동률 붕괴: 후보가 없음")
    top = max(c["확신도"] for c in candidates)
    group = [c for c in candidates if c["확신도"] == top]
    if len(group) == 1:
        return group[0], None

    def key(c):
        return (not c.get("해시확정"), _STATUS_RANK.get(c.get("지위"), 9),
                c.get("사건순서", 0), c["주소"])

    winner = min(group, key=key)
    record = {"동률수": len(group), "선택": winner["주소"],
              "근거": "해시확정→지위→사건순서→주소순"}
    if ledger is not None:
        ledger.append(record)
    return winner, record


# --- TAG 태그 탄생: 기계 기록의 캡슐 출생 --------------------------------
#
# 문법: 통합기록_태그문법_2026-11-05 §1. 한 줄 = 한 사건, 필드 순서
# 고정 EV·TM·PL·KD·CT·[XY]·[RF]·[SV]·[LK]. 생략은 기본값(RF 없음·
# SV 일반)이고, 민감 '제외'(SV=2)는 캡슐 자체를 만들지 않는다.
# 사람말 원문은 따옴표 보호 구역으로만 싣는다 — 인용 없는 산문은
# 캡슐로 태어날 수 없다. 파싱은 형식 위반을 추측 없이 거부한다(§3).
CAPSULE_KINDS = {"SC": "화면", "AU": "음성", "VS": "장면", "TC": "터치",
                 "CM": "명령", "DV": "기기", "SY": "시스템"}
CAPSULE_FIELDS = ("EV", "TM", "PL", "KD", "CT", "XY", "RF", "SV", "LK")
_CAPSULE_REQUIRED = ("EV", "TM", "PL", "KD", "CT")


def _capsule_quoted_ok(value):
    """값의 공백은 따옴표 보호 구역 안일 때만 허용한다.

    따옴표 구간을 지운 나머지에 공백이 있으면 인용 없는 산문이다.
    """
    bare = re.sub(r'"[^"]*"', "", str(value))
    return " " not in bare and "\t" not in bare


def _capsule_split(line):
    """따옴표 안의 공백을 건드리지 않고 토큰을 나눈다."""
    tokens, buf, quoted = [], [], False
    for ch in line:
        if ch == '"':
            quoted = not quoted
            buf.append(ch)
        elif ch in (" ", "\t") and not quoted:
            if buf:
                tokens.append("".join(buf))
                buf = []
        else:
            buf.append(ch)
    if buf:
        tokens.append("".join(buf))
    return tokens


def born_capsule(fields):
    """구조 필드를 태그 캡슐 한 줄로 찍어 낸다. (시험 TAG)

    fields: {EV, TM, PL, KD, CT, [XY], [RF], [SV], [LK]}.
    반환: 캡슐 문자열. 규칙 위반은 NLError:
    필수 누락·미지 필드·미지 종류·인용 없는 산문·민감 제외(SV=2).
    """
    unknown = [k for k in fields if k not in CAPSULE_FIELDS]
    if unknown:
        raise NLError(f"캡슐에 없는 필드: {unknown}")
    for key in _CAPSULE_REQUIRED:
        if not str(fields.get(key, "")).strip():
            raise NLError(f"캡슐 필수 칸 누락: {key}")
    kind = str(fields["KD"])
    if kind not in CAPSULE_KINDS:
        raise NLError(f"캡슐 미지 종류(KD): {kind}")
    sv = str(fields.get("SV", "")).strip()
    if sv in ("2", "제외"):
        raise NLError("민감 '제외' 등급은 캡슐 자체를 만들지 않는다 (TAG)")
    parts = []
    for key in CAPSULE_FIELDS:
        if key not in fields:
            continue
        value = str(fields[key]).strip()
        if not value:
            continue
        if key == "SV" and value in ("0", "일반"):
            continue  # 생략 = 일반(기본값)
        if not _capsule_quoted_ok(value):
            raise NLError(f"인용 없는 산문은 캡슐로 태어날 수 없다: {key}")
        parts.append(f"{key}={value}")
    return " ".join(parts)


def parse_capsule(line):
    """캡슐 한 줄을 필드 사전으로 되읽는다. (시험 TAG)

    순서·필수·종류·보호 구역 위반은 추측 없이 거부한다.
    반환: {필드: 값} — 사람말 원문은 따옴표째 그대로 복원된다.
    """
    fields, order = {}, []
    for token in _capsule_split(str(line)):
        m = re.match(r"^([A-Z]{2})=(.*)$", token)
        if not m or m.group(1) not in CAPSULE_FIELDS:
            raise NLError(f"캡슐 형식 위반: {token!r}")
        key, value = m.group(1), m.group(2)
        if key in fields:
            raise NLError(f"캡슐 필드 중복: {key}")
        fields[key] = value
        order.append(key)
    for key in _CAPSULE_REQUIRED:
        if key not in fields:
            raise NLError(f"캡슐 필수 칸 누락: {key}")
    if [CAPSULE_FIELDS.index(k) for k in order] != sorted(
            CAPSULE_FIELDS.index(k) for k in order):
        raise NLError("캡슐 필드 순서 위반 (EV·TM·PL·KD·CT·XY·RF·SV·LK)")
    if fields["KD"] not in CAPSULE_KINDS:
        raise NLError(f"캡슐 미지 종류(KD): {fields['KD']}")
    if fields.get("SV") in ("2", "제외"):
        raise NLError("민감 '제외' 캡슐은 존재하지 않는다 (TAG)")
    for key, value in fields.items():
        if not _capsule_quoted_ok(value):
            raise NLError(f"인용 없는 산문은 캡슐로 태어날 수 없다: {key}")
    return fields


# 값 체계 (문법 §15.5) — 진법은 층이 정하고, 층 안에서는 상황의
# 정밀도 요구가 정한다. 신호층의 값 개수는 그 층의 물리가 정하므로
# 언어가 관여하지 않고, 아래는 언어 층이 고정하는 값 집합뿐이다.
JUDGEMENT_VALUES = ("통과", "보류", "거부")        # 판정값: 3값 고정
STATE_STATUS_VALUES = ("실값", "복원", "전파", "후보", "보류")  # 지위값


def strip_echo(output, dictionary):
    """에코로 판정된 줄을 제거한 본문을 돌려준다."""
    are = _assign_re(dictionary)
    phrases = [p for p in dictionary.phrases() if len(p) >= 4]
    kept = []
    for line in (output or "").split("\n"):
        if "[µ사전]" in line:
            continue
        if are.match(line):
            continue
        if any(p in line for p in phrases):
            continue
        kept.append(line)
    out = "\n".join(kept).strip()
    out = re.sub(r"^(A:|U:)\s*", "", out)
    return out
