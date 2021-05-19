from parlaparser.data_parsers.base_parser import DocxParser
from parlaparser import settings
import logging
from enum import Enum
from datetime import timedelta

class ParserState(Enum):
    HEADER = 1
    PERSON = 2
    CONTENT = 3
    VOTE = 4

class SpeechesParser(DocxParser):
    def __init__(self, data, data_storage):
        super().__init__(data_storage, data['docx_url'], 'temp_file.docx')
        logging.debug(data['session_name'])

        start_time = data['date']
        start_time = start_time + timedelta(
            hours=int(data['time'].split(':')[0]),
            minutes=int(data['time'].split(':')[1]))


        session_id = self.data_storage.add_or_get_session({
            'name': data['session_name'],
            'organization': self.data_storage.main_org_id,
            'organizations': [self.data_storage.main_org_id],
            'start_time': start_time.isoformat()
        })

        self.speeches = []
        current_person = None
        current_text = ''
        state = ParserState.HEADER
        order = 1
        for paragraph in self.document.paragraphs:
            logging.debug(paragraph.text)
            text = paragraph.text
            if self.skip_line(text):
                continue
            # if text.startswith('Prehajamo k glasovanju') or state == ParserState.VOTE:
            #     if text.startswith('Sklep je'):
            #         state = ParserState.CONTENT
            #     else:
            #         state = ParserState.VOTE
            #     continue

            if text.startswith('GOSPOD') or text.startswith('GOSPA') and state in [ParserState.HEADER, ParserState.CONTENT]:

                if state == ParserState.CONTENT:
                    person_id, added_person = data_storage.get_or_add_person(
                        current_person.strip()
                    )
                    person_party = self.data_storage.get_membership_of_member_on_date(
                        person_id,
                        start_time,
                        self.data_storage.main_org_id
                    )
                    self.speeches.append({
                        'speaker': person_id,
                        'content': current_text,
                        'session': session_id,
                        'order': order,
                        'party': person_party,
                        'start_time': start_time.isoformat()
                    })
                    order += 1
                current_person = ' '.join(text.split(' ')[1:]).lower()
                if 'doktor' in current_person:
                    current_person = current_person.replace('doktor', 'dr.')
                current_text = ''
                state = ParserState.CONTENT
                continue
            elif state == ParserState.CONTENT and len(text.strip()) > 0:
                current_text += ' ' + text.strip()
        logging.debug(self.speeches)
        self.data_storage.add_speeches(self.speeches)

    def skip_line(self, text):
        if text.startswith('------------------'):
            return True
        elif text.startswith('... ///'):
            return True
        return False


