import logging

from parlaparser.data_parsers.base_parser import BaseParser


class CommitteeParser(BaseParser):
    def __init__(self, data, data_storage):
        super().__init__(data_storage)
        data = data

        organization = data_storage.organization_storage.get_or_add_object(
            {
                "name": data["org_name"],
                "parser_names": data["org_name"],
                "classification": data["classification"],
            }
        )

        person = data_storage.get_or_add_person(
            {"name": data["name"], "parser_names": data["name"]}
        )

        data_storage.memberships_storage.get_or_add_object(
            {
                "member": person.id,
                "organization": organization.id,
                "on_behalf_of": None,
                "start_time": data_storage.mandate_start_time.isoformat(),
                "role": data["role"] if data["role"] else "member",
                "mandate": data_storage.mandate_id,
            }
        )
