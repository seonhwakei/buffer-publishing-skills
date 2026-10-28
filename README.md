# buffer-publishing-skills

Buffer MCP(`mcp__buffer__*`)로 게시물을 **초안 생성 → 예약 발행 → 발행 트리거 → 발행 후 확인**까지 다루는 Claude Code 스킬 묶음.
2026-10-27 실제 Buffer 계정(Instagram 개인 프로필 + Threads)에서 실측한 동작을 근거로 쓴다.

## 구성
| 경로 | 역할 |
|---|---|
| `skills/buffer-post-lifecycle/` | **핵심.** 초안·예약·즉시 발행·발행 후 진단. `scripts/postcheck.py`는 `get_post` JSON의 상태를 코드로 점검 |
| `skills/buffer-mcp-channel-inventory/` | 채널·게시물 조회, 도구·스키마 조회(읽기 전용), createPost 스키마 메모 |
| `skills/buffer-draft-media-attach/` | 로컬 이미지를 Buffer 웹 작성기로 업로드해 초안에 첨부(API는 공개 URL만 받음) |
| `skills/agent-browser-login-session/` | 위 업로드에 쓰는 전용 Chrome 프로필 세션(자격 증명은 저장하지 않음) |
| `tests/` | 블랙박스 검증 프롬프트·채점 기준·결과 |

## 설치
```bash
cp -R skills/* ~/.claude/skills/        # 전역
# 또는 프로젝트의 .claude/skills/ 로 복사
```
Buffer MCP 연결: `claude mcp add --transport http --scope user buffer https://mcp.buffer.com/mcp` 후 OAuth.

## 점검 스크립트
```bash
python3 -I skills/buffer-post-lifecycle/scripts/postcheck.py selftest
echo '<get_post JSON>' | python3 -I skills/buffer-post-lifecycle/scripts/postcheck.py --expect scheduled
```

## 핵심 함정 (실측)
1. 예약은 `edit_post`에 `mode: customScheduled` + `dueAt` + **`saveToDraft: false`**. 마지막이 빠지면 `status`가 `draft`로 남아 발행되지 않는다.
2. Instagram **개인 프로필**은 `schedulingType: notification`만 가능하고, 시각이 되면 알림만 간다(`status: sent`여도 피드에는 없음).
3. `edit_post`는 전체 재검증이라 `text`·`metadata`·`assets`를 모두 다시 보낸다.
4. 발행 후에는 수정·삭제 불가(`allowedActions` 축소). Threads는 `#` 태그가 annotations에서 빠진다.
5. 댓글 내용은 읽을 수 없다. Threads만 댓글 **수**(`includeMetrics`).

## 미검증 (문서 근거만)
`shareNow` 즉시 발행, `addToQueue`/`shareNext` 큐 동작, 예약 취소(`removePostScheduledTime`), 비즈니스 계정 Instagram 자동 게시.
