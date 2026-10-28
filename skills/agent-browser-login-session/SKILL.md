---
name: agent-browser-login-session
description: |
  로그인이 필요한 사이트(Buffer 등)를 agent-browser로 다룰 때 쓴다. 전용 Chrome 프로필 + CDP(디버그 포트) 연결로
  로그인 세션을 스킬 밖에 유지한다. 자격 증명(아이디·비밀번호)은 스킬·파일·대화에 저장하지 않고,
  로그인은 사용자가 창에서 직접 1회 한다. "agent-browser로 로그인 필요한 페이지", "Buffer 웹에서 작업" 요청 시.
category: browser
---

# agent-browser 로그인 세션 (자격 증명 없이 세션 유지)

## 원칙
- **비밀번호를 입력·저장하지 않는다.** 대화에 붙여 넣은 계정 정보도 파일·환경변수·`agent-browser auth save`에 옮기지 않는다. 로그인은 사용자가 띄운 창에서 직접 한다.
- 로그인 상태는 **전용 프로필 폴더**에 남는다: `~/.agent-browser/profiles/<사이트>`. 스킬 폴더 밖이라 스킬을 내보내도(export) 쿠키·세션이 따라가지 않는다. 이 폴더는 공유·커밋하지 않는다.
- 세션이 만료되면 작업을 멈추고 사용자에게 다시 로그인해 달라고 한다.

## 절차

1. **전용 Chrome 띄우기**(사용자가 로그인할 창, 포트는 사이트마다 다르게):
   ```bash
   mkdir -p "$HOME/.agent-browser/profiles/buffer-publish"
   open -na "Google Chrome" --args --remote-debugging-port=9333 \
     --user-data-dir="$HOME/.agent-browser/profiles/buffer-publish" \
     --no-first-run --no-default-browser-check "https://publish.buffer.com/"
   curl -s http://127.0.0.1:9333/json/version | head -3   # Browser 값이 나오면 디버그 포트 정상
   ```
2. **연결** — 항상 전용 세션 이름을 쓴다:
   ```bash
   agent-browser --session buffer-pub connect 9333
   agent-browser --session buffer-pub get url
   agent-browser --session buffer-pub snapshot -i -c
   ```
3. **로그인 확인**: URL이 `auth.<사이트>/login...`이거나 스냅샷에 Email/Password 입력칸이 보이면 로그인 전이다. 입력하지 말고 사용자에게 "열린 Chrome 창에서 로그인해 주세요"라고 요청한 뒤 멈춘다. 로그인되면 같은 프로필이라 다음부터는 이 단계가 필요 없다.
4. **작업**: 이후 모든 명령에 `--session buffer-pub`을 붙인다. 페이지가 바뀌면 `snapshot -i`로 ref(@eN)를 다시 받는다. 파일 업로드는 `agent-browser --session buffer-pub upload <ref> <파일...>`.
5. **정리**: `agent-browser --session buffer-pub close`(자기 세션만). `close --all`은 다른 작업 세션까지 끊으므로 쓰지 않는다.

## 함정 (2026-10-27 실측)
- agent-browser 데몬이 이미 떠 있으면 `--headed`는 무시된다("daemon already running"). 데몬을 재시작하면 다른 세션(`lane-*` 등)이 끊길 수 있으므로, 사용자가 로그인할 창은 위 1번의 **별도 Chrome**으로 띄운다.
- `--session` 없이 `open`을 실행하면 이미 쓰이던 `default` 세션의 화면이 바뀐다. 항상 `--session <전용이름>`을 쓴다. `agent-browser session list`로 다른 세션을 확인한다.
- 원격 디버깅 포트는 전용 `--user-data-dir`로 띄운 Chrome에서 쓴다(기본 프로필에서는 막힐 수 있다 — 미검증).
- 로그인 직후에는 앱 세션이 덜 갖춰져 Buffer 작성기 업로드 등이 실패할 수 있다("Unauthorized request"). 로그인 후 대상 페이지를 **다시 열면** 정상이었다(2026-10-27, Buffer).
- 사용자가 로그인하는 동안 Chrome 탭이 닫히면 연결 후 `about:blank`만 보일 수 있다. `agent-browser --session <이름> open <URL>`로 다시 열어 로그인 상태를 확인한다.
- `which agent-browser`가 비면 nvm의 node bin 폴더(`~/.nvm/versions/node/<버전>/bin`)에서 찾는다.

## 검증 상태
- 확인함(2026-10-27): 1번 Chrome 기동과 `json/version` 응답, 2번 연결·`get url`·`snapshot -i -c`(Buffer 로그인 화면이 보임), 데몬이 떠 있을 때 `--headed` 무시.
- 확인함(2026-10-27): 사용자가 로그인한 뒤 Buffer 채널 페이지·초안 작성기 조작, `upload`로 파일 첨부와 `Save Draft`까지 동작(`buffer-draft-media-attach` 스킬).
- **미확인**: Chrome을 껐다 켰을 때 로그인이 프로필에 유지되는지.
