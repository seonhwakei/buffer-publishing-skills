# Buffer createPost 스키마 메모 (2026-10-27 introspect_schema 기준)

> 스키마 조회 결과 요약이며, 실제 createPost 호출로 검증한 내용이 아니다. 스키마는 바뀔 수 있다.

## CreatePostInput
- `channelId: ChannelId!` (필수)
- `mode: ShareMode!` (필수): `addToQueue`, `customScheduled`, `shareNext`, `shareNow`
- `schedulingType: SchedulingType!` (필수): `automatic`(자동 게시), `notification`(앱 알림 후 수동 게시)
- `assets: [AssetInput!]!` (기본 `[]`)
- `text: String`, `dueAt: DateTime`(`customScheduled`일 때), `metadata: PostInputMetaData`
- `saveToDraft: Boolean`, `draftId`, `ideaId`, `tagIds`, `needsApproval`(기본 false), `aiAssisted`, `source`

## AssetInput (@oneOf: 항목당 하나)
- `image: { url!, thumbnailUrl, metadata: { altText!, userTags[{handle,x,y}], animatedThumbnail } }`
- `video: { url!, thumbnailUrl, metadata: { title, thumbnailOffset } }`
- `document: { url!, title!, thumbnailUrl! }`
- `link`은 deprecated(2026-12-15 제거 예정). 대신 `metadata.<service>.linkAttachment` 사용.

## Instagram: `metadata.instagram` (InstagramPostMetadataInput)
- `type: PostType!` (필수): `post`, `carousel`, `reel`, `story` 등
- `shouldShareToFeed: Boolean!` (필수)
- 선택: `firstComment`, `link`, `geolocation{id,text}`, `stickerFields{music,text,topics,products,other}`, `isAiGenerated`
- 이미지·영상은 상위 `assets`에 넣는다. 캐러셀은 이미지 여러 개 + `type: carousel`.
- 채널 `InstagramMetadata.defaultToReminders`가 true면 `schedulingType: notification`과 짝을 맞춘다.

## Threads: `metadata.threads` (ThreadsPostMetadataInput)
- `type: PostType` 선택(Instagram과 달리 필수 아님)
- `thread: [ThreadedPostInput!]`: 각 항목 `{ text, assets[], metadata: { threads: { linkAttachment } } }`
- 선택: `linkAttachment{url!, title, description, thumbnail{url!}}`, `topic`, `locationId`, `locationName`
- 조직 한도에 `scheduledThreadsPerChannel`이 별도로 있다.

## 초안(draft) 만드는 방법
1. `createPost` + `saveToDraft: true`: 채널에 붙은 초안(`PostStatus.draft`). `mode`·`schedulingType`은 여전히 필수.
2. `createContentItemDraft`: 채널 없이 조직 단위 초안. 입력 `{ organizationId!, draft: { text!, assets[], aiAssisted }, title, targetDate, tagIds }`. 이후 `promoteContentItemDraftToPosts(id, posts: [CreatePostInput!])`로 채널별 게시물화.
3. `createIdea`: Ideas 보드에 아이디어로 저장. 게시 대기열과 별개.

`editPost`도 `saveToDraft`와 `mode`를 받는다. 기존 게시물을 초안으로 되돌리거나 예약으로 바꿀 때 쓸 수 있다(호출 검증 전 추측).