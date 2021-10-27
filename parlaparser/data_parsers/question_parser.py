from parlaparser.data_parsers.base_parser import BaseParser
from parlaparser import settings
from enum import Enum
from datetime import datetime, timedelta
import logging
import re


class QuestionParser(BaseParser):
    def __init__(self, data, data_storage):
        super().__init__(data_storage)
        logging.debug(data['session_name'])

        start_time = data['date']
        start_time = start_time + timedelta(
            hours=int(data['time'].split(':')[0]),
            minutes=int(data['time'].split(':')[1]))

        self.start_time = start_time


        session_id, added = self.data_storage.add_or_get_session({
            'name': data['session_name'],
            'organizations': [self.data_storage.main_org_id],
            'start_time': start_time.isoformat()
        })
        if added and 'session_notes' in data.keys():
            # add notes
            link_data = {
                'session': session_id,
                'url': data['session_notes']['url'],
                'name': data['session_notes']['title'],
            }
            self.data_storage.set_link(link_data)

        self.session_id = session_id

        agenda_item_id, added = self.data_storage.get_or_add_agenda_item({
            'name': data['agenda_name'].strip(),
            'datetime': start_time.isoformat(),
            'session': session_id,
            'order': data['order']
        })
        self.agenda_item_id = agenda_item_id

        url = data['url']
        text = data['text']

        splited_text = text.split('-')
        if len(splited_text) != 2:
            return

        question_text = splited_text[1].strip()
        mixed_text = splited_text[0]

        question_type = 'unkonwn'
        question_slo_type = ''

        if 'odgovor' in mixed_text.lower():
            return

        if 'pobud' in mixed_text.lower():
            question_type = 'initiative'
            question_slo_type = 'Pobuda'

        if 'vprašanj' in mixed_text.lower() or 'vprašanj' in mixed_text.lower():
            question_type = 'question'
            question_slo_type = 'Vprašanje'

        author = self.find_name(mixed_text)

        if not author:
            return

        question_data = {
            'title': question_text,
            'session': session_id,
            'timestamp': self.start_time.isoformat(),
            'type_of_question': question_type
        }
        if self.data_storage.check_if_question_is_parsed(question_data):
            return
        question_data.update(author)

        question = self.data_storage.set_question(question_data)

        question_id = question['id']

        self.data_storage.set_link({
            'agenda_item': self.agenda_item_id,
            'question': question_id,
            'url': f'{settings.BASE_URL}{url}',
            'name': f'{question_slo_type}{":" if question_slo_type else ""} {question_text}'
        })


    def find_name(self, mixed_text):
        person_name = None
        if 'v pisnega' in mixed_text:
            start = mixed_text.index("v pisnega")
            mixed_text = mixed_text[:start].strip()
        if 'svetnika' in mixed_text.lower():
            person_name = mixed_text.split('svetnika')[1].strip()

        elif 'svetnice' in mixed_text.lower():
            person_name = mixed_text.split('svetnice')[1].strip()

        elif 'svetniškega kluba' in mixed_text.lower():
            org_name = mixed_text.split('Svetniškega kluba')[1].strip()
            return {}

        if person_name:
            person_id, added_person = self.data_storage.get_or_add_person(
                person_name,
                name_type='genitive'
            )
        else:
            logging.debug(f'Cannot find peson name: {mixed_text}')
            raise Exception(f'Cannot find peson name: {mixed_text}')
        return {'authors': [person_id]}
