# 시니어 AI 생활플랫폼 v5.3 Cloudflare 배포

## 목표
Render 없이 Cloudflare Workers + Static Assets 한 곳에서 앱 화면과 AI API를 함께 운영합니다.

## 처음 한 번만
1. Cloudflare 대시보드 → Workers & Pages → Create → Import a repository.
2. GitHub 저장소 `jangsori7021/senior-ai-safecheck` 선택.
3. Framework preset은 None, Build command는 비워 둡니다.
4. Deploy command는 `npx wrangler deploy`를 사용합니다.
5. Settings → Variables and Secrets → Secret 추가: `OPENAI_API_KEY`.
6. 저장 후 Deploy.

## 이후 업데이트
GitHub main에 새 커밋이 들어오면 Cloudflare의 Git 연결 자동 배포를 사용합니다. 수동 ZIP 업로드가 필요 없습니다.

## 확인
- `/health`에 `platform: cloudflare`, `version: 5.3`가 보이는지 확인합니다.
- 첫 화면이 열리고 말로 부탁하기/글자로 묻기/사진 분석이 정상인지 확인합니다.
- 생활 한눈에에서 문자 써줘, 뭐 해 먹지, 분리배출, 휴대폰 도움, 가까운 곳 찾기를 확인합니다.

## 전환 원칙
새 Cloudflare 주소에서 사진 분석과 AI 질문까지 정상 확인하기 전에는 기존 Render 서비스를 삭제하지 않습니다. 정상 확인 후 홈 화면 PWA를 새 Cloudflare 주소로 다시 설치하면 됩니다.
