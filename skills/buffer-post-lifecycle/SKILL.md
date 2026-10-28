---
name: buffer-post-lifecycle
description: |
  Buffer MCP로 게시물을 초안 생성 → 예약 발행 → 즉시 발행(트리거) → 발행 후 확인까지 다루는 절차.
  "Buffer 초안 만들어줘", "N분 뒤로 예약", "예약 맞춰줘", "지금 발행", "발행 트리거", "발행됐는지 확인",
  "초안이 왜 안 올라갔어", "인스타 알림", "댓글 수 확인" 요청에 쓴다. 외부 게시는 사용자가 명시적으로 요청할 때만 한다.
category: social-media
---

# Buffer 게시물 수명주기 (초안 → 예약 → 발행 → 확인)

상태 흐름: `draft` →(예약) `scheduled` →(시각 도래) `sent`. 모든 단계는 `get_post`로 재조회해 확인한다.
표기: **[실측]** = 2026-10-27 실제 호출로 확인, **[문서]** = 도구 description만 근거(미시험).

## 0. 공통 전제 (모든 단계)
- 도구 로드: `ToolSearch`에 `select:mcp__buffer__get_account,mcp__buffer__get_channel,mcp__buffer__create_post,mcp__buffer__edit_post,mcp__buffer__get_post`(정확한 이름만).
- 채널 ID·post ID는 추측하지 않는다. 사용자가 준 값 또는 `list_channels`/`list_posts` 결과만 쓴다.
- **채널 타입 확인**(`get_channel`): Instagram **개인 프로필**(`type: profile`)은 `schedulingType: notification`만 가능. `automatic`은 HTTP 400
  ("personal profile channels require notification scheduling"). 개인 프로필은 예약해도 **Buffer가 대신 올리지 않고 폰 알림만 보낸다**. [실측]
- 시각 계산은 `get_account`의 `currentTime`(오프셋 포함)을 기준으로 한다. UTC로 가정하지 않는다. `dueAt`은 ISO 8601 + 오프셋(예 `+09:00`).
- 영구 삭제(`delete_post`)는 호출하지 않는다. 사용자가 직접 하도록 안내한다.

## 0-1. 인자 이름 (도구 스키마 기준, 틀리기 쉬움)
- 기존 게시물을 가리키는 인자는 **`postId`**다(`id` 아님): `get_post`, `edit_post`, `delete_post`.
- `create_post`: `channelId`, `text`, `mode`, `schedulingType`, `saveToDraft`, `dueAt`, `assets`, `metadata`. `edit_post`: `postId` + 같은 필드(`mode`, `dueAt`, `saveToDraft`, `schedulingType`, `text`, `assets`, `metadata`).
- 응답의 게시물 식별자 필드는 `id`다. 호출 인자와 응답 필드 이름이 다르다.

## 1. 초안 생성 (게시·예약 아님)
1. `get_channel`로 타입 확인 → 2. `create_post` with `saveToDraft: true`, `mode: addToQueue`, `schedulingType`(개인 프로필이면 `notification`, 그 외 `automatic`),
   `text`는 사용자가 준 문구 그대로(한 글자도 바꾸지 않는다) → 3. `get_post` 대조.
- Instagram: `metadata.instagram = {type: "post", shouldShareToFeed: true}`, 이미지는 `assets`(공개 URL만, 로컬 파일은 `buffer-draft-media-attach`).
- Threads 연결 게시물: 바깥 `text` = 1번 항목 텍스트, `metadata.threads.thread`에 **1번부터 전부** 넣는다.
- 합격 기준: `status: draft`, `dueAt: null`, `sentAt: null`, `sharedNow: false`. 하나라도 다르면 "초안 저장 확인됨"이라고 쓰지 않는다. `scripts/postcheck.py --expect draft`.

## 2. 예약 발행 (외부 게시가 예약됨 → 사용자 요청 있을 때만)
요청이 "N분 뒤 발행/예약"이면 그 자체가 명시적 요청이다. 요청이 모호하면(초안만 만들라는 건지) 먼저 묻는다.
1. `get_post`로 현재 `text`·`metadata`·`assets`·`schedulingType`을 읽는다.
2. `edit_post` 직전에 `get_account`로 `currentTime` 확보 → `dueAt = currentTime + N분 + 처리 여유 30~45초`. 호출 한 번이 10~20초 걸려 딱 N분으로 잡으면 과거가 될 수 있다. 여유를 60초 넘게 잡으면 사용자가 말한 시각에서 크게 벗어난다(2026-10-27 실측: +1분 요청에 +93초로 잡아 정상 발행). 실제 잡은 시각을 사용자에게 알린다.
3. `edit_post`에 **`saveToDraft: false`**, `mode: "customScheduled"`, `dueAt`을 넣는다. `schedulingType`은 생략(기존 유지).
   - **`saveToDraft: false`를 빼면 `dueAt`·`shareMode: customScheduled`만 들어가고 `status`는 `draft`로 남는다. 이 상태는 발행되지 않는다.** [실측]
   - `edit_post`는 부분 병합이 아니라 전체 재검증이다: `text`, `metadata`(Instagram `type`·`shouldShareToFeed` 필수 / Threads는 `thread` 전체), `assets`(각 `image.url`, `thumbnailUrl`, `metadata.altText`)를 **다시 전부** 보낸다. 빠지면 거부되거나 값이 날아간다.
4. 재조회: `status: scheduled`, `dueAt`이 의도한 UTC 시각(KST −9h), `isCustomScheduled: true`. `scripts/postcheck.py --expect scheduled`.
5. 예약 취소·변경: `allowedActions`에 `removePostScheduledTime`·`updatePostSchedule`이 나온다. 도구로 시험하지 않았다 [문서].

## 3. 발행 트리거 (즉시 발행)
- **예약 시각 도래(자동 트리거)**: 별도 호출 없음. 시각이 되면 Buffer가 처리한다. [실측: dueAt 22:35:00 → Instagram `sentAt` +6초, Threads `sentAt` +48초]
- **즉시 발행**: `edit_post`(또는 `create_post`)의 `mode: "shareNow"`. [문서 — 이번 세션에서 시험하지 않았다] 즉시 발행은 되돌릴 수 없으므로
  사용자가 "지금 발행"을 명시했을 때만, 채널·본문·이미지를 보여 주고 확인받은 뒤 호출한다.
- `addToQueue`/`shareNext`는 채널의 게시 시간표(posting schedule)에 의존한다. [문서, 미시험] 시각을 정확히 지키려면 `customScheduled`를 쓴다.
- 조건 없이 외부에 나가는 호출(`shareNow`, 예약)은 이미 승인된 범위 밖이면 사용자에게 묻는다. 한 번의 승인을 다른 게시물로 넓히지 않는다.

## 4. 발행 후 확인 ("왜 안 올라갔어?" 포함)
`get_post`로 읽고 아래 표대로 해석한다.

| 관찰 | 의미 |
|---|---|
| `status: draft` + `dueAt` 있음 | 예약이 안 됐다(`saveToDraft:false` 누락). 2단계 3번 재실행 |
| `status: scheduled` | 시각 대기 중 |
| `status: sent` + `externalLink` 있음 | 플랫폼에 자동 게시됨(Threads). 링크 확인 |
| `status: sent` + `notificationStatus: notified` + `externalLink` 없음 | **Instagram 개인 프로필**: 알림만 보냄. 사용자가 폰에서 직접 올려야 한다. 아직 피드에 없는 게 정상 |
| `status: error` | `error` 필드 원문을 그대로 보고하고 멈춘다 |
- 발행 후 `allowedActions`가 줄어든다(`updatePost`, `deletePost` 사라짐). 수정은 불가 → 새 게시물로 처리. [실측]
- **Threads 해시태그 주의**: 발행 후 `annotations`가 `[]`가 되고 최상위 `text`에서 `#`이 빠졌다(스레드 항목 안쪽에는 `#` 유지). 태그 링크 여부는 플랫폼 화면에서 확인. [실측]
- 지표: `get_post`에 `includeMetrics: true` → Threads는 comments(수)·reactions·views·reposts·quotes. **댓글 내용은 못 읽는다.** 수동 게시한 Instagram은 `metrics: null`. 지표는 하루 단위 갱신. [실측]
- 발행한 게시물의 비공개 전환·삭제는 Buffer로 못 한다(`allowedActions`에 없음). 각 앱에서 직접. Instagram은 보관(Archive)이 나만 보기. [부분 실측]

## 5. 하지 않는 것
- 사용자 요청 없이 예약·발행하지 않는다. 초안 요청에 예약까지 하지 않는다.
- 개인 프로필 Instagram에 `automatic`을 넣지 않는다.
- 내용이 가상 서비스·테스트면 실제 계정에 나가기 전에 한 번 짚는다(사용자가 이미 알고 있으면 반복하지 않는다).
- 발행 완료를 `status: sent`만 보고 단정하지 않는다. 개인 프로필 Instagram의 `sent`는 "알림 전송"이다.

## 6. 보고 형식
채널 | post id | 변경 전→후 status | dueAt(KST) | 근거(어느 `get_post` 필드). 확인 못 한 것은 "미확인"으로 적는다.
