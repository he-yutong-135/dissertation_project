from enum import Enum, auto
from dataclass import dataclass
from typing import Any, Iterator

TEST_FILE = 'data.json'

class TokenType(Enum):
    START_OBJECT = auto()  # {
    END_OBJECT = auto()    # }
    START_ARRAY = auto()   # [
    END_ARRAY = auto()     # ]
    KEY = auto()           # key in key:value pair
    VALUE = auto()         # value in key: value pair


json_structural_symbol_map = {
    '{': TokenType.START_OBJECT,
    '}': TokenType.END_OBJECT,
    '[': TokenType.START_ARRAY,
    ']': TokenType.END_ARRAY
}

json_end_symbols = (',', ':', '}', ']')

@dataclass
class Token:
    type: TokenType
    value: any = None

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


def tokenize(stream: str) -> Iterator[Token]:
    char_stream = CharStream(stream)
    next_token_type = None

    while True:
        c = char_stream.get()

        # skip whitespace
        if c.isspace():
            continue

        # if c is a structural symbol, yield the corresponding token
        if c in json_structural_symbol_map.keys():
            yield Token(json_structural_symbol_map[c])
            continue

        if c == '"':
            yield Token("VALUE", read_string(char_stream))
            continue

        yield Token("VALUE", read_value(c, char_stream))


def read_string(char_stream: CharStream):
    buf = ['"']

    while True:
        c = char_stream.get()

        if c == '':
            raise ValueError("Unterminated string")

        buf.append(c)

        if c == '\\':
            buf.append(char_stream.get())
            continue

        if c == '"':
            break

    return ''.join(buf)
        
def read_value(first_char:str, char_stream: CharStream):
    buf = [first_char]

    while True:
        c = char_stream.get()

        if c == '':
            break

        if c in json_end_symbols:
            char_stream.pushback(c)
            break

        buf.append(c)

    return ''.join(buf).strip()
        
        

def main(file_name):
    pass


if __name__ == "__main__":
    main()