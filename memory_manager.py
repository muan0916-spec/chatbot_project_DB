import os
from pymongo import MongoClient

from common import today

mongo_cluster = MongoClient(os.getenv('MONGO_CLUSTER_URI'))
mongo_chats_collection = mongo_cluster['jjinchin']['chats']


class MemoryManager:

    def save_chat(self, context, date=None):
        """
        스트림릿 환경에서 대화 한 턴이 끝날 때마다 호출된다고 가정하고,
        아직 DB에 저장되지 않은 메시지(saved=False)만 MongoDB에 저장한다.
        저장이 끝나면 해당 메시지의 saved를 True로 바꾸어
        다음 호출 때는 중복 저장되지 않도록 한다.
        """
        save_date = date if date is not None else today()

        # 1) 아직 저장 안 된 메시지만 골라오기
        unsaved_messages = [
            m for m in context
            if not m.get('saved', False)  # saved가 없거나 False인 것만
        ]

        if not unsaved_messages:
            return  # 새로 저장할 메시지가 없으면 바로 종료

        # 2) MongoDB에 저장할 도큐먼트 구성
        docs = [
            {
                'date': save_date,
                'role': m['role'],
                'content': m['content'],
            }
            for m in unsaved_messages
        ]

        # 3) MongoDB에 일괄 저장
        mongo_chats_collection.insert_many(docs)

        # 4) 방금 저장한 메시지들에 saved=True 표시
        for m in context:
            if not m.get('saved', False):
                m['saved'] = True

    def restore_chat(self, date=None):
        """
        기본값으로 오늘 날짜의 대화만 복원한다.
        복원된 메시지는 이미 DB에 있는 것이므로 saved=True를 붙여서 반환한다.
        """
        search_date = date if date is not None else today()
        search_results = mongo_chats_collection.find({'date': search_date})

        restored_chat = [
            {
                'role': v['role'],
                'content': v['content'],
                'saved': True  # 이미 DB에 있으므로 True
            }
            for v in search_results
        ]
        return restored_chat