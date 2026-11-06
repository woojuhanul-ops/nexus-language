# -*- coding: utf-8 -*-
"""패턴 언어 형태 정합 검사(다듬기 1호) 단위 시험.
실행: python3 tests/test_pattern_class_consistency.py

실측 분류 근거 (패턴사전_Qwen3-4B_2026-11-05.json):
  P024·P001·P368 = 집중형 / P013·P007·P398 = 균일형 / 혼합형은 전수 0개.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from pattern_lang import (EXAMPLES, check_class_consistency,
                          class_mismatches, compose, parse, roundtrip)

PASS = []


def check(name, cond, extra=""):
    PASS.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + (f" | {extra}" if extra else ""))


def rejects(fn):
    try:
        fn()
    except ValueError:
        return True
    return False


# --- 정합 케이스: 파싱·왕복이 통과해야 한다 -------------------------
CONSISTENT = [
    "P024 A01",        # 집중형에 A01
    "P013 A02",        # 균일형에 A02
    "P368 A01 A06",    # 집중형 + 비형태 상태 병기
    "P007 A02",        # 균일형 (Q6_K)
    "P398 A02 V11",    # 균일형, 지시형
    "X02 P368 A13 V07",  # 형태 주장 없음 → 정합
    "P024 A01 A10 V08",  # 집중형 + 확정, 지시형
    "P035 A11 V03",    # 비형태 상태만 → 정합
]
for s in CONSISTENT:
    r = roundtrip(s)
    check(f"정합 통과 {s!r}", r["일치"] and check_class_consistency(s) == [])

# --- 어긋남 케이스: parse·compose 모두 거부해야 한다 ----------------
MISMATCH = [
    ("P024 A02", "집중형 텐서에 균일형 주장"),
    ("P013 A01", "균일형 텐서에 집중형 주장"),
    ("P001 A03", "집중형 텐서에 혼합형 주장 — A03 경계(실측 0개)"),
    ("P007 A03", "균일형 텐서에 혼합형 주장 — A03 경계(실측 0개)"),
    ("P398 A01", "균일형 텐서에 집중형 주장 (제작 중 실제 어긋남 사례)"),
    ("P368 A02 A10", "다중 상태 중 하나만 어긋남"),
    ("P024 A01 A02", "상충하는 형태 주장 동시 병기"),
    ("P024 A02 V03", "지시형에서의 어긋남"),
    ("X05 P013 A01 V09", "접두가 있어도 어긋남"),
]
for s, why in MISMATCH:
    check(f"어긋남 거부(parse) {s!r}", rejects(lambda: parse(s)), why)
    p = s.split(" ")
    toks = [t for t in p if not t.startswith("V")]
    verb = next((t for t in p if t.startswith("V")), None)
    states = [t for t in toks if t.startswith("A")]
    target = next(t for t in toks if t.startswith("P"))
    prefixes = [t for t in toks if t.startswith("X")]
    check(f"어긋남 거부(compose) {s!r}",
          rejects(lambda: compose(prefixes, target, states, verb)), why)

# --- 플래그 API: 거부 없이 어긋남 내용을 돌려줘야 한다 ---------------
m = check_class_consistency("P024 A02")
check("플래그 내용 정확", m == [{"토큰": "A02", "주장": "균일형", "실측": "집중형"}],
      str(m))
m3 = check_class_consistency("P007 A03")
check("플래그 A03", m3 == [{"토큰": "A03", "주장": "혼합형", "실측": "균일형"}],
      str(m3))
check("class_mismatches 직접 호출",
      class_mismatches("P013", ["A01", "A11"]) ==
      [{"토큰": "A01", "주장": "집중형", "실측": "균일형"}])

# --- 기존 거동 회귀: 예문 왕복 16/16, 기존 거부 규칙 유지 -------------
ok = sum(roundtrip(s)["일치"] for s in EXAMPLES)
check("기존 예문 왕복 16/16 유지", ok == len(EXAMPLES) == 16, f"{ok}/16")
for s in ["A01 P024", "P024 V02", "P024 V01 P035", "P999 A01", "P024 A99",
          "P024", "P024 A01 A01", "X01 X01 P002 V04"]:
    check(f"기존 거부 유지 {s!r}", rejects(lambda: parse(s)))

print(f"\n합계: {sum(PASS)}/{len(PASS)} PASS")
sys.exit(0 if all(PASS) else 1)
