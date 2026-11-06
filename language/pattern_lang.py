# pattern_lang.py — 패턴 언어 해석기 v0.1
#
# 패턴 사전(명사층 P001~P398) + 기능 사전(동사 V##·형용사 A##·접두 X##)으로
# 기호 문장을 생성(compose)·파싱(parse)·풀어쓰기(expand)하는 코드 층 해석기.
# 라이브 해석기 nexus_lang.py와 별도 파일이며, nexus_lang.py는 수정하지 않는다
# (충돌 검사의 대조용으로 그 파일의 텍스트만 읽고 실행하지 않는다).
#
# 문법 (패턴언어_체계_v0.1의 문장 형식):
#   서술형: [접두]* 대상 [상태]+              — 동작 없음, 상태 1개 이상 필수
#   지시형: [접두]* 대상 [상태]* 동작 [상대]?  — 동작 1개 필수
#   상대 대상은 쌍동작(V02 비교·V05 동기화)에서만, V02는 상대 필수.
# 토큰은 공백 하나로 구분하고 전 토큰 일치로 판정한다 (A##를 'A'+숫자로
# 쪼개지 않는다 — 문법 정본의 T/TAG 구분과 같은 원칙).
# 모르는 토큰·순서 위반은 추측 없이 거부한다 (문법 정본 §3).
#
# 범위: 이 해석기는 의미 등록·서술·지시까지다. 기호 위의 산술(수 연산
# 체계)은 다루지 않는다.
#
# 다듬기 1호 (2026-11-05): 형태 정합 검사. 상태 형용사 A01(집중형)·
# A02(균일형)·A03(혼합형)은 패턴 사전의 실측 분류와 대응하므로, 문장에
# 붙은 형태 주장이 실측과 어긋나면 거부한다 (아래 CLASS_ADJECTIVES 절).

import json
import re
from pathlib import Path

BASE = Path(__file__).parent
FUNC_DICT_PATH = BASE / "패턴언어_사전_v0.1.txt"
PATTERN_DICT_PATH = BASE / "패턴사전_Qwen3-4B_2026-11-05.json"
NEXUS_DICT_PATH = BASE / "사전_v1.txt"
NEXUS_LANG_PATH = BASE / "nexus_lang.py"

PAIR_VERBS = {"V02", "V05"}     # 상대 대상을 받을 수 있는 동작
REQUIRED_PAIR = {"V02"}         # 상대 대상이 필수인 동작

_TOKEN_CLASS_RES = (
    ("접두", re.compile(r"^X\d{2}$")),
    ("대상", re.compile(r"^P\d{3}$")),
    ("상태", re.compile(r"^A\d{2}$")),
    ("동작", re.compile(r"^V\d{2}$")),
)


def _token_class(token):
    for name, rx in _TOKEN_CLASS_RES:
        if rx.match(token):
            return name
    return None


def load_functional_dict(path=FUNC_DICT_PATH):
    """패턴언어_사전_v0.1.txt → {토큰: {류, 의미, 짧은말, 근거, 상태}}"""
    result = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or re.match(r"^@(PDICT|DATE)\b", line):
            continue
        parts = [p.strip() for p in line.split(" | ")]
        if len(parts) != 5:
            raise ValueError(f"기능 사전 형식 위반: {line!r}")
        token, kind, meaning, basis, status = parts
        if token in result:
            raise ValueError(f"기능 사전 토큰 중복: {token}")
        result[token] = {
            "류": kind,
            "의미": meaning,
            "짧은말": meaning.split(" — ")[0],
            "근거": basis,
            "상태": status,
        }
    return result


def load_pattern_dict(path=PATTERN_DICT_PATH):
    """패턴사전 JSON → {기호: 항목}"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {e["symbol"]: e for e in data["entries"]}


FUNC = load_functional_dict()
PATTERNS = load_pattern_dict()


def _check_membership(token, cls):
    if cls == "대상":
        if token not in PATTERNS:
            raise ValueError(f"패턴 사전에 없는 기호: {token} (추측 없이 거부)")
    else:
        if token not in FUNC:
            raise ValueError(f"기능 사전에 없는 기호: {token} (추측 없이 거부)")
        want = {"접두": "접두", "상태": "형용사", "동작": "동사"}[cls]
        if FUNC[token]["류"] != want:
            raise ValueError(f"류가 맞지 않음: {token}은 {FUNC[token]['류']}")


def _validate_structure(prefixes, target, states, verb, target2):
    for t in prefixes:
        _check_membership(t, "접두")
    _check_membership(target, "대상")
    for t in states:
        _check_membership(t, "상태")
    if len(set(prefixes)) != len(prefixes):
        raise ValueError("접두 중복")
    if len(set(states)) != len(states):
        raise ValueError("상태 중복")
    if verb is None:
        if target2 is not None:
            raise ValueError("서술형에는 상대 대상을 둘 수 없다")
        if not states:
            raise ValueError("서술형은 상태가 1개 이상 필요하다")
    else:
        _check_membership(verb, "동작")
        if target2 is not None:
            _check_membership(target2, "대상")
            if verb not in PAIR_VERBS:
                raise ValueError(f"{verb}는 상대 대상을 받지 않는 동작이다")
        if verb in REQUIRED_PAIR and target2 is None:
            raise ValueError(f"{verb}는 상대 대상이 필수다")


def compose(prefixes=(), target=None, states=(), verb=None, target2=None):
    """기호 문장 생성. 구조가 문법을 어기거나 형태 정합을 어기면 ValueError."""
    if target is None:
        raise ValueError("대상(P기호)이 필요하다")
    prefixes, states = list(prefixes), list(states)
    _validate_structure(prefixes, target, states, verb, target2)
    _enforce_class_consistency(target, states)
    tokens = prefixes + [target] + states
    if verb is not None:
        tokens.append(verb)
        if target2 is not None:
            tokens.append(target2)
    return " ".join(tokens)


def _parse_structure(sentence):
    """기호 문장 파싱 → 구조 dict (형태 정합 검사는 하지 않는다).
    순서 위반·미등록 토큰은 거부."""
    if not isinstance(sentence, str) or not sentence.strip():
        raise ValueError("빈 문장")
    tokens = sentence.split(" ")
    if any(t == "" for t in tokens):
        raise ValueError("토큰은 공백 하나로 구분한다")
    prefixes, states = [], []
    target = verb = target2 = None
    stage = 0  # 0 접두 → 1 대상 → 2 상태 → 3 동작 → 4 상대
    for tok in tokens:
        cls = _token_class(tok)
        if cls is None:
            raise ValueError(f"알 수 없는 토큰: {tok} (추측 없이 거부)")
        if cls == "접두" and stage == 0:
            prefixes.append(tok)
        elif cls == "대상" and stage == 0:
            target, stage = tok, 2
        elif cls == "상태" and stage == 2:
            states.append(tok)
        elif cls == "동작" and stage == 2:
            verb, stage = tok, 4
        elif cls == "대상" and stage == 4:
            target2, stage = tok, 5
        else:
            raise ValueError(f"토큰 순서 위반: {tok} (단계 {stage})")
    if target is None:
        raise ValueError("대상이 없다")
    _validate_structure(prefixes, target, states, verb, target2)
    return {"접두": prefixes, "대상": target, "상태": states,
            "동작": verb, "상대": target2}


# ── 형태 정합 검사 (다듬기 1호, 2026-11-05) ─────────────────────
# 상태 형용사 중 형태 3종은 패턴 사전의 실측 분류와 1:1로 대응한다:
#   A01 = 집중형 · A02 = 균일형 · A03 = 혼합형
# 문장에 붙은 형태 주장과 사전의 실측 분류가 어긋나면 그 문장은 사실을
# 잘못 서술한 것이므로 추측 없이 거부한다 (문법 정본 §3과 같은 원칙).
# 판정은 어디까지나 사전이 정한다 — 현행 사전(Qwen3-4B 실측)에는 혼합형이
# 0개라 A03은 어느 텐서에 붙어도 어긋남이지만, 사전이 바뀌면 판정도
# 사전대로 바뀐다. 형태가 아닌 상태(A04~A15)는 이 검사의 대상이 아니다.
# 상태는 문법상 대상에만 붙으므로 상대 대상은 검사하지 않는다.

CLASS_ADJECTIVES = {"A01": "집중형", "A02": "균일형", "A03": "혼합형"}


def class_mismatches(target, states):
    """대상에 붙은 형태 주장 vs 패턴 사전 실측 분류 → 어긋남 목록.

    정합이면 빈 목록. 각 항목: {"토큰", "주장", "실측"}.
    """
    measured = PATTERNS[target].get("class")
    if measured is None:
        return []
    out = []
    for t in states:
        claimed = CLASS_ADJECTIVES.get(t)
        if claimed is not None and claimed != measured:
            out.append({"토큰": t, "주장": claimed, "실측": measured})
    return out


def _enforce_class_consistency(target, states):
    bad = class_mismatches(target, states)
    if bad:
        detail = "; ".join(
            f"{m['토큰']}({m['주장']})을 붙였으나 {target}의 실측 분류는 "
            f"{m['실측']}" for m in bad)
        raise ValueError(f"형태 정합 위반: {detail}")


def check_class_consistency(parsed_or_sentence):
    """형태 정합 검사 (플래그 방식) → 어긋남 목록. 비어 있으면 정합.

    기호 문장 문자열이면 구조 파싱만으로 검사하고(거부하지 않음),
    파싱 구조 dict면 그대로 검사한다.
    """
    parsed = (_parse_structure(parsed_or_sentence)
              if isinstance(parsed_or_sentence, str) else parsed_or_sentence)
    return class_mismatches(parsed["대상"], parsed["상태"])


def parse(sentence):
    """기호 문장 파싱 → 구조 dict.
    순서 위반·미등록 토큰·형태 정합 위반은 거부."""
    parsed = _parse_structure(sentence)
    _enforce_class_consistency(parsed["대상"], parsed["상태"])
    return parsed


def _expand_pattern(sym):
    e = PATTERNS[sym]
    s = f"{sym}({e['name']} — {e['type']} 텐서, {e['class']}, 엔트로피 {e['entropy_bits']}"
    if e.get("code_central_pct") is not None:
        s += f", 중심 집중도 {e['code_central_pct']}%"
    return s + ")"


def _short(token):
    return FUNC[token]["짧은말"]


def expand(parsed):
    """파싱 구조 (또는 기호 문장) → 자연어 풀어쓰기."""
    if isinstance(parsed, str):
        parsed = parse(parsed)
    prefixes = parsed["접두"]
    body_prefixes = [t for t in prefixes if t != "X01"]
    head = ""
    if body_prefixes:
        head = "〈" + "·".join(f"{t} {_short(t)}" for t in body_prefixes) + "〉 "
    p_exp = _expand_pattern(parsed["대상"])
    states = parsed["상태"]
    state_txt = ""
    if states:
        state_txt = "(" + "·".join(f"{t} {_short(t)}" for t in states) + ")"
    verb = parsed["동작"]
    if "X01" in prefixes:
        # 제외 수식은 선언으로 풀어 쓴다: 대상을 그 처리에서 뺀다
        what = f"{_short(verb)}" if verb else "서술"
        return (f"{head}{p_exp}{state_txt}를 {what} 처리에서 제외한다 "
                f"(X01 제외).")
    if verb is None:
        state_words = "이며 ".join(_short(t) for t in states)
        return f"{head}{p_exp}는 {state_words}이다."
    if parsed["상대"] is not None:
        p2_exp = _expand_pattern(parsed["상대"])
        return (f"{head}{p_exp}{state_txt}를 {p2_exp}와 "
                f"{_short(verb)}하라({verb}).")
    return f"{head}{p_exp}{state_txt}를 {_short(verb)}하라({verb})."


def roundtrip(sentence):
    """왕복 검사: 파싱 → 재생성 일치 여부 + 풀어쓰기."""
    parsed = parse(sentence)
    regenerated = compose(parsed["접두"], parsed["대상"], parsed["상태"],
                            parsed["동작"], parsed["상대"])
    return {"원문": sentence, "재생성": regenerated,
            "일치": regenerated == sentence,
            "풀어쓰기": expand(parsed), "구조": parsed}


# ── 충돌 검사 (전 체계 전수 대조) ────────────────────────────────

CAPSULE_FIELDS = {"EV", "TM", "PL", "KD", "CT", "XY", "RF", "SV", "LK"}
KD_VALUE_CODES = {"SC", "AU", "VS", "TC", "CM", "DV", "SY"}
HEADER_KEYS = {"DICT", "SID", "LAYER", "MAP"}


def _nexus_dict_tokens():
    tokens = set()
    for line in NEXUS_DICT_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or re.match(r"^@(DICT|DATE)\b", line):
            continue
        tokens.add(line.split(" | ")[0].strip())
    return tokens


def _law_codes():
    text = NEXUS_LANG_PATH.read_text(encoding="utf-8")
    return set(re.findall(r'"코드":\s*"([A-Z]+)"', text))


def existing_token_universe():
    """대조 대상 전 체계의 토큰 집합 (이름 → 집합)."""
    return {
        "사전_v1.2(19항목)": _nexus_dict_tokens(),
        "법칙코드(nexus_lang.py에서 추출)": _law_codes(),
        "캡슐필드(9)": set(CAPSULE_FIELDS),
        "KD값코드(7)": set(KD_VALUE_CODES),
        "전문머리키(4)": set(HEADER_KEYS),
        "패턴기호(398)": set(PATTERNS.keys()),
    }


def validate_registry():
    """기능 사전 토큰 vs 전 체계 — 전 토큰 일치 충돌 + 접두 겹침 주의."""
    universe = existing_token_universe()
    func_tokens = set(FUNC.keys())
    collisions = {}
    for name, toks in universe.items():
        hit = sorted(func_tokens & toks)
        if hit:
            collisions[name] = hit
    # 접두 겹침 (충돌은 아니나 전 토큰 일치 원칙으로 구분됨을 명시)
    all_existing = set().union(*universe.values())
    prefix_notes = sorted(
        t for t in func_tokens
        if any(t.startswith(e) and t != e
               for e in all_existing if len(e) == 1)
    )
    return {"기능토큰수": len(func_tokens), "충돌": collisions,
            "접두겹침주의": prefix_notes,
            "대조집합크기": {k: len(v) for k, v in universe.items()}}


EXAMPLES = [
    "P024 A01",
    "P013 A02",
    "P368 A01 A06",
    "P024 V02 P035",
    "P044 V02 P007",
    "X03 P398 V09",
    "P001 V01",
    "X05 P007 V09",
    "X01 P002 V04",
    "X02 P368 A13 V07",
    "X07 P009 V05 P011",
    "X09 P001 V12",
    "X04 P013 V10",
    "P398 A02 V11",
    "P035 A11 V03",
    "X06 P024 A10 V08",
]


if __name__ == "__main__":
    reg = validate_registry()
    print("== 충돌 검사 ==")
    print(json.dumps(reg, ensure_ascii=False, indent=1))
    print("\n== 예문 왕복 ==")
    ok = 0
    for s in EXAMPLES:
        r = roundtrip(s)
        ok += r["일치"]
        print(f"[{'OK' if r['일치'] else 'FAIL'}] {s}")
        print(f"    → {r['풀어쓰기']}")
    print(f"\n왕복 일치: {ok}/{len(EXAMPLES)}")
