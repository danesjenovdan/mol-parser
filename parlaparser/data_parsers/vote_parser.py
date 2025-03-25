import logging
import re
from collections import Counter
from datetime import datetime, timedelta
from enum import Enum

from parlaparser import settings
from parlaparser.data_parsers.base_parser import PdfParser


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
        super().__init__(data_storage, data["pdf_url"], "temp_file.pdf")
        logging.debug(data["session_name"])

        start_time = data["date"]
        start_time = start_time + timedelta(
            hours=int(data["time"].split(":")[0]),
            minutes=int(data["time"].split(":")[1]),
        )

        self.start_time = start_time

        all_votes_ids = []

        session = self.data_storage.session_storage.get_or_add_object(
            {
                "name": data["session_name"],
                "organizations": [self.data_storage.main_org_id],
                "start_time": start_time.isoformat(),
                "mandate": self.data_storage.mandate_id,
            }
        )
        if session.is_new and data.get("session_notes", None):
            # add notes
            link_data = {
                "session": session.id,
                "url": data["session_notes"]["url"],
                "name": data["session_notes"]["title"],
            }
            self.data_storage.parladata_api.links.set(link_data)

        self.session = session
        if data["agenda_name"]:
            agenda_item = session.agenda_items_storage.get_or_add_object(
                {
                    "name": data["agenda_name"].strip(),
                    "datetime": start_time.isoformat(),
                    "session": session.id,
                    "order": data["order"],
                }
            )
            if agenda_item.is_new:
                for link in data["links"]:
                    # save links
                    link_data = {
                        "agenda_item": agenda_item.id,
                        "url": link["url"],
                        "name": link["title"],
                        "tags": [link["tag"]],
                    }
                    self.data_storage.parladata_api.links.set(link_data)
        else:
            agenda_item = None

        state = ParserState.META
        start_time = None

        find_vote = r"([0-9]{3})\s*(.*?)\s*(\.[N|.]\s+\.[Z|P|\.])"
        find_paging = r"([0-9]+\/[0-9]+)"

        vote_id = None
        result = None
        title = ""  # data['agenda_name']
        pre_title = ""
        string_with_result = ""
        motion = {}
        vote = {}

        self.items = []

        self.vote_count = 0

        legislation_id = None

        legislation_added = False

        lines = "".join(self.pdf).split("\n")
        item = {"links": []}
        revoted = False
        ballots = {}
        for line in lines:
            if not line.strip():
                continue
            if state == ParserState.META:
                if line.startswith("DNE"):
                    date_str = line.split(" ")[2]
                if line.startswith("URA"):
                    time_str = line.split(" : ")[1]
                    start_time = datetime.strptime(
                        f"{date_str} {time_str}", "%d.%m.%Y %X"
                    )
                    state = ParserState.PRE_TITLE
            elif state == ParserState.PRE_TITLE:
                if line.strip().startswith("AD"):
                    pass
                elif (
                    "PREDLOG SKLEPA" in line
                    or "PREDLOGU SKLEPA" in line
                    or "PREDLOG UGOTOVITVENEGA SKLEPA:" in line
                    or "PREDLOG POSTOPKOVNEGA PREDLOGA:" in line
                ):
                    # reset tilte and go to title mode
                    if (
                        "ponovitev glasovanja" in line.lower()
                        or "ponovno glasovanje" in line.lower()
                    ):
                        revoted = True
                    state = ParserState.TITLE
                    title = ""
                elif "AMANDMA" in line:
                    state = ParserState.TITLE
                    if (
                        "ponovitev glasovanja" in line.lower()
                        or "ponovno glasovanje" in line.lower()
                    ):
                        revoted = True
                    title = f"{line.strip()}"
                elif line.strip().startswith("SKUPAJ"):
                    if (
                        "ponovitev glasovanja" in line.lower()
                        or "ponovno glasovanje" in line.lower()
                    ):
                        revoted = True
                    state = ParserState.TITLE
                else:
                    title = f"{title} {line.strip()}"
                    if not legislation_added:
                        pre_title = f"{pre_title} {line.strip()}"

            elif state == ParserState.TITLE:
                # TODO do this better
                # if line.strip().startswith('PREDLOG SKLEPA') or line.strip().startswith('SKUPAJ') or line.strip().startswith('PREDLOGU SKLEPA'):
                if len(line.strip()) > 1 and line.strip()[1] == ")":
                    line = line.strip()[2:].strip()
                if line.strip().startswith("AMANDMA"):
                    if not title.strip().startswith("AMANDMA"):
                        title = ""
                if line.strip().startswith("SKUPAJ"):
                    state = ParserState.RESULT
                    motion = {
                        "title": title,
                        "text": title,
                        "datetime": start_time.isoformat(),
                        "session": self.session.id,
                    }
                    if agenda_item:
                        motion.update({"agenda_items": [agenda_item.id]})
                    if ("osnutek Odloka" in title) or ("osnutek Akta" in title):
                        motion["tags"] = ["first-reading"]
                    # TODO set needs_editing if needed
                    vote = {
                        "name": title,
                        "timestamp": start_time.isoformat(),
                        "session": self.session.id,
                        "needs_editing": False,
                    }
                    if session.vote_storage.check_if_motion_is_parsed(motion):
                        logging.warning("vote is already parsed")
                        break
                if (
                    line.strip().startswith("PREDLOG SKLEPA")
                    or line.strip().startswith("PREDLOGU SKLEPA")
                    or line.strip().startswith("PREDLOG POSTOPKOVNEGA PREDLOGA")
                ):
                    title = ""
                else:
                    title = f"{title} {line.strip()}"
                    logging.warning(title)
            elif state == ParserState.RESULT:
                if line.strip().startswith("SKUPAJ"):
                    result = True
                    motion["result"] = result

                    if session.vote_storage.check_if_motion_is_parsed(motion):
                        logging.info("vote is already parsed")
                        break

                    if pre_title.strip() and ")" == pre_title.strip()[1]:
                        pre_title = pre_title.strip()[2:]

                    # if 'amandma' in motion['title'].lower():
                    #    # skip saving legislation if is an amdandma
                    #    pass
                    if legislation_added:
                        pass

                    elif "PREDLOG ODLOKA" in pre_title:
                        item["law"] = {
                            "text": pre_title,
                            "session": self.session.id,
                            "timestamp": self.start_time.isoformat(),
                            "classification": self.data_storage.legislation_storage.get_legislation_classifications_by_name(
                                "decree"
                            ),
                            "mandate": self.data_storage.mandate_id,
                        }
                        item["consideration"] = {
                            "session": self.session.id,
                            "timestamp": self.start_time.isoformat(),
                            "procedure_phase": 1,
                            "organization": self.data_storage.main_org_id,
                        }
                        legislation_added = True

                    item["revoted"] = revoted
                    revoted = False
                    item["motion"] = motion
                    vote["result"] = result
                    item["vote"] = vote

                    self.vote_count += 1
                    for link in data["links"]:
                        # add links
                        link_data = {
                            "url": link["url"],
                            "name": link["title"],
                            "tags": [link["tag"]],
                        }
                        item["links"].append(link_data)

                    logging.warning(vote)
                    logging.warning("......:::::::SAVE:::::......")

                    state = ParserState.CONTENT
                else:
                    string_with_result = f"{string_with_result} {line.strip()}"

            elif state == ParserState.CONTENT:
                if line.strip().startswith("SKUPAJ"):
                    continue
                if line.strip().startswith("GLASOVANJE NA DALJAVO"):
                    state = ParserState.REMOTE_VOTING_META
                    continue
                if line.strip().startswith(
                    "GLASOVANJE MESTNEGA SVETA MESTNE OBČINE LJUBLJANA"
                ):
                    # Save ballots and set parser state to META
                    state = ParserState.META

                    item["ballots"] = ballots

                    title = ""
                    ballots = {}
                    self.items.append(item)
                    item = {"links": []}
                    continue

                re_ballots = re.findall(find_vote, line)
                ballot_pairs = {}
                for ballot in re_ballots:
                    person_name = ballot[1]
                    option = self.get_option(ballot[2])
                    person = self.data_storage.people_storage.get_or_add_object(
                        {"name": person_name.strip()}
                    )

                    # Work around for duplicated person ballots on the same vote
                    if person.id in ballots.keys():
                        if ballots[person.id]["option"] == "absent":
                            ballots[person.id]["option"] = option

                    ballots[person.id] = {
                        "personvoter": person.id,
                        "option": option,
                        "session": self.session.id,
                        "vote": vote_id,
                    }
            elif state == ParserState.REMOTE_VOTING_META:
                if line.strip().startswith("Individualni odgovori:"):
                    state = ParserState.REMOTE_VOTING
                    continue
            elif state == ParserState.REMOTE_VOTING:
                if not line.strip():
                    continue

                if self.vote_count > 1:
                    for vote in all_votes_ids:
                        vote.patch_vote({"needs_editing": True})
                        break
                if line.strip().startswith(
                    "GLASOVANJE MESTNEGA SVETA MESTNE OBČINE LJUBLJANA"
                ) or re.findall(find_paging, line):
                    state = ParserState.META

                    item["ballots"] = ballots

                    self.items.append(item)
                    item = {"links": []}

                    title = ""
                    ballots = {}
                    self.vote_count = 0
                    continue

                logging.warning("SPLIT")
                logging.warning(line)
                try:
                    person_name, option = line.split(":")

                    person = self.data_storage.people_storage.get_or_add_object(
                        {
                            "name": person_name.strip(),
                        }
                    )
                    remote_options = {
                        "NI GLASOVAL/A": "abstain",
                        "DA": "for",
                        "ZA": "for",
                        "NE": "against",
                        "PROTI": "against",
                    }

                    option = remote_options[option.strip()]
                except:
                    logging.warning("....:::::UNPREDICTED OPTION:::::......")
                    logging.warning(line)
                    state = ParserState.META

                    ballots = {}
                    self.items.append(item)
                    item = {"links": []}

                    # set vote as needs editing
                    for vote in all_votes_ids:
                        vote.patch_vote({"needs_editing": True})
                    break

                ballots[person.id] = {
                    "personvoter": person.id,
                    "option": option,
                    "session": self.session.id,
                    "vote": vote.id,
                }

        if ballots:
            item["ballots"] = ballots
            self.items.append(item)
            ballots = {}

        self.save_motions()

    def save_motions(self):
        # delete repeated voting
        revoted_names = []
        for item in self.items:
            if item["revoted"]:
                revoted_names.append(item["motion"]["title"])

        for item in self.items:
            if item["motion"]["title"] in revoted_names and not item["revoted"]:
                # skip vote if has repeated voting
                continue
            if "law" in item.keys():
                legislation = self.data_storage.legislation_storage.set_law(item["law"])
                item["consideration"]["legislation"] = legislation.id
                self.data_storage.legislation_storage.set_legislation_consideration(
                    item["consideration"]
                )
                item["motion"]["law"] = legislation.id

            motion = self.session.vote_storage.get_or_add_object(item["motion"])

            for person_id in item["ballots"].keys():
                item["ballots"][person_id]["vote"] = motion.vote.id

            self.patch_result(item["ballots"], motion.vote, motion)
            self.session.vote_storage.set_ballots(list(item["ballots"].values()))
            self.validate_ballots(item["ballots"], motion.vote, self.start_time)

            for link in item["links"]:
                link.update({"motion": motion.id})
                if "law" in item.keys():
                    link.update({"law": legislation.id})
                self.data_storage.parladata_api.links.set(link)

    def validate_ballots(self, ballots, vote, date):
        num_of_members = 0
        main_org = self.data_storage.organization_storage.get_organization_by_id(
            int(self.data_storage.main_org_id)
        )
        for membership in main_org.memberships:
            if membership.role == "voter":
                if membership.start_time and membership.start_time > date:
                    continue
                if membership.end_time and membership.end_time < date:
                    continue
                else:
                    num_of_members += 1

        if len(list(ballots.values())) != num_of_members:
            vote.patch({"needs_editing": True})

    def patch_result(self, ballots, vote, motion):
        options = Counter([ballot["option"] for ballot in ballots.values()])
        result = options.get("for", 0) > options.get("against", 0)

        motion.patch({"result": result})
        vote.patch({"result": result})

    def get_option(self, data):
        splited = re.split(r"\s+", data)
        kvorum, vote = splited
        if vote == ".Z":
            return "for"
        elif vote == ".P":
            return "against"
        elif kvorum == ".N":
            return "abstain"
        else:
            return "absent"
