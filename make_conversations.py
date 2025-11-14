import json
from common import client, model

TOPICS = ["월급 관리", "식비/고정비 절감", "경제 공부 루틴", "투자 조언", "시간 관리"]

def build_prompt(topic: str) -> str:
    head = f"-대화의 주제는 {topic} 입니다.\n"
    body = """
-사용자 민수와 인공지능 챗봇 고비 사이의 자연스러운 일상 대화 데이터를 만들어야 합니다.
-샘플 형식은 아래와 같은 JSON 타입입니다.
'''
{
    "data":
            [
                {"민수": "안녕하세요. 선생님"},
                {"고비": "안녕 민수야, 요즘 잘 지내고 있어?"},
                {"민수": "요즘은 월급 관리와 저축에 대해 고민이 있어요."},
                {"고비": "처음 돈을 벌기 시작하면 당연히 갖게 되는 고민이지. 구체적으로 어떤 고민인지 알려주면 내가 조언을 줄게."},
                {"민수": "저축을 하고 싶은데, 어느 정도 수준으로, 어떤 방법으로 해야할 지 모르겠어요."}
            ]
}
'''
-주고 받는 대화의 수는 총 10개여야 합니다.
-출력은 JSON 데이터 외에 다른 부가 정보를 포함하지 않습니다.
-"```json"과 같은 부가 정보를 포함하지 않습니다.

'''
챗봇 고비에게 부여된 역할은 다음과 같습니다:
당신은 경제학 전공으로 오랜 기간 금융권(리서치, 자산운용, 리스크관리)에 몸담았다가 은퇴한 투자 조언가 고비다.
지금은 개인투자자들에게 현실적인 금융 조언을 해주면서, 민수의 인생 선배이자 친구처럼 대화한다.
처음 인사할 때는 "안녕 민수야,"로 시작하고, 그날의 날씨나 기분을 자연스럽게 곁들이면서 다음 질문을 유도한다.
대화는 투자·경제뿐 아니라 일상 고민, 습관, 시간 관리 등 현실적인 주제도 편하게 다룬다.
답변할 땐 따뜻하지만 솔직하고, 근거가 있는 현실적 조언을 우선한다.
[!IMPORTANT] 민수가 먼저 꺼내지 않으면 피해야 할 주제:
- 단기 매매 타이밍, 특정 종목·코인 추천, 고위험 투자 권유
- 불법적 절세, 내부정보, 급등주 언급
언제나 사람 중심의 시각으로, 돈을 삶의 일부로 바라본다.
'''
""".strip()
    return (head + "\n" + body)


conversations = []
MAX_RETRY = 3

for i in range(5):
    for attempt in range(1, MAX_RETRY + 1):
        try:
            response = client.responses.create(
                model=model.basic,
                input=[
                    {'role': 'developer', 'content': '당신은 유능한 극작가입니다.'},
                    {'role': 'user', 'content': build_prompt(TOPICS[i])}
                ],
                max_output_tokens=6000
            )
            content = response.output_text
            print('>', content)

            # JSON 로드
            conversation = json.loads(content)['data']
            print(f'{i+1}번째 종료 (시도 {attempt})\n')
            conversations.append(conversation)
            break
        except Exception as e:
            print(f'예외 발생 (시도 {attempt}/{MAX_RETRY}), 재시도합니다. topic={TOPICS[i]} | {e}')


# conversations 리스트를 JSON 파일로 저장
with open('대화원천내용.json', 'w', encoding='utf-8') as f:
    json.dump(conversations, f, ensure_ascii=False, indent=4)