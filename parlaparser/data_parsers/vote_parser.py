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
            'start_time': start_time.isoformat(),
            'mandate': self.data_storage.mandate_id
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
        if data['agenda_name']:
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
        else:
            self.agenda_item_id = None


        state = ParserState.META
        start_time = None

        find_vote = r'([0-9]{3})\s*(.*?)\s*(\.[N|.]\s+\.[Z|P|\.])'
        find_paging = r'([0-9]+\/[0-9]+)'

        vote_id = None
        result = None
        title = '' #data['agenda_name']
        pre_title = ''
        string_with_result = ''
        motion = {}
        vote = {}

        self.items = []

        self.vote_count = 0

        legislation_id = None

        legislation_added = False

        lines = ''.join(self.pdf).split('\n')
        item = {
            'links': []
        }
        revoted = False
        ballots = {}
        for line in lines:
            if not line.strip():
                continue
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
                elif 'PREDLOG SKLEPA' in line or 'PREDLOGU SKLEPA' in line or 'PREDLOG UGOTOVITVENEGA SKLEPA:' in line or 'PREDLOG POSTOPKOVNEGA PREDLOGA:' in line:
                    # reset tilte and go to title mode
                    if 'ponovitev glasovanja' in line.lower() or 'ponovno glasovanje' in line.lower():
                        revoted = True
                    state = ParserState.TITLE
                    title = ''
                elif 'AMANDMA' in line:
                    state = ParserState.TITLE
                    if 'ponovitev glasovanja' in line.lower() or 'ponovno glasovanje' in line.lower():
                        revoted = True
                    title = f'{line.strip()}'
                elif line.strip().startswith('SKUPAJ'):
                    if 'ponovitev glasovanja' in line.lower() or 'ponovno glasovanje' in line.lower():
                        revoted = True
                    state = ParserState.TITLE
                else:
                    title = f'{title} {line.strip()}'
                    if not legislation_added:
                        pre_title = f'{pre_title} {line.strip()}'

            elif state == ParserState.TITLE:
                # TODO do this better
                #if line.strip().startswith('PREDLOG SKLEPA') or line.strip().startswith('SKUPAJ') or line.strip().startswith('PREDLOGU SKLEPA'):
                if len(line.strip()) > 1 and line.strip()[1]==')':
                    line = line.strip()[2:].strip()
                if line.strip().startswith('AMANDMA'):
                    if not title.strip().startswith('AMANDMA'):
                        title = ''
                if line.strip().startswith('SKUPAJ'):
                    state = ParserState.RESULT
                    motion = {
                        'title': title,
                        'text': title,
                        'datetime': start_time.isoformat(),
                        'session': self.session_id,
                    }
                    if self.agenda_item_id:
                        motion.update({
                            'agenda_items': [self.agenda_item_id]
                        })
                    if ('osnutek Odloka' in title) or ('osnutek Akta' in title):
                        motion['tags'] = ['first-reading']
                    # TODO set needs_editing if needed
                    vote = {
                        'name': title,
                        'timestamp': start_time.isoformat(),
                        'session': self.session_id,
                        'needs_editing': False,
                    }
                    print(self.data_storage.get_motion_key(motion))
                    if self.data_storage.check_if_motion_is_parsed(motion):
                        logging.warning('vote is already parsed')
                        break
                if line.strip().startswith('PREDLOG SKLEPA') or line.strip().startswith('PREDLOGU SKLEPA') or line.strip().startswith('PREDLOG POSTOPKOVNEGA PREDLOGA'):
                    title = ''
                else:
                    title = f'{title} {line.strip()}'
                    logging.warning(title)
            elif state == ParserState.RESULT:
                if line.strip().startswith('SKUPAJ'):
                    result = True
                    motion['result'] = result

                    if self.data_storage.check_if_motion_is_parsed(motion):
                        logging.info('vote is already parsed')
                        break

                    if pre_title.strip() and ')' == pre_title.strip()[1]:
                        pre_title = pre_title.strip()[2:]

                    #if 'amandma' in motion['title'].lower():
                    #    # skip saving legislation if is an amdandma
                    #    pass
                    if legislation_added:
                        pass

                    elif 'PREDLOG ODLOKA' in pre_title:
                        item['law'] = {
                            'text': pre_title,
                            'session': self.session_id,
                            'timestamp': self.start_time.isoformat(),
                            'classification': self.data_storage.legislation_classification['decree'],
                            'mandate': self.data_storage.mandate_id
                        }
                        item['consideration'] = {
                            'session': self.session_id,
                            'timestamp': self.start_time.isoformat(),
                            'procedure_phase': 1,
                            'organization': self.data_storage.main_org_id,
                        }
                        legislation_added = True


                    item['revoted'] = revoted
                    revoted = False
                    item['motion'] = motion
                    vote['result'] = result
                    item['vote'] = vote

                    self.vote_count += 1
                    for link in data['links']:
                        # add links
                        link_data = {
                            'url': link['url'],
                            'name': link['title'],
                            'tags': [link['tag']]
                        }
                        item['links'].append(link_data)

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

                    item['ballots'] = ballots

                    title = ''
                    ballots = {}
                    self.items.append(item)
                    item = {
                        'links': []
                    }
                    continue

                re_ballots = re.findall(find_vote, line)
                ballot_pairs = {}
                for ballot in re_ballots:
                    person_name = ballot[1]
                    option = self.get_option(ballot[2])
                    person_id, added_person = self.data_storage.get_or_add_person(
                        person_name.strip()
                    )

                    # Work around for duplicated person ballots on the same vote
                    if person_id in ballots.keys():
                        if ballots[person_id]['option'] == 'absent':
                            ballots[person_id]['option'] = option

                    ballots[person_id] = {
                        'personvoter': person_id,
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

                if self.vote_count > 1:
                    for vote in all_votes_ids:
                        self.data_storage.patch_vote(vote, {'needs_editing': True})
                        break
                if line.strip().startswith('GLASOVANJE MESTNEGA SVETA MESTNE OBČINE LJUBLJANA') or re.findall(find_paging, line):
                    state = ParserState.META

                    item['ballots'] = ballots

                    self.items.append(item)
                    item = {
                        'links': []
                    }


                    title = ''
                    ballots = {}
                    self.vote_count = 0
                    continue

                logging.warning('SPLIT')
                logging.warning(line)
                try:
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

                    option = remote_options[option.strip()]
                except:
                    logging.warning('....:::::UNPREDICTED OPTION:::::......')
                    logging.warning(line)
                    state = ParserState.META

                    ballots = {}
                    self.items.append(item)
                    item = {
                        'links': []
                    }


                    # set vote as needs editing
                    for vote in all_votes_ids:
                        self.data_storage.patch_vote(vote, {'needs_editing': True})
                    break

                ballots[person_id] = {
                    'personvoter': person_id,
                    'option': option,
                    'session': self.session_id,
                    'vote': vote_id
                }

        if ballots:
            item['ballots'] = ballots
            self.items.append(item)
            ballots = {}

        self.save_motions()

    def save_motions(self):
        # delete repeated voting
        revoted_names = []
        for item in self.items:
            if item['revoted']:
                revoted_names.append(item['motion']['title'])

        for item in self.items:
            if item['motion']['title'] in revoted_names and not item['revoted']:
                # skip vote if has repeated voting
                continue
            if 'law' in item.keys():
                legislation_obj = self.data_storage.set_legislation(item['law'])
                legislation_id = legislation_obj['id']
                item['consideration']['legislation'] = legislation_id
                self.data_storage.set_legislation_consideration(item['consideration'])

            motion_obj = self.data_storage.set_motion(item['motion'])
            motion_id = motion_obj['id']
            item['vote']['motion'] = motion_id
            vote_obj = self.data_storage.set_vote(item['vote'])
            vote_id = int(vote_obj['id'])

            for person_id in item['ballots'].keys():
                item['ballots'][person_id]['vote'] = vote_id

            self.patch_result(item['ballots'], vote_id, motion_id)
            self.data_storage.set_ballots(list(item['ballots'].values()))
            self.validate_ballots(item['ballots'], vote_id, self.start_time)

            for link in item['links']:
                link.update({'motion': motion_id})
                if 'law' in item.keys():
                    link.update({'law': legislation_id})
                self.data_storage.set_link(link)

    def validate_ballots(self, ballots, vote_id, date):
        num_of_members = len(self.data_storage.get_members_on_date(date, int(self.data_storage.main_org_id)))
        if len(list(ballots.values())) != num_of_members:
            self.data_storage.patch_vote(vote_id, {'needs_editing': True})

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
