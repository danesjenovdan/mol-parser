import logging
import re
from datetime import datetime, timedelta
from enum import Enum

from parlaparser import settings
from parlaparser.data_parsers.base_parser import BaseParser


class QuestionParser(BaseParser):
    def __init__(self, data, data_storage):
        super().__init__(data_storage)
        logging.debug(data["session_name"])

        start_time = data["date"]
        start_time = start_time + timedelta(
            hours=int(data["time"].split(":")[0]),
            minutes=int(data["time"].split(":")[1]),
        )

        self.start_time = start_time

        session = self.data_storage.session_storage.get_or_add_object(
            {
                "name": data["session_name"].strip(),
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

        self.session = session

        agenda_item = session.agenda_items_storage.get_or_add_object(
            {
                "name": data["agenda_name"].strip(),
                "datetime": start_time.isoformat(),
                "session": session.id,
                "order": data["order"],
            }
        )

        url = data["url"]
        text = data["text"]

        splited_text = text.split("-")
        if len(splited_text) != 2:
            return

        question_text = splited_text[1].strip()
        mixed_text = splited_text[0]

        question_type = "unkonwn"
        question_slo_type = ""

        if "odgovor" in mixed_text.lower():
            return

        if "pobud" in mixed_text.lower():
            question_type = "initiative"
            question_slo_type = "Pobuda"

        if "vprašanj" in mixed_text.lower() or "vprašanj" in mixed_text.lower():
            question_type = "question"
            question_slo_type = "Vprašanje"

        author = self.find_name(mixed_text)

        if not author:
            return

        question_data = {
            "title": question_text,
            "session": session.id,
            "mandate": self.data_storage.mandate_id,
            "timestamp": self.start_time.isoformat(),
            "type_of_question": question_type,
        }
        if self.data_storage.question_storage.check_if_question_is_parsed(
            question_data
        ):
            return
        question_data.update(author)

        question = self.data_storage.question_storage.get_or_add_object(question_data)

        self.data_storage.parladata_api.links.set(
            {
                "agenda_item": agenda_item.id,
                "question": question.id,
                "url": f"{settings.BASE_URL}{url}",
                "name": f'{question_slo_type}{":" if question_slo_type else ""} {question_text}',
            }
        )

    def find_name(self, mixed_text):
        person_name = None
        if "v pisnega" in mixed_text:
            start = mixed_text.index("v pisnega")
            mixed_text = mixed_text[:start].strip()
        if "svetnika" in mixed_text.lower():
            person_name = mixed_text.split("svetnika")[1].strip()

        elif "svetnice" in mixed_text.lower():
            person_name = mixed_text.split("svetnice")[1].strip()

        elif re.findall(r"\wvetniškega klub.", mixed_text.lower()):
            # org_name = mixed_text.split('Svetniškega kluba')[1].strip()
            org_name = re.split(r"\wvetniškega klub.", mixed_text.lower())[1].strip()
            if org_name:
                organization = self.data_storage.organization_storage.get_or_add_object(
                    {"name": org_name, "parser_names": org_name, "classification": "pg"}
                )
                return {"organization_authors": [organization.id]}
            else:
                return {}

        if person_name:
            person = self.data_storage.people_storage.get_or_add_object(
                {"name": person_name}, name_type="genitive"
            )
        else:
            logging.debug(f"Cannot find peson name: {mixed_text}")
            raise Exception(f"Cannot find peson name: {mixed_text}")
        return {"person_authors": [person.id]}
