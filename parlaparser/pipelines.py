import logging

from parladata_base_api.storages.agenda_item_storage import AgendaItem
from parladata_base_api.storages.question_storage import Question
from parladata_base_api.storages.session_storage import Session
from parladata_base_api.storages.storage import DataStorage
from parladata_base_api.storages.vote_storage import Motion

from parlaparser.data_parsers.agenda_item_parser import AgendaItemParser
from parlaparser.data_parsers.committee_parser import CommitteeParser
from parlaparser.data_parsers.committee_session_parser import CommitteeSessionParser
from parlaparser.data_parsers.person_parser import PersonParser
from parlaparser.data_parsers.question_parser import QuestionParser
from parlaparser.data_parsers.speeches_parser_docx import SpeechesParserDocx
from parlaparser.data_parsers.speeches_parser_pdf import SpeechesParserPdf
from parlaparser.data_parsers.vote_parser import VoteParser
from parlaparser.settings import (
    API_AUTH,
    API_URL,
    MAIN_ORG_ID,
    MANDATE,
    MANDATE_STARTIME,
)


class ParlaparserPipeline:
    def __init__(self, *args, **kwargs):
        super(ParlaparserPipeline, self).__init__(*args, **kwargs)
        logging.warning("........::Start parser:........")
        self.storage = DataStorage(
            MANDATE, MANDATE_STARTIME, MAIN_ORG_ID, API_URL, API_AUTH[0], API_AUTH[1]
        )

        Session.keys = ["name", "organizations", "mandate"]
        Motion.keys = ["session", "datetime"]
        Question.keys = ["title", "timestamp"]
        AgendaItem.keys = ["name", "session"]

    def process_item(self, item, spider):
        if item["type"] == "person":
            PersonParser(item, self.storage)
        elif item["type"] == "speeches-docx":
            SpeechesParserDocx(item, self.storage)
        elif item["type"] == "speeches-pdf":
            SpeechesParserPdf(item, self.storage)
        elif item["type"] == "vote":
            VoteParser(item, self.storage)
        elif item["type"] == "question":
            QuestionParser(item, self.storage)
        elif item["type"] == "memberships":
            CommitteeParser(item, self.storage)
        elif item["type"] == "agenda-item":
            AgendaItemParser(item, self.storage)
        elif item["type"] == "committee-agenda-items":
            CommitteeSessionParser(item, self.storage)
        return item
