from twisted.internet.defer import Deferred

from .enums import UNSET, LOW, MEDIUM, HIGH, CRITICAL


class NodeID:
    def __init__(self, node_id, verify=True, priority=UNSET):
        # pass node_id = None to generate a random ID with a current timestamp.
        # priority defaults to CRITICAL if node_id is None, unless a value
        # other than UNSET is passed in.

        self.node_id = node_id
        self.address = node_id[0]
        self.preimage = node_id[1]
        self.priority = priority

        self.check_result = None
        self.on_check = Deferred()

        if node_id is None:
            self.generate_address()
        elif verify:
            self.verify_address()

    def set_priority(self, new_priority):
        if new_priority.value > self.priority.value:
            ...  # TODO

    def generate_address(self):
        ...  # TODO

    def verify_address(self):
        ...  # TODO

    @staticmethod
    def _getHash(input_bytes, work_factor):
        ...  # TODO
