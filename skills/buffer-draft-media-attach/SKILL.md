---
name: buffer-draft-media-attach
description: |
  Buffer API는 이미지를 공개 URL로만 받는다. 이미 만든 Buffer 초안(인스타 캐러셀 등)에 카드 이미지 파일을
  agent-browser로 Buffer 웹 작성기에 직접 업로드해 첨부하고 "Save Draft"만 누르는 절차. 게시·예약은 하지 않는다.
  "Buffer 초안에 이미지 첨부", "카드 이미지 올려줘", "공개 URL 없이 이미지 붙이기" 요청 시.
category: social-media
---

# Buffer 초안에 이미지 첨부 (agent-browser, 2026-10-27 실측)

Buffer 웹 작성기는 파일을 Buffer 자체 저장소로 올리므로 **별도 공개 호스팅이 필요 없다**
(첨부 후 `get_post`의 asset url 호스트가 `buffer-media-uploads.s3.amazonaws.com`).

## 전제
- 로그인된 agent-browser 세션: `agent-browser-login-session` 스킬의 절차로 전용 Chrome(포트 9333)·세션 `buffer-pub`.
  자격 증명은 이 스킬에도 저장하지 않는다.
- 첨부할 파일: `ig-threads-format`의 `media/01.jpg`~`NN.jpg`(JPEG 1080×1350, 검증 통과분).
- 대상 초안: 채널 ID와 초안 문구 앞부분(같은 채널에 초안이 여러 개일 수 있어 문구·생성 시각으로 구분).
- 이 절차가 건드리는 것은 대상 초안 1개뿐이다. 다른 초안은 열거나 수정하지 않는다.

## 절차

```bash
ab() { agent-browser --session buffer-pub "$@"; }

# 1) 파일을 읽기 쉬운 임시 폴더로 복사(이 경로로 성공. Documents 경로 직접 사용이 문제인지는 미확인)
T=/private/tmp/buffer-media-upload; mkdir -p $T && cp <media폴더>/0*.jpg $T/

# 2) 채널 페이지 → Drafts 탭 → 대상 초안 열기
ab open "https://publish.buffer.com/channels/<channelId>/schedule"
ab wait --load networkidle
ab find role tab click --name "Drafts"
ab find text 'Edit draft "<초안 캡션 첫 부분>' click     # 작성기(Edit Draft)가 열림

# 3) 숨겨진 file input(name=file-upload-input, multiple)에 업로드 — 순서대로 파일 나열
ab upload 'input[name="file-upload-input"]' $T/01.jpg
ab upload 'input[name="file-upload-input"]' $T/02.jpg $T/03.jpg $T/04.jpg $T/05.jpg $T/06.jpg $T/07.jpg $T/08.jpg

# 4) 업로드 완료 대기: 'Cancel upload' 버튼이 0개가 될 때까지
until [ "$(ab snapshot -i -c | grep -c 'Cancel upload')" = "0" ]; do sleep 4; done

# 5) 눈으로 확인: 썸네일 순서(01→NN)와 우측 Instagram Preview의 캐러셀 점
ab screenshot <경로>/composer.png

# 6) 장별 alt text: 썸네일마다 있는 'Add description' 버튼 → "Edit Media" 대화창(Alt Text 탭, 입력 최대 1000자)
ab click @<첫 장의 Add description ref>
#    대화창 하단 탭 "Image N of M"으로 장을 바꾸며 textbox "Add a description"에 입력. 값은 장을 바꿔도 유지된다.
for n in 1..M:  ab click @<"Image n of M" 탭 ref>;  ab fill @<textbox ref> "<n번 alt text>";  ab get value @<textbox ref> 로 확인
ab click @<"Apply Changes to M Items" ref>     # 한 번에 적용, 대화창이 닫힘(이후 'Add description' 버튼이 사라짐)

# 7) 'Save Draft' 버튼만 클릭(ref는 snapshot -i -c에서 매번 다시 확인)
ab snapshot -i -c | grep -E 'button "Save Draft"'
ab click @<ref>        # 토스트 "Your post has been saved." 확인
```

**더 쉬운 대안(2026-10-27 실측):** UI에서는 이미지 업로드 + `Save Draft`까지만 하고, alt text와 본문은 MCP로 넣는다.
`get_post`로 새 asset url을 읽은 뒤 `edit_post`에 `text`(원고 그대로), `metadata.instagram`(`type`, `shouldShareToFeed` 필수),
`assets`(각 `image.url`·`thumbnailUrl`=같은 url, `metadata.altText`=표의 장별 값)를 **전부** 다시 보낸다. `saveToDraft: true`,
`schedulingType`·`mode`는 생략한다. UI의 6번(Edit Media 대화창)보다 빠르고 `get_post`로 바로 대조된다.

alt text 원본은 `ig-threads-format`의 `instagram.md` 슬라이드 표 마지막 열이다. 표에서 장별 값을 뽑아 입력한다
(`python3 -I`로 `^\|\s*(\d+)\s*\|(.*)\|\s*$` 행을 파싱).

## 이미지 교체 (이미 첨부된 초안의 이미지를 바꿀 때, 2026-10-27 실측)
작성기에서 썸네일마다 있는 `Remove image` 버튼을 모두 누른 뒤(버튼 수가 0이 될 때까지 첫 번째 ref를 반복 클릭) 위 절차 3~7을 그대로
다시 한다. 새로 올린 이미지는 alt text가 비어 있으므로 6번(alt text)도 다시 입력한다. 교체 후 `get_post`의 asset id가 모두 새 값이어야 한다
(실측: 이전 `6ae0744…` 계열 → 교체 후 `6ae07a2…` 계열). 이 절차는 첨부한 이미지만 지우며 초안 본문·설정은 건드리지 않는다.

## 반드시 지킬 것
- **누르지 않는 버튼**: `Schedule Post`, `Next Available`, `Notify Me`(예약 방식 변경), `Add to Queue`. 게시·예약·공유는 사용자가 따로 요청할 때만.
- 작성기의 `Post / Reel / Story` 라디오는 `Post`를 유지한다.
- 닫을 때는 `agent-browser --session buffer-pub close`(자기 세션만).

## 저장 후 API 검증 (읽기 전용 Buffer MCP)
`get_post`로 확인한다: `status=draft`, `dueAt`·`sentAt`=null, `sharedNow=false`, `schedulingType` 기존값,
`assets` 개수 = 카드 수, 각 asset `mime=image/jpeg`·크기 1080×1350, 각 asset `altText` = 표의 해당 장 값(2026-10-27 8장 모두 일치 확인).
초안 id는 UI 저장 후에도 바뀌지 않았다.
**이미지 순서·내용 대조**: asset url(`source`)은 공개 S3 주소라 `curl`로 내려받을 수 있다. 각 파일을 작게(54×68 흑백) 줄여 로컬 `NN.jpg`와
픽셀 차이를 재면 "Buffer N번 = 로컬 N번"이 확인된다(2026-10-27 8장 모두 차이 0.0).
게시 전에 캡처·카드 문구에서 금지 키워드(예: "모두의 창업")가 이미지 안에 남았는지도 눈으로 확인한다(텍스트 검증기는 이미지를 못 읽는다).
`list_posts`(organizationId + channelIds + status=[draft])로 다른 초안이 그대로인지도 본다.

## 함정 (실측)
- **로그인 직후에는 업로드가 전부 실패한다**: 작성기에 "Upload failed … We couldn't reach the upload server"가 뜨고
  콘솔에 "Unauthorized request". 원인은 로그인 직후 앱 세션이 덜 갖춰진 상태(추정). **채널 페이지를 다시 열면(reload) 정상**이었다.
  실패한 업로드 항목이 쌓이면 작성기를 닫고(저장 없이) 초안을 다시 연다.
- 실패 시 네트워크: `uploads.buffer.com/uploads`로 tus(재개 가능 업로드) POST가 `net::ERR_FAILED`.
  `agent-browser network requests --filter uploads.buffer.com --json`과 `console`로 확인한다.
- **페이지 로드 직후 `Drafts` 탭 클릭이 무시된다**(화면 전환이 늦어 클릭이 먹지 않음). `open` 후 3~5초 기다린 뒤 snapshot에서 탭 ref를 다시 읽어 클릭하고,
  `tab "Drafts … [selected"`가 보이는지 확인한다. 초안 버튼 이름의 따옴표는 `\"`(두 글자)라 grep은 `'Edit draft ..캡션 첫 부분'`처럼 점 두 개로 맞춘다.
- zsh에서 `rm -f dir/*.png`는 파일이 없으면 오류로 `&&` 체인을 끊는다. 렌더 전 정리는 `rm -rf dir && mkdir -p dir`로 한다.
- `ab click 'role=tab[name="…"]'` 형식은 "Element not found"였다. `ab find role tab click --name "Drafts"`와
  `ab find text '…' click`은 동작했다. ref(@eN)는 화면이 바뀔 때마다 `snapshot -i -c`로 다시 받는다.
- 작성기 하단의 `# Remaining: 2`(해시태그 3개 사용 시)는 Buffer 작성기 UI가 인스타 해시태그 5개까지 허용한다는 뜻으로 읽힌다(공식 규격은 아님 — `ig-threads-format`은 3개 이하로 제한).

## 아직 하지 않았거나 미검증
- 썸네일/커버 지정, 이미지 순서의 API 대조(asset url만으로는 순서 판별 불가 — 썸네일 화면으로만 확인).
- 8장을 한 번의 `upload` 호출로 올릴 때의 순서 보장(이번엔 1장 + 7장 두 번에 나눠 올려 01→08 순서 확인).
- 이 절차는 인스타 **개인 프로필** 채널(알림 방식, `schedulingType=notification`)에서만 확인했다. 비즈니스 계정·Threads는 미확인.
