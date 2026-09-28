# gstack-cowork

[garrytan/gstack](https://github.com/garrytan/gstack)(MIT)를 **Claude Cowork**(Claude 데스크톱 앱)에서 쓸 수 있도록
플러그인 마켓플레이스 형태로 다시 포장한 비공식 저장소입니다. `build.py`가 로컬 gstack 체크아웃
(`~/.claude/skills/gstack`)에서 자동 생성합니다.

## 왜 필요한가

- Cowork는 `~/.claude/skills`를 읽지 않습니다. 스킬은 계정에 동기화된 플러그인/스킬만 로드됩니다.
- Cowork 작업은 Linux VM 샌드박스에서 실행되므로 gstack의 `bin/`(bash + bun 런타임), 번들 브라우저,
  `~/.gstack` 상태 파일이 존재하지 않습니다.
- gstack에는 아직 `--host cowork`가 없습니다 (upstream issue #1345).

그래서 이 저장소는 **프롬프트(SKILL.md + 참고 문서)만** 담고, 다음 변환을 적용합니다.

| 변환 | 이유 |
|---|---|
| `~/.claude/skills/gstack/…` → `${CLAUDE_PLUGIN_ROOT}/…` | 플러그인 내부 경로로 참조 |
| 프리앰블(`gstack-skill-start`) → Cowork 스텁 | 런타임 부재를 "정상 상태"로 처리, setup 안내 제거 |
| frontmatter `hooks:` 제거 | Cowork 플러그인은 hooks 미지원 (autoplan의 hook은 스크립트가 없으면 Read를 차단하므로 필수) |
| 각 SKILL.md 상단 Cowork 안내 블록 삽입 | bin/ 호출 실패를 무시하고 프로즈 워크플로우로 진행하도록 지시 |

## Cowork에 설치하기

1. Claude 데스크톱 앱 → **Cowork** 탭 → 왼쪽 **Customize(맞춤 설정)** → **Plugins**
2. **Add(+)** → **Add marketplace** → **Add from a repository**
3. 저장소 입력: `kooock/gstack-cowork` (또는 `https://github.com/kooock/gstack-cowork`)
4. 마켓플레이스에서 **gstack** 설치. 필요하면 **gstack-extras**도 설치 (아래 주의 참고)
5. Cowork 대화에서 `/office-hours`, `/plan-ceo-review`, `/review` 처럼 사용

플러그인은 계정 단위로 동기화되므로 Claude Code에도 나타날 수 있습니다. Claude Code에 이미 gstack이
네이티브로 설치돼 있다면 그쪽에서는 이 플러그인을 **비활성화**하세요 (`/plugin` → gstack@gstack-cowork → disable).
중복 스킬 목록만 늘어납니다.

## 포함 스킬

**gstack (core, 24개)** — 런타임 없이도 프롬프트만으로 동작하는 스킬
`gstack`(라우터), `office-hours`, `plan-ceo-review`, `plan-eng-review`, `plan-design-review`, `plan-devex-review`,
`autoplan`, `spec`, `review`, `investigate`, `retro`, `health`, `document-generate`, `document-release`,
`deslop-shared-libs`, `learn`, `context-save`, `context-restore`, `plan-tune`, `ship`, `landing-report`,
`setup-deploy`, `design-html`, `design-consultation`

**gstack-extras (27개, 실험용)** — gstack 번들 브라우저·iOS 시뮬레이터·codex·gbrain·docker 등 호스트 도구가 필요한 스킬.
Cowork에서는 해당 단계가 실패하거나 축소 동작합니다: `browse`, `qa`, `qa-only`, `design-review`, `design-shotgun`,
`devex-review`, `land-and-deploy`, `canary`, `diagram`, `make-pdf`, `scrape`, `skillify`, `pair-agent`,
`connect-chrome`, `open-gstack-browser`, `setup-browser-cookies`, `benchmark`, `benchmark-models`, `codex`, `cso`,
`ios-*`(5), `setup-gbrain`, `sync-gbrain`

**제외 (5개)** — `careful`, `guard`, `freeze`, `unfreeze`(PreToolUse hook 전용이라 hook이 없으면 "보호 중"이라고
말만 하는 위험한 상태가 됨), `gstack-upgrade`(VM 안에서 의미 없음)

## gstack 업그레이드 후 갱신

```bash
# Claude Code에서 /gstack-upgrade 실행 후
cd ~/epsilonDelta/projects/gstack-cowork
python3 build.py            # ~/.claude/skills/gstack 기준으로 plugins/ 재생성
claude plugin validate .    # 선택
git add -A && git commit -m "gstack $(cat ~/.claude/skills/gstack/VERSION)" && git push
```

Cowork는 마켓플레이스를 주기적으로 다시 동기화합니다. 바로 반영하려면 Plugins 화면에서 마켓플레이스를 새로고침하세요.

## 알려진 한계

- 텔레메트리, 질문 선호도(`/plan-tune`), 결정/학습 로그 등 `bin/` 기반 기능은 Cowork에서 모두 no-op입니다.
- `${CLAUDE_PLUGIN_ROOT}`가 Cowork 런타임에서 설정되지 않으면 참고 문서 경로 해석이 실패할 수 있습니다.
  각 SKILL.md 상단 안내가 대체 규칙(플러그인 디렉터리 기준)을 제공합니다.
- upstream이 `--host cowork`를 공식 지원하면 이 저장소는 필요 없어집니다.

## License

MIT. gstack © 2026 Garry Tan. 이 저장소는 재배포/재포장본이며 원본 LICENSE를 그대로 포함합니다.
