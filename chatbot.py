import math
from common import client, makeup_response, gpt_num_tokens
from memory_manager import MemoryManager
from warning_agent import WarningAgent

import threading
import time
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
        self.memoryManager = MemoryManager(user=self.user, assistant=self.assistant)
        self.context.extend(self.memoryManager.restore_chat())
        self.warningAgent = self._create_warning_agent()
        # 데몬 스레드 시작
        bg_thread = threading.Thread(target=self.background_task, daemon=True)
        bg_thread.start()
    def background_task(self):
        while True:
            self.save_chat()
            self.memoryManager.build_memory()
            time.sleep(3600)
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

    def _send_request(self, extra_instruction: str = ""):
        try:
            if self._is_over_token_limit():
                if self.context:
                    self.context.pop()
                return makeup_response('메시지를 조금 짧게 보내줄래?')

                # 기본 instruction + 메모리 지시문
            instructions = self.instruction + extra_instruction
            print("> new_instructions: :",instructions)

            response = client.responses.create(
                model=self.model,
                instructions=instructions,
                input=self.to_openai_context()
            )
            return response

        except Exception as e:
            print(f'> Exception 오류({type(e)}) 발생:{e} ')
            return makeup_response('[내 챗봇에 문제가 발생했습니다. 잠시 뒤 이용해주세요]')

    def retrieve_memory(self):
        user_message = self.context[-1]['content']
        if not self.memoryManager.needs_memory(user_message):
            return

        memory = self.memoryManager.retrieve_memory(user_message)
        if memory is not None:
            return memory
        else:
            return '[NO_MEMORY_FOUND]'
    def send_request(self):
        try:
            if not getattr(self, "warningAgent", None):
                self.warningAgent = self._create_warning_agent()

            extra_instruction = ""

            if getattr(self, "memoryManager", None):
                mem = self.retrieve_memory()

                if mem is not None:
                    if mem == "[NO_MEMORY_FOUND]":
                        # 기억 못 찾은 경우
                        extra_instruction += """\n
            [기억 관련 지시]
            이번 사용자의 질문과 연관된 과거 대화를 벡터 DB에서 찾지 못했다.
            만약 사용자가 "예전에 말해줬잖아?"처럼 과거 대화를 기대하는 뉘앙스를 보였다면,
            정확한 내용을 기억하지 못한다고 솔직하게 말하고,
            다시 상황이나 조건을 설명해달라고 요청하라.
            """
                    else:
                        # 기억을 찾은 경우
                        extra_instruction += f"""\n
            [대화 기억]
            아래는 사용자가 과거에 했던 대화의 요약이다. 이 내용을 현재 질문과 함께 참고해서 자연스럽게 답변하라.
            사용자에게는 "예전에 말했던 것처럼..." 정도로 필요할 때만 간단히 언급하고,
            불필요하게 장황하게 과거 내용을 나열하지 말 것.

            --- 과거 대화 요약 ---
            {mem}
            --------------------
            """

            #전체 컨텍스트 기반 안전성 점검
            if self.warningAgent.monitor_user(self.to_openai_context()):
                return makeup_response(self.warningAgent.warn_user())

            response = self._send_request(extra_instruction=extra_instruction)

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
