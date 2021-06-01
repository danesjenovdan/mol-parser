from parlaparser.data_parsers.base_parser import PdfParser
from parlaparser import settings
from enum import Enum
from datetime import datetime, timedelta
import logging
import re

class ParserState(Enum):
    META = 1
    TITLE = 2
    RESULT = 3
    CONTENT = 4
    VOTE = 5
    PRE_TITLE = 6

class VoteParser(PdfParser):
    def __init__(self, data, data_storage):
        super().__init__(data_storage, data['pdf_url'], 'temp_file.pdf')
        logging.debug(data['session_name'])

        start_time = data['date']
        start_time = start_time + timedelta(
            hours=int(data['time'].split(':')[0]),
            minutes=int(data['time'].split(':')[1]))

        self.start_time = start_time


        session_id = self.data_storage.add_or_get_session({
            'name': data['session_name'],
            'organizations': [self.data_storage.main_org_id],
            'start_time': start_time.isoformat()
        })
        self.session_id = session_id

        agenda_item_id = self.data_storage.get_or_add_agenda_item({
            'name': data['agenda_name'].strip(),
            'datetime': start_time.isoformat(),
            'session': session_id,
            'order': data['order']
        })
        self.agenda_item_id = agenda_item_id

        state = ParserState.META
        start_time = None

        find_vote = r'([0-9]{3})\s*(.*?)\s*(\.[N|.]\s+\.[Z|P|\.])'

        vote_id = None
        result = None
        title = '' #data['agenda_name']
        string_with_result = ''
        motion = {}
        vote = {}

        lines = ''.join(self.pdf).split('\n')
        ballots = []
        for line in lines:
            if state == ParserState.META:
                if line.startswith('DNE'):
                    date_str = line.split(" ")[2]   
                if line.startswith('URA'):
                    time_str = line.split(" : ")[1]
                    start_time = datetime.strptime(f'{date_str} {time_str}', '%d.%m.%Y %X')
                    state = ParserState.PRE_TITLE
            elif state == ParserState.PRE_TITLE:
                if line.strip().startswith('AD'):
                    pass
                elif line.strip().startswith('PREDLOG SKLEPA:') or 'PREDLOG UGOTOVITVENEGA SKLEPA:' in line:
                    # reset tilte and go to title mode
                    state = ParserState.TITLE
                    title = ''
                elif line.strip().startswith('AMANDMA'):
                    state = ParserState.TITLE
                    title = f'{line.strip()}'
                elif line.strip().startswith('SKUPAJ'):
                    state = ParserState.TITLE
                else:
                    title = f'{title} {line.strip()}'

            elif state == ParserState.TITLE:
                if line.strip().startswith('PREDLOG SKLEPA') or line.strip().startswith('SKUPAJ'):
                    state = ParserState.RESULT
                    # TODO remove title limit
                    motion = {
                        'title': title[:950],
                        'text': title[:950],
                        'datetime': start_time.isoformat(),
                        'session': self.session_id,
                        'agenda_items': [self.agenda_item_id]
                    }
                    # TODO set needs_editing if needed
                    vote = {
                        'name': title[:950],
                        'timestamp': start_time.isoformat(),
                        'session': self.session_id,
                        'needs_editing': False,
                    }
                    if self.data_storage.check_if_motion_is_parsed(motion):
                        logging.info('vote is already parsed')
                        break
                else:
                    title = f'{title} {line.strip()}'
                    logging.warning(title)
            elif state == ParserState.RESULT:
                if line.strip().startswith('SKUPAJ'):
                    # TODO find result
                    positive = ['sprejme', 'seznani']
                    negative = ['zavrne']
                    if any(word in string_with_result for word in negative):
                        result = 'False'
                    elif any(word in string_with_result for word in positive):
                        result = 'True'
                    motion['result'] = result
                    motion_obj = self.data_storage.set_motion(motion)
                    vote['motion'] = motion_obj['id']
                    vote['result'] = result
                    vote_obj = self.data_storage.set_vote(vote)
                    vote_id = int(vote_obj['id'])

                    logging.warning(vote)
                    logging.warning('......:::::::SAVE:::::......')

                    state = ParserState.CONTENT
                else:
                    string_with_result = f'{string_with_result} {line.strip()}'

            elif state == ParserState.CONTENT:
                if line.strip().startswith('SKUPAJ'):
                    continue
                if line.strip().startswith('GLASOVANJE MESTNEGA SVETA MESTNE OBČINE LJUBLJANA'):
                    state = ParserState.META
                    self.data_storage.set_ballots(ballots)
                    title = ''
                    ballots = []
                    continue

                re_ballots = re.findall(find_vote, line)
                for ballot in re_ballots:
                    person_name = ballot[1]
                    option = self.get_option(ballot[2])
                    person_id, added_person = self.data_storage.get_or_add_person(
                        person_name.strip()
                    )
                    # person_party = self.data_storage.get_membership_of_member_on_date(
                    #     person_id,
                    #     self.start_time,
                    #     self.data_storage.main_org_id
                    # )
                    ballots.append({
                        'personvoter': person_id,
                        #'orgvoter': person_party,
                        'option': option,
                        'session': self.session_id,
                        #'datetime': self.start_time.isoformat(),
                        'vote': vote_id
                    })
        if ballots:
            self.data_storage.set_ballots(ballots)
            ballots = []
            # TODO make new vote

    def get_option(self, data):
        splited = re.split(r'\s+', data)
        kvorum, vote = splited
        if vote == '.Z':
            return 'for'
        elif vote == '.P':
            return 'against'
        elif kvorum == '.N':
            return 'abstain'
        else:
            return 'absent'


