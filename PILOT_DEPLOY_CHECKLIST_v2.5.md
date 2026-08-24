# v2.5 실제 파일럿 배포 체크리스트

## P0 — 없으면 실제 파일럿 금지
- [ ] HTTPS 스테이징 백엔드
- [ ] 서버 환경변수로 AI 키/모델 설정
- [ ] 프런트 사진 입력과 `/api/v1/analyze-image` 실제 연결
- [ ] 응답 schema validation + Safety Gate 확인
- [ ] timeout / retry / offline 복구
- [ ] 이미지 저장 기본 OFF 또는 명확한 보관정책
- [ ] 개인정보/민감정보 안내와 동의
- [ ] 위험 결과에서 민감 행동 차단

## P1 — 첫 20~30명 파일럿 전
- [ ] 실제/비식별 위험·정상·애매 이미지 세트
- [ ] false-safe 자동 집계
- [ ] 분석 latency/cost 기록
- [ ] 도움됨/안됨 버튼
- [ ] 가족 공유 consent
- [ ] 익명 referral attribution
- [ ] 삭제/기록 opt-in 흐름

## P2 — 공개 출시 전
- [ ] 접근성 실제기기 점검
- [ ] 앱스토어 개인정보 표시
- [ ] 장애/비용/abuse 모니터링
- [ ] 공식 확인 connector
- [ ] 고객지원/신고 경로
- [ ] 결제/환불/구독 UX 및 정책(유료화 시)
