import logging
import re
from datetime import timedelta
from enum import Enum

from parlaparser import settings
from parlaparser.data_parsers.base_parser import PdfParser


class ParserState(Enum):
    HEADER = 1
    PERSON = 2
    CONTENT = 3
    VOTE = 4


class SpeechesParserPdf(PdfParser):
    def __init__(self, data, data_storage):
        super().__init__(data_storage, data["pdf_url"], "temp_file.pdf")
        logging.debug(data["session_name"])

        for_text = r"\d+ ZA\.?"
        against_text = r"\d+ PROTI\.?"

        start_time = data["date"]
        start_time = start_time + timedelta(
            hours=int(data["time"].split(":")[0]),
            minutes=int(data["time"].split(":")[1]),
        )

        session = data_storage.session_storage.get_or_add_object(
            {
                "name": data["session_name"],
                "organization": self.data_storage.main_org_id,
                "organizations": [self.data_storage.main_org_id],
                "start_time": start_time.isoformat(),
                "mandate": self.data_storage.mandate_id,
            }
        )
        if session.is_new and data.get("session_notes", {}):
            # add notes
            link_data = {
                "session": session.id,
                "url": data["session_notes"]["url"],
                "name": data["session_notes"]["title"],
            }
            if not getattr(session, "added_notes", False):
                self.data_storage.parladata_api.links.set(link_data)
                session.added_notes = True

        if session.get_speech_count() > 0:
            logging.warning("Speeches of this session was already parsed")
            return

        self.speeches = []
        current_person = None
        current_text = ""
        state = ParserState.HEADER
        order = 1
        lines = "".join(self.pdf).split("\n")
        for line in lines:
            # text = paragraph.text -> workaround for get text from smarttags
            text = line.strip()
            if self.skip_line(text):
                continue
            # if text.startswith('Prehajamo k glasovanju') or state == ParserState.VOTE:
            #     if text.startswith('Sklep je'):
            #         state = ParserState.CONTENT
            #     else:
            #         state = ParserState.VOTE
            #     continue

            if (
                text.startswith("GOSPOD")
                or text.startswith("GOPOD")
                or text.startswith("GOSPA")
                and state in [ParserState.HEADER, ParserState.CONTENT]
            ):

                if state == ParserState.CONTENT:
                    person = data_storage.people_storage.get_or_add_object(
                        {"name": current_person.strip()}
                    )
                    results = re.findall(for_text, current_text) + re.findall(
                        against_text, current_text
                    )
                    if len(results) > 0:
                        tags = ["vote"]
                    else:
                        tags = []

                    fixed_text = self.fix_speech_content(current_text)
                    logging.debug(tags)
                    self.speeches.append(
                        {
                            "speaker": person.id,
                            "content": fixed_text.strip(),
                            "session": session.id,
                            "order": order,
                            "tags": tags,
                            "start_time": start_time.isoformat(),
                        }
                    )
                    order += 1
                current_person = " ".join(text.split(" ")[1:]).lower()
                if "doktor" in current_person:
                    current_person = current_person.replace("doktor", "dr.")
                current_text = ""
                state = ParserState.CONTENT
                continue
            elif state == ParserState.CONTENT and len(text.strip()) > 0:
                current_text += f"{text}\n"
        if current_text:
            results = re.findall(for_text, current_text) + re.findall(
                against_text, current_text
            )
            if len(results) > 0:
                tags = ["vote"]
            else:
                tags = []
            person = data_storage.people_storage.get_or_add_object(
                {"name": current_person.strip()}
            )
            self.speeches.append(
                {
                    "speaker": person.id,
                    "content": current_text.strip(),
                    "session": session.id,
                    "order": order,
                    "tags": tags,
                    "start_time": start_time.isoformat(),
                }
            )
        session.add_speeches(self.speeches)

    def skip_line(self, text):
        if text.startswith("------------------"):
            return True
        if text.strip("\n").strip("\f").isdigit():
            return True
        return False

    def para2text(self, p):
        rs = p._element.xpath(".//w:t")
        return "".join([r.text for r in rs])

    def fix_speech_content(self, content):
        repalce_chars = [("«", '"'), ("»", '"')]
        for org_char, rapcece_char in repalce_chars:
            content = content.replace(org_char, rapcece_char)

        return content
