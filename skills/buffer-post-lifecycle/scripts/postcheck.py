#!/usr/bin/env python3
"""Buffer get_post 응답(JSON)이 기대 상태와 맞는지 점검한다.

사용:
  python3 -I postcheck.py --expect draft|scheduled|sent [--now ISO8601] [--file post.json]
  (JSON은 --file 또는 stdin)
  python3 -I postcheck.py selftest

종료 코드: 0 PASS, 1 FAIL, 2 사용 오류.
"""
import argparse
import json
import sys
from datetime import datetime, timezone


def parse(ts):
    if ts is None:
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def check(post, expect, now=None):
    """위반 목록을 반환한다. 빈 리스트면 PASS."""
    bad = []
    st = post.get("status")
    due, sent = post.get("dueAt"), post.get("sentAt")
    if st != expect:
        bad.append(f"status={st!r}, 기대 {expect!r}")
        if st == "draft" and due:
            bad.append("draft인데 dueAt이 있음: edit_post에 saveToDraft:false가 빠진 예약 실패 상태")
    if expect == "draft":
        if due is not None:
            bad.append(f"dueAt={due}, 초안은 null이어야 함")
        if sent is not None:
            bad.append("sentAt이 있음")
        if post.get("sharedNow"):
            bad.append("sharedNow=true")
    elif expect == "scheduled":
        if due is None:
            bad.append("dueAt 없음")
        elif now is not None and parse(due) <= now:
            bad.append(f"dueAt={due}가 now 이하(과거 예약)")
        if post.get("isCustomScheduled") is False:
            bad.append("isCustomScheduled=false")
        if sent is not None:
            bad.append("sentAt이 이미 있음")
    elif expect == "sent":
        if sent is None:
            bad.append("sentAt 없음")
        if post.get("channelService") == "instagram" and post.get("schedulingType") == "notification":
            if post.get("externalLink"):
                bad.append("알림 방식인데 externalLink가 있음(예상 밖)")
        elif not post.get("externalLink"):
            bad.append("자동 게시인데 externalLink 없음")
    if post.get("error"):
        bad.append(f"error={post['error']!r}")
    if post.get("channelService") == "instagram" and post.get("schedulingType") == "automatic":
        bad.append("instagram automatic: 개인 프로필이면 거부되는 조합(채널 타입 확인)")
    return bad


def selftest():
    base = {"error": None, "sharedNow": False, "isCustomScheduled": False}
    now = datetime(2026, 10, 27, 13, 33, tzinfo=timezone.utc)
    cases = [
        ("draft ok", {**base, "status": "draft", "dueAt": None, "sentAt": None}, "draft", [], True),
        ("draft with dueAt = 예약 실패", {**base, "status": "draft", "dueAt": "2026-10-27T13:35:00.000Z", "sentAt": None, "isCustomScheduled": True}, "scheduled", ["saveToDraft"], False),
        ("scheduled ok", {**base, "status": "scheduled", "dueAt": "2026-10-27T13:35:00.000Z", "sentAt": None, "isCustomScheduled": True}, "scheduled", [], True),
        ("scheduled past", {**base, "status": "scheduled", "dueAt": "2026-10-27T13:30:00.000Z", "sentAt": None, "isCustomScheduled": True}, "scheduled", ["과거"], False),
        ("sent threads", {**base, "status": "sent", "dueAt": "x", "sentAt": "2026-10-27T13:35:48Z", "channelService": "threads", "schedulingType": "automatic", "externalLink": "https://t"}, "sent", [], True),
        ("sent ig notify", {**base, "status": "sent", "dueAt": "x", "sentAt": "2026-10-27T13:35:06Z", "channelService": "instagram", "schedulingType": "notification", "externalLink": None}, "sent", [], True),
        ("ig automatic", {**base, "status": "draft", "dueAt": None, "sentAt": None, "channelService": "instagram", "schedulingType": "automatic"}, "draft", ["automatic"], False),
    ]
    fails = 0
    for name, post, expect, needles, should_pass in cases:
        bad = check(post, expect, now)
        ok = (not bad) == should_pass and all(any(n in b for b in bad) for n in needles)
        print(("OK   " if ok else "FAIL ") + name + ("" if not bad else " -> " + "; ".join(bad)))
        fails += 0 if ok else 1
    print("selftest", "PASS" if fails == 0 else f"FAIL {fails}")
    return 1 if fails else 0


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        sys.exit(selftest())
    ap = argparse.ArgumentParser()
    ap.add_argument("--expect", required=True, choices=["draft", "scheduled", "sent"])
    ap.add_argument("--now")
    ap.add_argument("--file")
    a = ap.parse_args()
    raw = open(a.file, encoding="utf-8").read() if a.file else sys.stdin.read()
    try:
        post = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"JSON 오류: {e}", file=sys.stderr)
        sys.exit(2)
    now = parse(a.now) if a.now else datetime.now(timezone.utc)
    bad = check(post, a.expect, now)
    for b in bad:
        print("FAIL", b)
    print("PASS" if not bad else f"FAIL {len(bad)}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
