from enum import Enum, auto
from dataclasses import dataclass
from typing import Iterator

TEST_FILE = 'data.json'

class TokenType(Enum):
    START_OBJECT = auto()  # {
    END_OBJECT = auto()    # }
    START_ARRAY = auto()   # [
    END_ARRAY = auto()     # ]
    KEY = auto()           # key in key:value pair
    VALUE = auto()         # value in key: value pair


@dataclass
class Token:
    type: TokenType
    content: any = None

    def __repr__(self):
        repr = f"{self.type.name}: ({self.content})"
        if self.content is None:
            repr =  f"{self.type.name}"
        return '{' + repr + '}'

class CharStream:
    def __init__(self, stream):
        self.stream = stream
        self.buf = []

    def get(self):
        if self.buf:
            return self.buf.pop()
        return self.stream.read(1)

    def pushback(self, ch):
        self.buf.append(ch)