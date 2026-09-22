class ConversationNotFoundError(LookupError):
    pass


class TopicNotFoundError(LookupError):
    pass


class MemoryNotFoundError(LookupError):
    pass


class DocumentNotFoundError(LookupError):
    pass


class DuplicateDocumentError(ValueError):
    pass


class EmptyDocumentError(ValueError):
    pass


class UnsupportedDocumentTypeError(ValueError):
    pass


class DocumentIndexError(RuntimeError):
    pass
