import json
import requests
from pprint import pprint
from common import client, model, makeup_response
import yfinance as yf
from tavily import TavilyClient
import os
tavily = TavilyClient(api_key=os.getenv('TAVILY_API_KEY'))

# 위도 경도
global_lat_lon = {
           '서울':[37.57,126.98],'강원도':[37.86,128.31],'경기도':[37.44,127.55],
           '경상남도':[35.44,128.24],'경상북도':[36.63,128.96],'광주':[35.16,126.85],
           '대구':[35.87,128.60],'대전':[36.35,127.38],'부산':[35.18,129.08],
           '세종시':[36.48,127.29],'울산':[35.54,129.31],'전라남도':[34.90,126.96],
           '전라북도':[35.69,127.24],'제주도':[33.43,126.58],'충청남도':[36.62,126.85],
           '충청북도':[36.79,127.66],'인천':[37.46,126.71],
           'Boston':[42.36, -71.05], '도쿄':[35.68, 139.69]
          }

# 화폐 코드
global_currency_code = {'달러': 'USD', '엔화': 'JPY', '유로화': 'EUR', '위안화': 'CNY', '파운드': 'GBP'}


def get_celsius_temperature(**kwargs):
    location = kwargs['location']
    lat_lon = global_lat_lon.get(location, None)
    if lat_lon is None:
        return None
    lat = lat_lon[0]
    lon = lat_lon[1]

    # API endpoint
    url = f'https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true'

    # API를 호출하여 데이터 가져오기
    response = requests.get(url)
    # 응답을 JSON 형태로 변환
    data = response.json()
    # 현재 온도 가져오기 (섭씨)
    temperature = data['current_weather']['temperature']

    print('> temperature:', temperature)
    return temperature


def get_currency(**kwargs):
    currency_name = kwargs['currency_name']
    currency_name = currency_name.replace('환율', '')
    currency_code = global_currency_code.get(currency_name, 'USD')

    if currency_code is None:
        return None

    response = requests.get(f'https://api.exchangerate-api.com/v4/latest/{currency_code}')
    data = response.json()
    krw = data['rates']['KRW']

    print('> 환율:', krw)
    return krw


def get_stock_price(**kwargs):
    ticker = kwargs['ticker'].upper().strip()
    try:
        tk = yf.Ticker(ticker)

        info = getattr(tk, 'fast_info', {}) or {}
        price = info.get("last_price")
        currency = info.get("currency", "USD")

        if price is None:
            df = tk.history(
                period="5d", interval="1d",
                auto_adjust=False, prepost=False,
                raise_errors=True, timeout=20
            )
            if df is None or df.empty:
                raise RuntimeError("Empty dataframe from history()")
            price = float(df["Close"].iloc[-1])

        return f"> {ticker} 현재가:{price} {currency}"

    except Exception as e:
        return f"[ERROR:get_stock_price] {ticker} 조회 실패 - {type(e).__name__}: {e}"

def search_internet(**kwargs):
    print("search_internet", kwargs)
    answer = tavily.search(query=kwargs['search_query'], include_answer=True)['answer']
    print("answer: ", answer)
    return answer

tools = [
            {
                'type': 'function',
                'name': 'get_celsius_temperature',
                'description': '지정된 위치의 현재 섭씨 날씨 확인',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'location': {
                            'type': 'string',
                            'description': '광역시도, e.g. 서울, 경기',
                        }
                    },
                    'required': ['location'],
                },
            },
            {
                'type': 'function',
                'name': 'get_currency',
                'description': '지정된 통화의 원(KRW) 기준의 환율 확인.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'currency_name': {
                            'type': 'string',
                            'description': '통화명, e.g. 달러환율, 엔화환율',
                        }
                    },
                    'required': ['currency_name'],
                },
            },
            {
                'type': 'function',
                'name': 'get_stock_price',
                'description': '주식 또는 ETF의 현재 주가를 조회합니다.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'ticker': {
                            'type': 'string',
                            'description': '주식 티커 (예: AAPL, TSLA, 005930.KS 등)',
                        }
                    },
                    'required': ['ticker'],
                },
            },
            {
                "type": "function",
                "name": "search_internet",
                "description": "답변 시 인터넷 검색이 필요하다고 판단되는 경우 수행",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "search_query": {
                            "type": "string",
                            "description": "인터넷 검색을 위한 검색어" } },
                    "required": ["search_query"]
                }
            }
        ]

class FunctionCalling:
    def __init__(self, model,instruction=None):
        self.model = model
        self.instruction = instruction
        self.available_functions = {
            "get_currency": get_currency,
            "get_celsius_temperature": get_celsius_temperature,
            "get_stock_price": get_stock_price,
            "search_internet": search_internet
        }


    def analyze(self, user_message, tools):
        try:
            response = client.responses.create(
                model=self.model,
                input=[{"role": "user", "content": user_message}],
                tools=tools,
                tool_choice="auto"
            )
            return response, "function_call"
        except Exception as e:
            print("Error occurred(analyze):", e)
            return makeup_response("[analyze 오류입니다]"), "error"


    def run(self, previous_response, context):
        try:
            tool_calls = [
                item for item in previous_response.output
                if item.type == "function_call"
            ]

            if not tool_calls:
                return makeup_response("도구 호출이 없었습니다.")

            # 각 함수 실행 결과를 담을 리스트
            function_outputs = []

            for call in tool_calls:
                func_name = getattr(call, "name", None) or getattr(call.function, "name", None)
                func_to_call = self.available_functions.get(func_name)
                func_args_json = getattr(call, "arguments", "{}") or "{}"
                func_args = json.loads(func_args_json)

                if func_to_call:
                    func_response = func_to_call(**func_args)
                else:
                    func_response = f"[알 수 없는 함수 호출: {func_name}]"

                function_outputs.append({
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": str(func_response)
                })

            sanitized_context = [
                {"role": m["role"], "content": m["content"]}
                for m in context
                if "role" in m and "content" in m
            ]

            full_input = sanitized_context + function_outputs

            final_response = client.responses.create(
                model=self.model,
                input=full_input,
                previous_response_id=previous_response.id,
                instructions = self.instruction
            )
            return final_response

        except Exception as e:
            print("Error occurred(run):", e)
            return makeup_response("[run 오류입니다]")
