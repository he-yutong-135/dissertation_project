import sys
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

json_end_symbols = (',', ':', '}', ']')
json_skip_symbols = (' ', '\t', '\n', '\r')

@dataclass
class Token:
    type: TokenType
    content: any = None

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


# lexical analysis: split input into raw tokens (structural symbols, strings, raw values)
def raw_lexer(stream):
    while True:
        c = stream.get()
        if c == "":
            return
        if c in json_skip_symbols:
            continue

        # structural symbols
        if c in "{}[]:,":
            yield ("STRUCT", c)
        elif c == '"':
            yield ("STRING", read_string(stream))
        else:
            yield ("RAW", read_value(c, stream))

# read a JSON string
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

# read a JSON raw value (number, true, false, null) 
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

def normalize_key(s):
    return s.strip('"')
        
# token generation: convert raw tokens into intermediate representation of JSON structure
# that can be directly feed into the verifier
def token_gen(tokens):
    next_state = "KEY"
    stack = [] # to track whether we are in an object or array context

    for type, value in tokens:
        # print(f"DEBUG: type={type}, value={value}, next_state={next_state}, stack={stack}")

        ## structural symbols -> tokens and state transitions
        if value == '{':
            stack.append('{')
            yield Token(TokenType.START_OBJECT)
            next_state = "KEY"

        elif value == '[':
            stack.append('[')
            yield Token(TokenType.START_ARRAY)
            next_state = "VALUE"

        elif value == '}':
            if not stack or stack[-1] != '{':
                raise ValueError("Mismatched }")
            stack.pop()
            yield Token(TokenType.END_OBJECT)
            next_state = "KEY_OR_END"

        elif value == ']':
            if not stack or stack[-1] != '[':
                raise ValueError("Mismatched ]")
            stack.pop()
            yield Token(TokenType.END_ARRAY)
            next_state = "KEY_OR_END"

        elif value == ':':
            if next_state != "COLON":
                raise ValueError("Unexpected :")

            next_state = "VALUE"

        elif value == ',':
            if not stack and next_state != "COMMA_OR_END":
                raise ValueError("Unexpected ,")
            if stack[-1] == "{":
                next_state = "KEY"
            else:
                next_state = "VALUE"

        # string / raw value -> key or value
        if type in ("STRING", "RAW"):

            if not stack:
                yield Token(TokenType.VALUE, value)
                continue

            # if in an object context
            if stack[-1] == "{":
            
                if next_state == "KEY":
                    if type != "STRING":
                        raise ValueError("Expected string for key")
                    
                    yield Token(TokenType.KEY, normalize_key(value))
                    next_state = "COLON"


                elif next_state == "VALUE":
                    yield Token(TokenType.VALUE, value)
                    next_state = "COMMA_OR_END"

                else:
                    raise ValueError(f"Unexpected {type} in state {next_state}")
                
            elif stack[-1] == "[":
                if next_state == "VALUE":
                    yield Token(TokenType.VALUE, value)
                    next_state = "COMMA_OR_END"
                else:
                    raise ValueError(f"Unexpected {type} in state {next_state} within array")
        
def token_stream(file_name):
    with open(file_name, 'r') as f:
        char_stream = CharStream(f)
        for token in token_gen(raw_lexer(char_stream)):
            yield token

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