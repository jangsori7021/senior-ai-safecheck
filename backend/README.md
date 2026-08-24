# v1.5 Backend Scaffold

목적: 브라우저/모바일 앱에 비밀 API 키를 넣지 않고 이미지 분석을 서버에서 수행.

실행 전:
1. Python 가상환경 생성
2. `pip install -r requirements.txt`
3. `.env.example`을 참고해 서버 환경변수 `OPENAI_API_KEY`, `OPENAI_MODEL` 설정
4. `uvicorn main:app --host 0.0.0.0 --port 8000`

현재 상태:
- /health 실제 동작
- 이미지 타입/크기 검증 실제 동작
- 서버측 API 키 구조 구현
- 멀티모달 Provider 호출 코드 구현
- 구조화 결과 Pydantic 검증 및 Safety Gate 구현
- 실제 API 호출은 유효한 서버 키와 모델 설정이 있어야 검증 가능

주의:
프로덕션에서는 CORS allowlist, 인증/익명 세션, rate limit, request timeout,
로그 비식별화, 이미지 보관/삭제 정책, abuse monitoring, 비용 한도를 추가해야 함.
