import math
from common import client, makeup_response, gpt_num_tokens
from memory_manager import MemoryManager
from warning_agent import WarningAgent
# from pprint import pprint


class Chatbot:

    def __init__(self, model, system_role, instruction, **kwargs):
        self.context = [{'role': 'developer', 'content': system_role}]
        self.model = model
        self.instruction = instruction
        self.max_token_size = 16 * 1024
        self.kwargs = kwargs
        self.user = kwargs['user']
        self.assistant = kwargs['assistant']
        self.memoryManager = MemoryManager()
        self.context.extend(self.memoryManager.restore_chat())
        self.warningAgent = self._create_warning_agent()

    def add_user_message(self, message):
        self.context.append({'role': 'user', 'content': message, 'saved': False})

    def _is_over_token_limit(self):
        # instructions를 보수적으로 developer(system) 메시지로 합산해 계산
        token_check_target = self.to_openai_context() + [
            {"role": "developer", "content": str(self.instruction)}
        ]
        try:
            return gpt_num_tokens(token_check_target) > self.max_token_size
        except Exception:
            return False

    def _send_request(self):
        try:
            if self._is_over_token_limit():
                if self.context:
                    self.context.pop()
                return makeup_response('메시지를 조금 짧게 보내줄래?')

            response = client.responses.create(
                model=self.model,
                instructions=self.instruction,        # 지시문은 여기서만 전달
                input=self.to_openai_context()        # saved 등 커스텀 키 제거
            )
            return response

        except Exception as e:
            print(f'> Exception 오류({type(e)}) 발생:{e} ')
            return makeup_response('[내 챗봇에 문제가 발생했습니다. 잠시 뒤 이용해주세요]')

    def send_request(self):
        try:
            if not getattr(self, "warningAgent", None):
                self.warningAgent = self._create_warning_agent()

            # 전체 컨텍스트 기반 안전성 점검
            if self.warningAgent.monitor_user(self.to_openai_context()):
                return makeup_response(self.warningAgent.warn_user())

            response = self._send_request()

            self.handle_token_limit(response)
            return response

        except Exception as e:
            print(f'> Exception 오류({type(e)}) 발생:{e} ')
            return makeup_response('[내 챗봇에 문제가 발생했습니다. 잠시 뒤 이용해주세요]')

    def add_response(self, response):
        self.context.append({
            'role': response.output[-1].role,
            'content': response.output_text,
            'saved': False
        })

    def get_last_response(self):
        return self.context[-1]['content']

    def to_openai_context(self):
        return [{'role': v['role'], 'content': v['content']} for v in self.context]

    def save_chat(self):
        self.memoryManager.save_chat(self.context)

    def handle_token_limit(self, response):
        try:
            if response['usage']['total_tokens'] > self.max_token_size:
                remove_size = math.ceil(len(self.context) / 10)
                self.context = [self.context[0]] + self.context[remove_size+1:]
        except Exception as e:
            print(f'> handle_token_limit exception:{e}')

    def _create_warning_agent(self):
        return WarningAgent(
                    model=self.model,
                    user=self.user,
                    assistant=self.assistant,
               )
