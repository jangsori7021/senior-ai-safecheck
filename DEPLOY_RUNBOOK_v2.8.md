# v2.8 P0 배포 Runbook

## 준비된 것
- FastAPI 서버
- Dockerfile
- `/health`
- `/api/v1/analyze-image`
- CORS allowlist 환경변수
- no-store/privacy response headers
- 이미지 크기/형식 검사
- 서버측 AI secret 구조
- structured result + Safety Gate

## 배포 환경에서 필요한 비밀값
채팅/소스코드에 키를 넣지 않는다.
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `ALLOWED_ORIGINS`

## 배포 후 순서
1. HTTPS URL의 `/health`가 200인지 확인
2. `provider_configured=true` 확인
3. 프런트의 API base를 HTTPS 서버 주소로 설정
4. 실제 휴대폰에서 사진 촬영
5. 정상/애매/위험 테스트 이미지로 결과 확인
6. false-safe, latency, failure rate 기록

## 출시 금지 조건
- HTTPS 아님
- API 키가 클라이언트에 노출됨
- 위험 샘플 false-safe 원인 미해결
- 원본 이미지가 의도치 않게 로그/스토리지에 남음
