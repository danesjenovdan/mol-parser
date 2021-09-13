from parlaparser.data_parsers.base_parser import PdfParser
from parlaparser import settings
from enum import Enum
from collections import Counter
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
    REMOTE_VOTING_META = 7
    REMOTE_VOTING = 8

class VoteParser(PdfParser):
    def __init__(self, data, data_storage):
        super().__init__(data_storage, data['pdf_url'], 'temp_file.pdf')
        logging.debug(data['session_name'])

        start_time = data['date']
        start_time = start_time + timedelta(
            hours=int(data['time'].split(':')[0]),
            minutes=int(data['time'].split(':')[1]))

        self.start_time = start_time

        all_votes_ids = []


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
        if added:
            for link in data['links']:
                # save links
                link_data = {
                    'agenda_item': self.agenda_item_id,
                    'url': link['url'],
                    'name': link['title'],
                    'tags': [link['tag']]
                }
                self.data_storage.set_link(link_data)
        

        state = ParserState.META
        start_time = None

        find_vote = r'([0-9]{3})\s*(.*?)\s*(\.[N|.]\s+\.[Z|P|\.])'
        find_paging = r'([0-9]+\/[0-9]+)'

        vote_id = None
        result = None
        title = '' #data['agenda_name']
        string_with_result = ''
        motion = {}
        vote = {}

        lines = ''.join(self.pdf).split('\n')
        ballots = {}
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
                    motion = {
                        'title': title,
                        'text': title,
                        'datetime': start_time.isoformat(),
                        'session': self.session_id,
                        'agenda_items': [self.agenda_item_id]
                    }
                    # TODO set needs_editing if needed
                    vote = {
                        'name': title,
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
                    result = True
                    motion['result'] = result

                    if self.data_storage.check_if_motion_is_parsed(motion):
                        logging.info('vote is already parsed')
                        break

                    if 'amandma' in motion['title'].lower():
                        # skip saving legislation if is an amdandma
                        pass
                    elif 'Akta' in data['agenda_name']:
                        legislation_obj = self.data_storage.set_legislation({
                            'text': motion['title'],
                            'session': self.session_id,
                            'datetime': self.start_time.isoformat(),
                            'law_type': 'act',
                        })
                        motion['law'] = legislation_obj['id']
                    elif 'Odloka' in data['agenda_name']:
                        legislation_obj = self.data_storage.set_legislation({
                            'text': motion['title'],
                            'session': self.session_id,
                            'datetime': self.start_time.isoformat(),
                            'law_type': 'decree',
                        })
                        motion['law'] = legislation_obj['id']

                    motion_obj = self.data_storage.set_motion(motion)
                    vote['motion'] = motion_obj['id']
                    vote['result'] = result
                    vote_obj = self.data_storage.set_vote(vote)
                    vote_id = int(vote_obj['id'])
                    all_votes_ids.append(vote_id)
                    motion_id = motion_obj['id']
                    for link in data['links']:
                        # save links
                        link_data = {
                            'motion': motion_id,
                            #'agenda_item': self.agenda_item_id,
                            'url': link['url'],
                            'name': link['title'],
                            'tags': [link['tag']]
                        }
                        if 'law' in motion.keys():
                            link_data.update({'law': motion['law']})
                        self.data_storage.set_link(link_data)
 

                    logging.warning(vote)
                    logging.warning('......:::::::SAVE:::::......')

                    state = ParserState.CONTENT
                else:
                    string_with_result = f'{string_with_result} {line.strip()}'

            elif state == ParserState.CONTENT:
                if line.strip().startswith('SKUPAJ'):
                    continue
                if line.strip().startswith('GLASOVANJE NA DALJAVO'):
                    state = ParserState.REMOTE_VOTING_META
                    continue
                if line.strip().startswith('GLASOVANJE MESTNEGA SVETA MESTNE OBČINE LJUBLJANA'):
                    # Save ballots and set parser state to META
                    state = ParserState.META

                    self.patch_result(ballots, vote_id, motion_id)

                    self.data_storage.set_ballots(list(ballots.values()))
                    title = ''
                    ballots = {}
                    continue

                re_ballots = re.findall(find_vote, line)
                ballot_pairs = {}
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

                    # Work around for duplicated person ballots on the same vote
                    if person_id in ballots.keys():
                        if ballots[person_id]['option'] == 'absent':
                            ballots[person_id]['option'] = option

                    ballots[person_id] = {
                        'personvoter': person_id,
                        #'orgvoter': person_party,
                        'option': option,
                        'session': self.session_id,
                        'vote': vote_id
                    }
            elif state == ParserState.REMOTE_VOTING_META:
                if line.strip().startswith('Individualni odgovori:'):
                    state = ParserState.REMOTE_VOTING
                    continue
            elif state == ParserState.REMOTE_VOTING:
                if not line.strip():
                    continue
                if line.strip().startswith('GLASOVANJE MESTNEGA SVETA MESTNE OBČINE LJUBLJANA') or re.findall(find_paging, line):
                    state = ParserState.META

                    self.patch_result(ballots, vote_id, motion_id)

                    self.data_storage.set_ballots(list(ballots.values()))
                    title = ''
                    ballots = {}
                    continue

                logging.warning('SPLIT')
                logging.warning(line)
                person_name, option = line.split(':')

                person_id, added_person = self.data_storage.get_or_add_person(
                    person_name.strip()
                )
                remote_options = {
                    'NI GLASOVAL/A': 'abstain',
                    'DA': 'for',
                    'ZA': 'for',
                    'NE': 'against',
                    'PROTI': 'against',
                }
                try:
                    option = remote_options[option.strip()]
                except:
                    logging.warning('....:::::UNPREDICTED OPTION:::::......')
                    logging.warning(line)
                    state = ParserState.META
                    self.data_storage.set_ballots(list(ballots.values()))
                    # set vote as needs editing
                    for vote in all_votes_ids:
                        self.data_storage.patch_vote(vote, {'needs_editing': True})
                    break

                ballots[person_id] = {
                    'personvoter': person_id,
                    #'orgvoter': person_party,
                    'option': option,
                    'session': self.session_id,
                    'vote': vote_id
                }

        if ballots:
            self.patch_result(ballots, vote_id, motion_id)
            self.data_storage.set_ballots(list(ballots.values()))
            ballots = {}

    def patch_result(self, ballots, vote_id, motion_id):
        options = Counter([ballot['option'] for ballot in ballots.values()])
        result = options.get('for', 0) > options.get('against', 0)

        self.data_storage.patch_motion(motion_id, {'result': result})
        self.data_storage.patch_vote(vote_id, {'result': result})

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
