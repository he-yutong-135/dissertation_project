import argparse
from pathlib import Path

from src.engine import Engine

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Streaming JSON Schema Validator'
    )

    parser.add_argument(
        'schema',
        help='Path to the JSON Schema file'
    )

    parser.add_argument(
        'target',
        help='Path to the JSON input file'
    )

    parser.add_argument(
        '--log',
        default='validation.log',
        help='Path to the validation log file'
    )

    parser.add_argument(
        '--max-depth',
        type=int,
        default=1000,
        help='Maximum allowed JSON nesting depth'
    )

    args = parser.parse_args()

    engine = Engine(
        schema=Path(args.schema),
        target=Path(args.target),
        log_file_name=args.log,
        max_depth=args.max_depth
    )

    result, _ = engine.run()
    print(f"Validation result: {'valid' if result else 'invalid'}")