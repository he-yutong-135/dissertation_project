import sys
from enum import Enum, auto
from dataclasses import dataclass
from io import StringIO
import json
from pathlib import Path


TEST_FILE = 'data.json'

class TokenType(Enum):
    START_OBJECT = auto()  # {
    END_OBJECT = auto()    # }
    START_ARRAY = auto()   # [
    END_ARRAY = auto()     # ]
    KEY = auto()           # key in key:value pair
    VALUE = auto()         # value in key: value pair

json_end_symbols = (',', ':', '}', ']')
json_skip_symbols = (' ', '\t', '\n', '\r')

@dataclass
class Token:
    type: TokenType
    content: any = None
    line: int = None

    def is_start_object(self):
        return self.type == TokenType.START_OBJECT
    
    def is_start_array(self):
        return self.type == TokenType.START_ARRAY
    
    def is_end_object(self):
        return self.type == TokenType.END_OBJECT
    
    def is_end_array(self):
        return self.type == TokenType.END_ARRAY
    
    def is_key(self):
        return self.type == TokenType.KEY
    
    def is_value(self):
        return self.type == TokenType.VALUE

    def __repr__(self):
        repr = f"{self.type.name}: ({self.content})"
        if not (self.is_key() or self.is_value()):
            repr =  f"{self.type.name}"
        return '{' + repr + f' [line: {self.line}]' + '}'

class Char:
    def __init__(self, v, l):
        self.value = v
        self.line = l

    def __str__(self):
        return f'char({self.value, self.line})'

    def __repr__(self):
        return self.__str__()

class CharStream:
    def __init__(self, stream):
        self.stream = stream
        self.buf = []
        self.line = 1

    def get(self):
        if self.buf:
            return self.buf.pop()
        c = self.stream.read(1)
        char = Char(c, self.line)
        
        if char.value == "\n":
            self.line += 1

        # print(f'get: {char}')

        return char

    def pushback(self, char):
        # store a char item
        self.buf.append(char)


# lexical analysis: split input into raw tokens (structural symbols, strings, raw values)
def raw_lexer(stream):
    while True:
        char = stream.get()
        c = char.value
        if c == "":
            return
        if c in json_skip_symbols:
            continue

        # structural symbols
        if c in "{}[]:,":
            yield ("STRUCT", char)
        elif c == '"':
            s = read_string(stream)
            # incomplete strings are not processed
            if s is not None:
                yield ("STRING", Char(s, char.line))
        else:
            yield ("RAW", Char(read_value(char, stream), char.line))

# read a JSON string
def read_string(char_stream: CharStream):
    buf = []

    while True:
        char = char_stream.get()
        c = char.value

        if c == '':
            return None

        if c == '"':
            break

        if c == '\\':
            esc = char_stream.get().value

            if esc == '':
                raise ValueError("Unterminated escape sequence")

            # unicode escape: \uXXXX
            if esc == 'u':
                hex_digits = ''.join(char_stream.get().value for _ in range(4))
                code = int(hex_digits, 16)

                # high surrogate
                if 0xD800 <= code <= 0xDBFF:

                    if char_stream.get().value != '\\' or char_stream.get().value != 'u':
                        raise ValueError("Expected low surrogate")

                    low_hex = ''.join(char_stream.get().value for _ in range(4))
                    low = int(low_hex, 16)

                    if not (0xDC00 <= low <= 0xDFFF):
                        raise ValueError("Invalid low surrogate")

                    code = (
                        ((code - 0xD800) << 10)
                        + (low - 0xDC00)
                        + 0x10000
                    )

                elif 0xDC00 <= code <= 0xDFFF:
                    raise ValueError("Unexpected low surrogate")

                buf.append(chr(code))

            else:
                escape_map = {
                    '"': '"',
                    '\\': '\\',
                    '/': '/',
                    'b': '\b',
                    'f': '\f',
                    'n': '\n',
                    'r': '\r',
                    't': '\t',
                }

                if esc not in escape_map:
                    raise ValueError(f"Invalid escape character: \\{esc}")

                buf.append(escape_map[esc])

        else:
            buf.append(c)

    return ''.join(buf)

# read a JSON raw value (number, true, false, null) 
def read_value(first_char: Char, char_stream: CharStream):
    buf = [first_char.value]


    while True:
        char = char_stream.get()
        c = char.value

        if c == '':
            break

        if c in json_end_symbols:
            char_stream.pushback(char)
            break

        buf.append(c)

    raw_value = ''.join(buf).strip()
    if raw_value == "true": return True
    if raw_value == "false": return False
    if raw_value == "null": return None

    try:
        return int(raw_value)
    except ValueError:
        try:
            return float(raw_value)
        except ValueError:
            raise ValueError(f"Unexpected value: {raw_value}")

def normalize_key(s):
    return s.strip('"')
        
# token generation: convert raw tokens into intermediate representation of JSON structure
# that can be directly feed into the verifier
def token_gen(tokens):
    next_state = "KEY"
    stack = [] # to track whether we are in an object or array context

    for type, char in tokens:
        # print(f"DEBUG: type={type}, value={value}, next_state={next_state}, stack={stack}")
        value = char.value

        ## structural symbols -> tokens and state transitions
        if value == '{':
            stack.append('{')
            yield Token(TokenType.START_OBJECT, line=char.line)
            next_state = "KEY"

        elif value == '[':
            stack.append('[')
            yield Token(TokenType.START_ARRAY, line=char.line)
            next_state = "VALUE"

        elif value == '}':
            stack.pop()
            yield Token(TokenType.END_OBJECT, line=char.line)
            next_state = "KEY_OR_END"

        elif value == ']':
            stack.pop()
            yield Token(TokenType.END_ARRAY, line=char.line)
            next_state = "KEY_OR_END"

        elif value == ':':
            next_state = "VALUE"

        elif value == ',':
            if stack[-1] == "{":
                next_state = "KEY"
            else:
                next_state = "VALUE"

        # string / raw value -> key or value
        if type in ("STRING", "RAW"):
            if not stack:
                yield Token(TokenType.VALUE, value, line=char.line)
                continue

            # if in an object context
            if stack[-1] == "{":
                if next_state == "KEY":
                    yield Token(TokenType.KEY, normalize_key(value), line=char.line)
                    next_state = "COLON"
                elif next_state == "VALUE":
                    yield Token(TokenType.VALUE, value, line=char.line)
                    next_state = "COMMA_OR_END"
            elif stack[-1] == "[":
                if next_state == "VALUE":
                    yield Token(TokenType.VALUE, value, line=char.line)
                    next_state = "COMMA_OR_END"
                
def token_stream_from_stream(stream):
    char_stream = CharStream(stream)
    yield from token_gen(raw_lexer(char_stream))

def token_stream(source):
    if isinstance(source, Path):
        with open(source) as f:
            yield from token_stream_from_stream(f)

    # for reading test data
    else:
        print(json.dumps(source))
        yield from token_stream_from_stream(
            StringIO(json.dumps(source))
        )

def print_token_stream(token_stream):
    print("token stream: ==>")
    for token in token_stream:
            print(token, end=' ')
    print()

def main(file_name):
    print_token_stream(token_stream(file_name))

if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        main(TEST_FILE)