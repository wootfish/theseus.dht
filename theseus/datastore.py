class DataStore:
    # so far this is a very naive implementation. it just stores everything
    # forever.

    def __init__(self):
        self.data = {}

    #def getCallbacks(self):
    #    def get_query(args):
    #        return self.data.get(args.get(b'addr'))

    #    def put_query(args):
    #        addr = args.get(b'addr')
    #        if addr is not None and type(addr) is bytes and len(addr) == 20:
    #            self.data.setdefault(addr, []).append(args)
    #            return {}

    #    def get_response(args):
    #        ...  # TODO what do we do here? do we want to store retrieved data for a while? probably, right?

    #    return get_query, put_query, get_response
