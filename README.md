# Streaming JSON Schema Validator

This validator processes JSON input incrementally and validates it against a JSON Schema without constructing a complete in-memory representation of the input document. 

The final validation result is printed to the terminal, while detailed validation errors are written to the validation log.

## Requirements

- Python 3.13

Install the required dependencies with:

```bash
pip install -r requirements.txt
```

## Usage

Run the validator with:

```bash
python main.py <schema.json> <input.json>
```

### Arguments

- schema.json: Path to the JSON Schema file used for validation.
- input.json: Path to the JSON input file to be validated.
- --log: Optional path to the validation log file. The default is validation.log.
- --max-depth: Optional maximum allowed JSON nesting depth. The default is 1000.

### Example:

```bash
python main.py examples/schema.json examples/data.json
```

`demonstration.ipynb` contains more representative test examples 

## Evaluation

All evaluation notebooks were developed and tested with Python 3.13. Dependencies required by the evaluation code are listed in the corresponding `requirements.txt` files.

### Keyword Coverage

The correctness evaluation uses the official JSON Schema Test Suite for Draft 2020-12. The corresponding code and result are provided in `evaluation/keyword_coverage/json_test.ipynb`. 

### Performance

The performance evaluation code and results for different input sizes are provided in `evaluation/performance/test.ipynb` and `test2.ipynb`.

### Keyword-level Performance

The keyword-level performance evaluation code and results are provided in `evaluation/keyword_level_perf/test.ipynb`.

## Project structure

- `src/` — prototype implementation
- `graphs/` — graphs used in the thesis
- `evaluation/` — correctness and performance evaluation
- `examples/` — example schemas and JSON inputs
- `demonstration.ipynb` — representative usage examples
- `main.py` — command-line entry point

## Limitations

The current prototype does not support all JSON Schema Draft 2020-12 keywords. See evaluation directory for more information